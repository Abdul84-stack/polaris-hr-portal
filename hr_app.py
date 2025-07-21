import streamlit as st
import json
from datetime import datetime, timedelta, date
import os
import pandas as pd
import plotly.express as px
from fpdf import FPDF
import base64
from passlib.hash import pbkdf2_sha256 # For password hashing
import requests # For making HTTP requests to external APIs (e.g., Gemini)
import uuid # For generating unique IDs

# --- SET STREAMLIT PAGE CONFIG (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="Polaris Digitech HR Portal",
    layout="wide", # Use wide layout for more space
    initial_sidebar_state="expanded"
)
# --- END CORRECT PLACEMENT ---

# --- Configuration & Paths ---
DATA_DIR = "hr_data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
LEAVE_REQUESTS_FILE = os.path.join(DATA_DIR, "leave_requests.json")
OPEX_CAPEX_REQUESTS_FILE = os.path.join(DATA_DIR, "opex_capex_requests.json")
PERFORMANCE_GOALS_FILE = os.path.join(DATA_DIR, "performance_goals.json")
SELF_APPRAISALS_FILE = os.path.join(DATA_DIR, "self_appraisals.json")
PAYROLL_FILE = os.path.join(DATA_DIR, "payroll.json")
BENEFICIARIES_FILE = os.path.join(DATA_DIR, "beneficiaries.json")
HR_POLICIES_FILE = os.path.join(DATA_DIR, "hr_policies.json")
CHAT_MESSAGES_FILE = os.path.join(DATA_DIR, "chat_messages.json") # NEW: Chat messages file
ATTENDANCE_RECORDS_FILE = os.path.join(DATA_DIR, "attendance_records.json") # NEW: Attendance records file
DISCIPLINARY_RECORDS_FILE = os.path.join(DATA_DIR, "disciplinary_records.json") # NEW: Disciplinary records file


# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

ICON_BASE_DIR = "Project_Resources" # Assuming you create this folder and put images inside
if not os.path.exists(ICON_BASE_DIR):
    os.makedirs(ICON_BASE_DIR)

# Ensure 'leave_documents' and 'opex_capex_documents' directories exist for file uploads
os.makedirs("leave_documents", exist_ok=True)
os.makedirs("opex_capex_documents", exist_ok=True)
os.makedirs("opex_capex_pdfs", exist_ok=True) # New directory for generated PDFs


LOGO_FILE_NAME = "polaris_digitech_logo.png"
LOGO_PATH = os.path.join(ICON_BASE_DIR, LOGO_FILE_NAME)

ABDULAHI_IMAGE_FILE_NAME = "abdulahi_image.png"
ABDULAHI_IMAGE_PATH = os.path.join(ICON_BASE_DIR, ABDULAHI_IMAGE_FILE_NAME)

# --- Define Approval Route Roles and simulate emails (Updated to fetch from users) ---
# These are the *stages* in the approval chain, mapped to department/grade levels
# The order here defines the sequence of approval for OPEX/CAPEX
APPROVAL_CHAIN = [
    {"role_name": "Admin Manager", "department": "Administration", "grade_level": "Manager"},
    {"role_name": "HR Manager", "department": "HR", "grade_level": "Manager"},
    {"role_name": "Finance Manager", "department": "Finance", "grade_level": "Manager"},
    {"role_name": "MD", "department": "Executive", "grade_level": "MD"} # MD is assumed to be in Executive department
]

# --- NEW: OPEX/CAPEX Expense Lines and Budgeted Amounts ---
EXPENSE_LINES_BUDGET = {
    "Office Repairs and Maintenance": 1000000.00,
    "Equipment Maintenance": 500000.00,
    "Regulatory Maintenance": 750000.00,
    "Electricity": 6000000.00,
    "Cleaning & Pest Control": 2500000.00,
    "Fleet Management": 5000000.00,
    "Subscriptions": 1000000.00,
    "Rent": 2500000.00,
    "Fuel and Lubrication": 4500000.00,
    "Plant & Machinery Maintenance": 450000.00,
    "Printing & Stationeries": 1200000.00,
    "Insurance": 7500000.00,
    "Internet Subscription": 2500000.00,
    "IT Equipment Maintenance": 5000000.00,
}

# Helper function to get an approver's full name based on department and grade level
def get_approver_name_by_criteria(users, department, grade_level):
    for user in users:
        profile = user.get('profile', {})
        if profile.get('department') == department and profile.get('grade_level') == grade_level:
            return profile.get('name')
    return None # Or raise an error if an approver is strictly required

# --- Data Loading/Saving Functions ---
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

def load_data(filename, default_value=None):
    if default_value is None:
        default_value = []
    try:
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            with open(filename, "r") as file:
                data = json.load(file)
                # Specific handling for users.json to ensure 'profile' and 'staff_id'
                if filename == USERS_FILE:
                    for user in data:
                        user.setdefault('profile', {})
                        user['profile'].setdefault('staff_id', 'N/A')
                        user['profile'].setdefault('name', user.get('username', 'Unknown User')) # Ensure name is present
                        user['profile'].setdefault('department', 'N/A')
                        user['profile'].setdefault('grade_level', 'N/A')
                        user['profile'].setdefault('email_address', user.get('username', 'N/A'))
                # Specific handling for leave/opex requests to ensure requester_staff_id and request_id
                elif filename in [LEAVE_REQUESTS_FILE, OPEX_CAPEX_REQUESTS_FILE]:
                    for req in data:
                        req.setdefault('request_id', str(uuid.uuid4())) # Ensure request_id exists
                        req.setdefault('requester_staff_id', 'N/A')
                        req.setdefault('requester_name', 'N/A')
                        req.setdefault('requester_department', 'N/A')
                        req.setdefault('request_type', 'N/A')
                        req.setdefault('item_description', 'N/A')
                        req.setdefault('expense_line', 'N/A')
                        req.setdefault('budgeted_amount', 0.0)
                        req.setdefault('material_cost', 0.0)
                        req.setdefault('labor_cost', 0.0)
                        req.setdefault('total_amount', 0.0)
                        req.setdefault('wht_percentage', 0.0)
                        req.setdefault('wht_amount', 0.0)
                        req.setdefault('net_amount_payable', 0.0)
                        req.setdefault('budget_balance', 0.0)
                        req.setdefault('justification', 'N/A')
                        req.setdefault('vendor_name', 'N/A')
                        req.setdefault('vendor_account_name', 'N/A')
                        req.setdefault('vendor_account_no', 'N/A')
                        req.setdefault('vendor_bank', 'N/A')
                        req.setdefault('document_path', None)
                        req.setdefault('submission_date', datetime.now().isoformat())
                        req.setdefault('current_approver_role', 'N/A') # Crucial for KeyError fix
                        req.setdefault('current_approval_stage', 0)
                        req.setdefault('final_status', 'Pending')
                        req.setdefault('approval_history', [])
                        # Ensure duration_days and request_date are set for leave requests
                        if filename == LEAVE_REQUESTS_FILE:
                            req.setdefault('duration_days', 0) # Default to 0, will be calculated on submission
                            req.setdefault('request_date', datetime.now().isoformat())
                # Specific handling for performance_goals to ensure all expected keys are present
                elif filename == PERFORMANCE_GOALS_FILE:
                    for goal in data:
                        goal.setdefault('goal_id', str(uuid.uuid4()))
                        goal.setdefault('staff_id', 'N/A')
                        goal.setdefault('goal_description', 'No description provided')
                        goal.setdefault('collaborating_department', 'N/A')
                        goal.setdefault('status', 'Not Started')
                        goal.setdefault('employee_remark_update', '')
                        goal.setdefault('start_date', datetime.now().isoformat().split('T')[0])
                        goal.setdefault('end_date', (datetime.now() + timedelta(days=365)).isoformat().split('T')[0])
                        goal.setdefault('duration', 'N/A')
                        goal.setdefault('weighting_percent', 0)
                        goal.setdefault('set_date', datetime.now().isoformat())
                        goal.setdefault('progress_updates', [])
                        goal.setdefault('self_rating', None)
                        goal.setdefault('line_manager_rating', None)
                # Specific handling for self_appraisals to ensure all expected keys are present
                elif filename == SELF_APPRAISALS_FILE:
                    for appraisal in data:
                        appraisal.setdefault('appraisal_id', str(uuid.uuid4()))
                        appraisal.setdefault('staff_id', 'N/A')
                        appraisal.setdefault('appraisal_period', str(datetime.now().year))
                        appraisal.setdefault('employee_data', {})
                        appraisal['employee_data'].setdefault('name', 'N/A')
                        appraisal['employee_data'].setdefault('designation', 'N/A')
                        appraisal['employee_data'].setdefault('department', 'N/A')
                        appraisal['employee_data'].setdefault('date', datetime.now().isoformat().split('T')[0])
                        appraisal.setdefault('key_status_ratings', {})
                        appraisal.setdefault('section_a_goals', [])
                        appraisal.setdefault('section_b_qualitative', {})
                        appraisal['section_b_qualitative'].setdefault('leadership_team_development', {'remark': '', 'self_rating': None, 'line_manager_rating': None})
                        appraisal['section_b_qualitative'].setdefault('coordinate_optimize_resources', {'remark': '', 'self_rating': None, 'line_manager_rating': None})
                        appraisal['section_b_qualitative'].setdefault('interpersonal', {'remark': '', 'self_rating': None, 'line_manager_rating': None})
                        appraisal.setdefault('training_recommendation', '')
                        appraisal.setdefault('hr_remark', '')
                        appraisal.setdefault('md_remark', '')
                # Specific handling for chat messages
                elif filename == CHAT_MESSAGES_FILE:
                    for msg in data:
                        msg.setdefault('message_id', str(uuid.uuid4()))
                        msg.setdefault('sender_staff_id', 'N/A')
                        msg.setdefault('receiver_staff_id', 'N/A')
                        msg.setdefault('timestamp', datetime.now().isoformat())
                        msg.setdefault('message', '')
                        msg.setdefault('read', False)
                # Specific handling for payroll
                elif filename == PAYROLL_FILE:
                    for payslip in data:
                        payslip.setdefault('payslip_id', str(uuid.uuid4()))
                        payslip.setdefault('staff_id', 'N/A')
                        payslip.setdefault('pay_period', 'N/A')
                        # Convert to float to prevent ValueError in formatting
                        # Remove commas before converting to float
                        gross_pay_str = str(payslip.get('gross_pay', 0.0)).replace(',', '')
                        deductions_str = str(payslip.get('deductions', 0.0)).replace(',', '')
                        net_pay_str = str(payslip.get('net_pay', 0.0)).replace(',', '')

                        payslip['gross_pay'] = float(gross_pay_str)
                        payslip['deductions'] = float(deductions_str)
                        payslip['net_pay'] = float(net_pay_str)
                        payslip.setdefault('pay_date', datetime.now().isoformat().split('T')[0])
                # Specific handling for HR policies
                elif filename == HR_POLICIES_FILE:
                    # Ensure each policy is a dictionary, not a string
                    cleaned_data = []
                    for policy_entry in data:
                        if isinstance(policy_entry, str): # Handle cases where policy might be a plain string
                            st.warning(f"Found string policy entry in {filename}: '{policy_entry}'. Skipping or converting.")
                            # You might choose to skip it, or try to convert it to a dict if it's a simple string
                            cleaned_data.append({
                                "policy_id": str(uuid.uuid4()),
                                "title": f"Malformed Policy ({str(uuid.uuid4())[:8]})",
                                "content": policy_entry,
                                "last_updated": datetime.now().isoformat().split('T')[0]
                            })
                        else:
                            policy_entry.setdefault('policy_id', str(uuid.uuid4()))
                            policy_entry.setdefault('title', 'N/A')
                            policy_entry.setdefault('content', 'N/A')
                            policy_entry.setdefault('last_updated', datetime.now().isoformat().split('T')[0])
                            cleaned_data.append(policy_entry)
                    data = cleaned_data # Update data with cleaned version
                # Specific handling for disciplinary records
                elif filename == DISCIPLINARY_RECORDS_FILE:
                    for record in data:
                        record.setdefault('record_id', str(uuid.uuid4()))
                        record.setdefault('staff_id', 'N/A')
                        record.setdefault('incident_date', datetime.now().isoformat().split('T')[0])
                        record.setdefault('incident_type', 'N/A')
                        record.setdefault('description', 'N/A')
                        record.setdefault('action_taken', 'N/A')
                        record.setdefault('status', 'Open')
                        record.setdefault('recorded_by', 'N/A')
                        record.setdefault('recorded_date', datetime.now().isoformat())
                # Specific handling for attendance records
                elif filename == ATTENDANCE_RECORDS_FILE:
                    for record in data:
                        record.setdefault('record_id', str(uuid.uuid4()))
                        record.setdefault('staff_id', 'N/A')
                        record.setdefault('date', datetime.now().isoformat().split('T')[0])
                        
                        # --- FIX for ValueError: Invalid isoformat string ---
                        # Ensure clock_in_time and clock_out_time are full ISO format strings
                        # If they are just time strings (e.g., "11:31:30"), prepend today's date.
                        
                        # Handle clock_in_time
                        if isinstance(record.get('clock_in_time'), str) and 'T' not in record['clock_in_time']:
                            try:
                                # Try to parse as time only, then combine with a dummy date (e.g., today's date)
                                time_obj = datetime.strptime(record['clock_in_time'], '%H:%M:%S').time()
                                # Use a fixed date (e.g., 2000-01-01) for time-only strings to ensure consistent isoformat
                                record['clock_in_time'] = datetime.combine(date(2000, 1, 1), time_obj).isoformat()
                            except ValueError:
                                record['clock_in_time'] = None # Fallback if even time parsing fails
                        elif not isinstance(record.get('clock_in_time'), str):
                            record['clock_in_time'] = None # Ensure it's None if not a string

                        # Handle clock_out_time
                        if isinstance(record.get('clock_out_time'), str) and 'T' not in record['clock_out_time']:
                            try:
                                time_obj = datetime.strptime(record['clock_out_time'], '%H:%M:%S').time()
                                record['clock_out_time'] = datetime.combine(date(2000, 1, 1), time_obj).isoformat()
                            except ValueError:
                                record['clock_out_time'] = None # Fallback if even time parsing fails
                        elif not isinstance(record.get('clock_out_time'), str):
                            record['clock_out_time'] = None # Ensure it's None if not a string
                        # --- END FIX ---

                        record.setdefault('duration_hours', 0.0)

                return data
        return default_value
    except json.JSONDecodeError:
        st.warning(f"Error decoding JSON from {filename}. File might be corrupted or empty. Resetting data.")
        return default_value
    except FileNotFoundError:
        return default_value

def save_data(data, filename):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4, cls=DateEncoder)

def save_uploaded_file(uploaded_file, destination_folder="uploaded_documents"):
    if uploaded_file is not None:
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        file_path = os.path.join(destination_folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None

# --- PDF Generation Function (New) ---
def generate_opex_capex_pdf(request_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "OPEX/CAPEX Requisition Summary", 0, 1, "C")
    pdf.ln(10)

    # Set font for content
    pdf.set_font("Arial", "", 10)
    line_height = 7 # Standard line height

    # Helper to safely get data with default
    def get_data(key, default='N/A'):
        return request_data.get(key, default)

    # Format currency
    def format_currency(amount):
        try:
            return f"NGN {float(amount):,.2f}"
        except (ValueError, TypeError):
            return f"NGN N/A (Invalid: {amount})"

    # Format date
    def format_date(date_str):
        if isinstance(date_str, str):
            try:
                return datetime.fromisoformat(date_str).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                return date_str # Return as is if not valid isoformat
        return date_str

    # Extract and format data
    requester_name = get_data('requester_name')
    requester_department = get_data('requester_department')
    request_type = get_data('request_type')
    item_description = get_data('item_description')
    expense_line = get_data('expense_line')
    total_amount = format_currency(get_data('total_amount'))
    net_amount_payable = format_currency(get_data('net_amount_payable'))
    justification = get_data('justification')
    vendor_name = get_data('vendor_name')
    vendor_account_name = get_data('vendor_account_name')
    vendor_account_no = get_data('vendor_account_no')
    vendor_bank = get_data('vendor_bank')

    # Print main details
    pdf.write(line_height, f"Requester: {requester_name} ({requester_department})")
    pdf.ln(line_height)
    pdf.write(line_height, f"Request Type: {request_type}")
    pdf.ln(line_height)
    # Item Description might be long, use multi_cell for it
    pdf.write(line_height, "Item Description: ")
    pdf.set_x(pdf.get_x()) # Set X to current position after "Item Description: "
    pdf.multi_cell(0, line_height, item_description, 0, 'L') # 0 for full width, L for left align
    
    pdf.write(line_height, f"Expense Line: {expense_line}")
    pdf.ln(line_height)
    pdf.write(line_height, f"Total Amount: {total_amount}")
    pdf.ln(line_height)
    pdf.write(line_height, f"Net Amount Payable: {net_amount_payable}")
    pdf.ln(line_height)
    # Justification might be long, use multi_cell for it
    pdf.write(line_height, "Justification: ")
    pdf.set_x(pdf.get_x()) # Set X to current position after "Justification: "
    pdf.multi_cell(0, line_height, justification, 0, 'L')

    pdf.write(line_height, f"Vendor: {vendor_name} (Account: {vendor_account_no}, Bank: {vendor_bank})")
    pdf.ln(line_height)
    pdf.ln(5) # Add some extra space before history

    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "Approval History:", 0, 1)
    pdf.set_font("Arial", "", 10)

    # Ensure enough horizontal space for multi_cell for history entries
    # The '0' in multi_cell(0, ...) means it will use the remaining width to the right margin.
    # We need to ensure the cursor is at the left margin before calling it.
    if request_data.get('approval_history'):
        for entry in request_data['approval_history']:
            approver_role = entry.get('approver_role', 'N/A')
            approver_name = entry.get('approver_name', 'N/A')
            approval_date = format_date(entry.get('date', 'N/A'))
            status = entry.get('status', 'N/A')
            comment = entry.get('comment', 'No comment.')
            
            history_text = f"- {approver_role} by {approver_name} on {approval_date}: {status}. Comment: {comment}"
            
            # Reset X position to left margin before each multi_cell to ensure full width is available
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, line_height, history_text, 0, 'L') # Use 0 for width to extend to right margin
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, line_height, "No approval history recorded.", 0, 'L')

    # Save the PDF
    pdf_filename = f"OPEX_CAPEX_Request_{request_data['request_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join("opex_capex_pdfs", pdf_filename)
    pdf.output(pdf_path)
    return pdf_path

# --- Initial Data Setup (Users, Policies, Beneficiaries) ---
def setup_initial_data():
    # Initial Users (Admin + 6 Staff Members)
    initial_users = [
        # Admin User (can act as MD and Admin Manager for initial setup if no other specific user)
        {
            "username": "abdul_bolaji@yahoo.com",
            "password": pbkdf2_sha256.hash("admin123"), # Hashed password
            "role": "admin", # This role grants access to admin functions
            "profile": { # Ensure staff_id is within profile
                "name": "Abdul Bolaji (Admin)",
                "staff_id": "ADM/2024/000", # Moved staff_id here
                "date_of_birth": "1980-01-01",
                "gender": "Male",
                "grade_level": "MD", # This user can act as MD approver
                "department": "Executive", # This user can act as MD approver, also Admin manager for the purpose of this demo
                "education_background": "MBA, Computer Science",
                "professional_experience": "15+ years in IT Management",
                "address": "123 Admin Lane, Lagos",
                "phone_number": "+2348011112222",
                "email_address": "abdul_bolaji@yahoo.com",
                "training_attended": [],
                "work_anniversary": "2010-09-01"
            }
        },
        # Staff Members (with generic password 123456)
        {
            "username": "ada_ama",
            "password": pbkdf2_sha256.hash("123456"),
            "role": "staff",
            "profile": { # Ensure staff_id is within profile
                "name": "Ada Ama",
                "staff_id": "POL/2024/001", # Moved staff_id here
                "date_of_birth": "1995-01-01",
                "gender": "Female", # Corrected from Male in table
                "grade_level": "Officer",
                "department": "Marketing",
                "education_background": "BSc. Marketing",
                "professional_experience": "5 years in digital marketing",
                "address": "456 Market St, Abuja",
                "phone_number": "+2348023456789",
                "email_address": "ada.ama@example.com",
                "training_attended": [],
                "work_anniversary": "2024-01-15"
            }
        },
        {
            "username": "udu_aka",
            "password": pbkdf2_sha256.hash("123456"),
            "role": "staff",
            "profile": { # Ensure staff_id is within profile
                "name": "Udu Aka",
                "staff_id": "POL/2024/002", # Moved staff_id here
                "date_of_birth": "2000-02-01",
                "gender": "Male",
                "grade_level": "Manager", # This user can act as Finance Manager approver
                "department": "Finance",
                "education_background": "ACA, B.Acc",
                "professional_experience": "8 years in financial management",
                "address": "789 Bank Rd, Lagos",
                "phone_number": "+2348034567890",
                "email_address": "udu.aka@example.com",
                "training_attended": [],
                "work_anniversary": "2024-03-01"
            }
        },
        {
            "username": "abdulahi_ibrahim",
            "password": pbkdf2_sha256.hash("123456"),
            "role": "staff",
            "profile": { # Ensure staff_id is within profile
                "name": "Abdulahi Ibrahim",
                "staff_id": "POL/2024/003", # Moved staff_id here
                "date_of_birth": "1998-03-03",
                "gender": "Male", # Corrected from Female
                "grade_level": "Manager", # This user can act as Admin Manager approver
                "department": "Administration",
                "education_background": "B.A. Public Admin",
                "professional_experience": "6 years in office administration",
                "address": "101 Admin Way, Port Harcourt",
                "phone_number": "+2348045678901",
                "email_address": "abdulahi.ibrahim@example.com",
                "training_attended": [],
                "work_anniversary": "2024-02-10"
            }
        },
        {
            "username": "addidas_puma",
            "password": pbkdf2_sha256.hash("123456"),
            "role": "staff",
            "profile": { # Ensure staff_id is within profile
                "name": "Addidas Puma",
                "staff_id": "POL/2024/004", # Moved staff_id here
                "date_of_birth": "1999-09-04",
                "gender": "Female", # Corrected from Male
                "grade_level": "Manager", # This user can act as HR Manager approver
                "department": "HR",
                "education_background": "MSc. Human Resources",
                "professional_experience": "7 years in HR operations",
                "address": "202 HR Lane, Kano",
                "phone_number": "+2348056789012",
                "email_address": "addidas.puma@example.com",
                "training_attended": [],
                "work_anniversary": "2023-07-20"
            }
        },
        {
            "username": "big_kola",
            "password": pbkdf2_sha256.hash("123456"),
            "role": "staff",
            "profile": { # Ensure staff_id is within profile
                "name": "Big Kola",
                "staff_id": "POL/2024/005", # Moved staff_id here
                "date_of_birth": "2001-06-13",
                "gender": "Female",
                "grade_level": "Officer",
                "department": "Operations", # Assuming 'CV' was a typo for a department, changed to Operations
                "education_background": "BEng. Civil Engineering",
                "professional_experience": "3 years in project management",
                "address": "303 Ops Drive, Ibadan",
                "phone_number": "+2348067890123",
                "email_address": "big.kola@example.com",
                "training_attended": [],
                "work_anniversary": "2022-04-05"
            }
        },
        {
            "username": "king_queen",
            "password": pbkdf2_sha256.hash("123456"),
            "role": "staff",
            "profile": { # Ensure staff_id is within profile
                "name": "King Queen",
                "staff_id": "POL/2024/006", # Moved staff_id here
                "date_of_birth": "2002-06-16",
                "gender": "Female",
                "grade_level": "Officer",
                "department": "IT", # Changed from Administration to IT
                "education_background": "BSc. Computer Science",
                "professional_experience": "2 years in IT support",
                "address": "404 Tech Road, Enugu",
                "phone_number": "+2348078901234",
                "email_address": "king.queen@example.com",
                "training_attended": [],
                "work_anniversary": "2023-11-01"
            }
        }
    ]

    initial_policies = [
        {
            "policy_id": str(uuid.uuid4()),
            "title": "Employee Code of Conduct",
            "content": """
            **1. Introduction**
            This Code of Conduct outlines the expected standards of behavior and professionalism for all employees of Polaris Digitech. Adherence to this code is mandatory and reflects our commitment to a respectful, productive, and ethical work environment.

            **2. Respect and Professionalism**
            Employees must treat colleagues, clients, partners, and the public with respect, courtesy, and fairness. Discrimination, harassment, or any form of offensive behavior based on race, gender, religion, age, disability, sexual orientation, or any other protected characteristic will not be tolerated. Professionalism should be maintained in all communications and interactions.

            **3. Integrity and Honesty**
            All business dealings must be conducted with the highest level of integrity and honesty. Employees must not engage in any form of fraud, theft, bribery, or corruption. Conflicts of interest must be disclosed and managed appropriately to ensure that personal interests do not interfere with the company's best interests.

            **4. Confidentiality**
            Employees are obligated to protect the confidential information of Polaris Digitech, its clients, and its partners. This includes, but is not limited to, trade secrets, financial data, client lists, and personal employee information. Confidential information should not be disclosed to unauthorized individuals or used for personal gain.

            **5. Workplace Safety and Health**
            Polaris Digitech is committed to providing a safe and healthy work environment. Employees must comply with all safety regulations and procedures, report any hazards or accidents promptly, and take reasonable care for their own safety and the safety of others.

            **6. Use of Company Property**
            Company property, including equipment, systems, and facilities, must be used responsibly and for legitimate business purposes only. Unauthorized use, damage, or theft of company property is strictly prohibited.

            **7. Compliance with Laws and Regulations**
            Employees must comply with all applicable laws, regulations, and company policies. This includes laws related to data privacy, anti-money laundering, environmental protection, and employment.

            **8. Social Media Policy**
            Employees should exercise caution and good judgment when using social media. Content that is discriminatory, harassing, defamatory, or that discloses confidential company information is prohibited. Personal opinions expressed on social media should not be attributed to Polaris Digitech.

            **9. Reporting Violations**
            Employees are encouraged to report any suspected violations of this Code of Conduct or other company policies to their manager, HR department, or through established reporting channels. Retaliation against employees who report concerns in good faith is strictly prohibited.

            **10. Consequences of Violation**
            Violations of this Code of Conduct may result in disciplinary action, up to and including termination of employment, and may also lead to legal action where applicable.
            """,
            "last_updated": "2024-01-01"
        },
        {
            "policy_id": str(uuid.uuid4()),
            "title": "Leave Policy",
            "content": """
            **1. Introduction**
            Polaris Digitech provides various types of leave to support employees' well-being and personal needs while ensuring business continuity. This policy outlines the guidelines for requesting and managing leave.

            **2. Types of Leave**
            * **Annual Leave:** All full-time employees are entitled to 20 working days of paid annual leave per year, accrued monthly. Leave must be approved in advance by the employee's line manager.
            * **Sick Leave:** Employees are entitled to up to 10 working days of paid sick leave per year. For absences exceeding 3 consecutive days, a medical certificate is required.
            * **Maternity Leave:** Female employees are entitled to 16 weeks of paid maternity leave.
            * **Paternity Leave:** Male employees are entitled to 2 weeks of paid paternity leave.
            * **Compassionate Leave:** Up to 5 working days of paid leave may be granted in cases of bereavement or serious family emergencies.
            * **Study Leave:** Discretionary leave may be granted for approved professional development or educational pursuits.

            **3. Leave Request Procedure**
            All leave requests (except for emergencies) must be submitted through the HR Portal at least two weeks in advance for annual leave, and as soon as practicable for other types of leave. Line managers must approve leave requests, considering operational requirements.

            **4. Leave Accrual and Carry-Over**
            Annual leave accrues from the employee's start date. A maximum of 5 unused annual leave days can be carried over to the next calendar year. Any leave exceeding this amount will be forfeited.

            **5. Unpaid Leave**
            In exceptional circumstances, unpaid leave may be granted at the discretion of management, following a formal request and justification.

            **6. Return to Work**
            Employees are expected to return to work on the scheduled date after leave. Any delays must be communicated to the line manager and HR department immediately.
            """,
            "last_updated": "2024-01-01"
        },
        {
            "policy_id": str(uuid.uuid4()),
            "title": "Expense Reimbursement Policy",
            "content": """
            **1. Purpose**
            This policy outlines the guidelines and procedures for employees to incur and claim reimbursement for business-related expenses while performing duties for Polaris Digitech.

            **2. General Principles**
            * All expenses must be legitimate, reasonable, and directly related to company business.
            * Employees must exercise good judgment and cost-consciousness when incurring expenses.
            * Original receipts or valid proof of payment are required for all reimbursement claims.
            * Claims must be submitted within 30 days of the expense being incurred.

            **3. Reimbursable Expenses**
            * **Travel:** Airfare (economy class), train fares, bus fares, taxi/ride-share (business-related), personal car mileage (at approved rates).
            * **Accommodation:** Reasonable hotel costs for business travel.
            * **Meals:** Reasonable meal expenses incurred while traveling or entertaining clients (with client names and business purpose noted).
            * **Office Supplies:** Purchase of necessary office supplies not available through standard company procurement.
            * **Training/Conferences:** Approved registration fees and associated travel/accommodation costs.

            **4. Non-Reimbursable Expenses**
            * Personal expenses (e.g., personal entertainment, toiletries, personal phone calls).
            * Alcoholic beverages (unless explicitly approved for client entertainment).
            * Traffic fines or parking tickets.
            * First-class travel or luxury accommodation without prior executive approval.

            **5. Approval Limits**
            Expenses exceeding certain thresholds may require pre-approval from a line manager or department head. Specific limits are detailed in the company's financial guidelines.

            **6. Reimbursement Procedure**
            * Complete an expense claim form via the HR Portal.
            * Attach all original receipts or scanned copies.
            * Submit the claim to your line manager for approval.
            * Approved claims will be processed by the Finance department and reimbursed via bank transfer.

            **7. Audit and Compliance**
            All expense claims are subject to audit. Any fraudulent or non-compliant claims will result in disciplinary action and potential legal consequences.
            """,
            "last_updated": "2024-01-01"
        }
    ]

    initial_payroll_data = [
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/001",
            "pay_period": "July 2024",
            "gross_pay": "350,000.00", # Changed to string to simulate original issue
            "deductions": "50,000.00", # Example: Tax, pension
            "net_pay": "300,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/002",
            "pay_period": "July 2024",
            "gross_pay": "700,000.00",
            "deductions": "120,000.00",
            "net_pay": "580,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/003",
            "pay_period": "July 2024",
            "gross_pay": "650,000.00",
            "deductions": "110,000.00",
            "net_pay": "540,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/004",
            "pay_period": "July 2024",
            "gross_pay": "600,000.00",
            "deductions": "100,000.00",
            "net_pay": "500,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/005",
            "pay_period": "July 2024",
            "gross_pay": "320,000.00",
            "deductions": "45,000.00",
            "net_pay": "275,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/006",
            "pay_period": "July 2024",
            "gross_pay": "300,000.00",
            "deductions": "40,000.00",
            "net_pay": "260,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "ADM/2024/000",
            "pay_period": "July 2024",
            "gross_pay": "1,500,000.00",
            "deductions": "300,000.00",
            "net_pay": "1,200,000.00",
            "pay_date": "2024-07-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/001",
            "pay_period": "June 2024",
            "gross_pay": "350,000.00",
            "deductions": "50,000.00",
            "net_pay": "300,000.00",
            "pay_date": "2024-06-25"
        },
        {
            "payslip_id": str(uuid.uuid4()),
            "staff_id": "POL/2024/002",
            "pay_period": "June 2024",
            "gross_pay": "700,000.00",
            "deductions": "120,000.00",
            "net_pay": "580,000.00",
            "pay_date": "2024-06-25"
        },
    ]


    if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
        save_data(initial_users, USERS_FILE)
    if not os.path.exists(HR_POLICIES_FILE) or os.path.getsize(HR_POLICIES_FILE) == 0:
        save_data(initial_policies, HR_POLICIES_FILE)
    if not os.path.exists(PAYROLL_FILE) or os.path.getsize(PAYROLL_FILE) == 0:
        save_data(initial_payroll_data, PAYROLL_FILE)
    # Ensure other files are initialized as empty lists if they don't exist
    for filename in [LEAVE_REQUESTS_FILE, OPEX_CAPEX_REQUESTS_FILE, PERFORMANCE_GOALS_FILE,
                     SELF_APPRAISALS_FILE, BENEFICIARIES_FILE, CHAT_MESSAGES_FILE,
                     ATTENDANCE_RECORDS_FILE, DISCIPLINARY_RECORDS_FILE]:
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            save_data([], filename) # Save empty list to initialize


# --- Authentication Functions ---
def authenticate_user(username, password):
    users = load_data(USERS_FILE)
    for user in users:
        if user["username"] == username and pbkdf2_sha256.verify(password, user["password"]):
            return user
    return None

def get_user_profile(staff_id):
    users = load_data(USERS_FILE)
    for user in users:
        if user.get('profile', {}).get('staff_id') == staff_id:
            return user.get('profile', {})
    return None

def get_user_by_staff_id(staff_id):
    users = load_data(USERS_FILE)
    for user in users:
        if user.get('profile', {}).get('staff_id') == staff_id:
            return user
    return None

def get_user_name_by_staff_id(staff_id):
    profile = get_user_profile(staff_id)
    return profile.get('name', 'Unknown User')

# --- Layout Components ---
def display_logo_and_title():
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=100)
        else:
            st.warning(f"Logo file not found at {LOGO_PATH}")
    with col2:
        st.title("Polaris Digitech HR Portal")
    st.markdown("---")

def display_dashboard():
    st.header(f"Welcome, {st.session_state.current_user['profile']['name']}!")
    st.write("This is your personalized HR dashboard.")

    # Fetch all data needed for dashboard insights
    users = load_data(USERS_FILE)
    leave_requests = load_data(LEAVE_REQUESTS_FILE)
    opex_capex_requests = load_data(OPEX_CAPEX_REQUESTS_FILE)
    performance_goals = load_data(PERFORMANCE_GOALS_FILE)

    st.subheader("Key HR Metrics")
    col1, col2, col3 = st.columns(3)

    # Metric 1: Total Employees
    total_employees = len(users)
    col1.metric("Total Employees", total_employees)

    # Metric 2: Pending Leave Requests (for HR Manager)
    pending_leave_requests_count = len([req for req in leave_requests if req.get('status') == 'Pending'])
    col2.metric("Pending Leave Requests", pending_leave_requests_count)

    # Metric 3: Pending OPEX/CAPEX Approvals (overall)
    pending_opex_capex_count = len([req for req in opex_capex_requests if req.get('final_status') == 'Pending'])
    col3.metric("Pending OPEX/CAPEX Approvals", pending_opex_capex_count)

    st.markdown("---")

    # Display pending approvals if the user is an approver
    current_user_profile = st.session_state.current_user.get('profile', {})
    current_user_department = current_user_profile.get('department')
    current_user_grade = current_user_profile.get('grade_level')

    is_approver = False
    approver_role_name = None
    for role_info in APPROVAL_CHAIN:
        if (role_info['department'] == current_user_department and
                role_info['grade_level'] == current_user_grade):
            is_approver = True
            approver_role_name = role_info['role_name']
            break

    if is_approver:
        st.subheader(f"Your Role: {approver_role_name}")
        
        # Ensure 'current_approver_role' exists for all requests before filtering
        pending_requests = [
            req for req in opex_capex_requests
            if req.get('current_approver_role') == approver_role_name and req.get('final_status') == 'Pending'
        ]

        if pending_requests:
            st.warning(f"You have {len(pending_requests)} pending OPEX/CAPEX requests to approve!")
            # Select relevant columns for display in dashboard summary
            df_pending = pd.DataFrame(pending_requests)
            st.dataframe(df_pending[['request_id', 'requester_name', 'request_type', 'total_amount', 'submission_date']])
            if st.button("Go to Approvals"):
                st.session_state.current_page = "manage_opex_capex_approvals"
                st.rerun()
        else:
            st.info("No pending OPEX/CAPEX requests for your approval at this time.")

    # Display pending leave requests if the user is an HR Manager
    if current_user_department == "HR" and current_user_grade == "Manager":
        pending_leave_requests = [
            req for req in leave_requests if req.get('status') == 'Pending'
        ]
        if pending_leave_requests:
            st.warning(f"You have {len(pending_leave_requests)} pending leave requests to review!")
            st.dataframe(pd.DataFrame(pending_leave_requests))
            if st.button("Go to Leave Approvals"):
                st.session_state.current_page = "admin_manage_leave"
                st.rerun()
        else:
            st.info("No pending leave requests for HR review at this time.")

    # Display unread chat messages
    unread_messages_count = get_unread_messages(st.session_state.current_user['profile']['staff_id'])
    if unread_messages_count > 0: # Check if count is greater than 0
        st.info(f"You have {unread_messages_count} unread chat messages! Go to Chat to view them.") # Removed len()
        if st.button("Go to Chat"):
            st.session_state.current_page = "chat"
            st.rerun()

    st.markdown("---")
    st.subheader("Company Overview Infographics")

    col_chart1, col_chart2 = st.columns(2)

    # Chart 1: Employee Distribution by Department
    if users:
        df_users = pd.DataFrame(users)
        df_users['Department'] = df_users['profile'].apply(lambda x: x.get('department', 'N/A'))
        dept_counts = df_users['Department'].value_counts().reset_index()
        dept_counts.columns = ['Department', 'Number of Employees']
        fig_dept = px.bar(dept_counts, x='Department', y='Number of Employees',
                          title='Employee Distribution by Department',
                          color='Department',
                          template='plotly_white')
        col_chart1.plotly_chart(fig_dept, use_container_width=True)
    else:
        col_chart1.info("No employee data to display department distribution.")

    # Chart 2: Employee Distribution by Gender
    if users:
        df_users = pd.DataFrame(users)
        df_users['Gender'] = df_users['profile'].apply(lambda x: x.get('gender', 'N/A'))
        gender_counts = df_users['Gender'].value_counts().reset_index()
        gender_counts.columns = ['Gender', 'Number of Employees']
        fig_gender = px.pie(gender_counts, values='Number of Employees', names='Gender',
                            title='Employee Distribution by Gender',
                            hole=.3)
        col_chart2.plotly_chart(fig_gender, use_container_width=True)
    else:
        col_chart2.info("No employee data to display gender distribution.")

    st.markdown("---")
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🌴 Request Leave", use_container_width=True):
            st.session_state.current_page = "request_leave"
            st.rerun()
    with col2:
        if st.button("💰 Request OPEX/CAPEX", use_container_width=True):
            st.session_state.current_page = "request_opex_capex"
            st.rerun()
    with col3:
        if st.button("🎯 Set Performance Goals", use_container_width=True):
            st.session_state.current_page = "set_performance_goals"
            st.rerun()
    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("📝 Submit Self-Appraisal", use_container_width=True):
            st.session_state.current_page = "submit_self_appraisal"
            st.rerun()
    with col5:
        if st.button("💸 View Payslip", use_container_width=True):
            st.session_state.current_page = "view_payslip"
            st.rerun()
    with col6:
        if st.button("📜 View Company Policy", use_container_width=True):
            st.session_state.current_page = "view_company_policy"
            st.rerun()


# --- User Management (Admin Only) ---
def admin_manage_users():
    st.header("Manage Users")
    users = load_data(USERS_FILE)

    if not users:
        st.info("No users found.")
        return

    st.subheader("Existing Users")
    # Manually extract and flatten profile data to avoid duplicate column names
    display_data = []
    for user in users:
        user_display = {
            "Username": user.get('username'),
            "Role": user.get('role').capitalize()
        }
        profile = user.get('profile', {})
        user_display["Staff ID"] = profile.get('staff_id')
        user_display["Full Name"] = profile.get('name')
        user_display["Department"] = profile.get('department')
        user_display["Grade Level"] = profile.get('grade_level')
        user_display["Email Address"] = profile.get('email_address')
        user_display["Date of Birth"] = profile.get('date_of_birth')
        user_display["Gender"] = profile.get('gender')
        user_display["Phone Number"] = profile.get('phone_number')
        user_display["Address"] = profile.get('address')
        user_display["Education Background"] = profile.get('education_background')
        user_display["Professional Experience"] = profile.get('professional_experience')
        user_display["Work Anniversary"] = profile.get('work_anniversary')
        display_data.append(user_display)

    df_users_display = pd.DataFrame(display_data)
    st.dataframe(df_users_display, use_container_width=True)

    st.subheader("Add New User")
    with st.form("add_user_form"):
        new_username = st.text_input("Username (Email)")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["staff", "admin"])

        st.markdown("---")
        st.subheader("User Profile Details")
        new_name = st.text_input("Full Name")
        new_staff_id = st.text_input("Staff ID")
        new_dob = st.date_input("Date of Birth", value=date(2000, 1, 1))
        new_gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        new_grade_level = st.text_input("Grade Level")
        new_department = st.text_input("Department")
        new_education = st.text_area("Education Background")
        new_experience = st.text_area("Professional Experience")
        new_address = st.text_area("Address")
        new_phone = st.text_input("Phone Number")
        new_email = st.text_input("Email Address")
        new_work_anniversary = st.date_input("Work Anniversary", value=date(datetime.now().year, 1, 1))

        add_user_submitted = st.form_submit_button("Add User")

        if add_user_submitted:
            if new_username and new_password and new_name and new_staff_id:
                if any(u['username'] == new_username for u in users):
                    st.error("Username already exists.")
                elif any(u.get('profile', {}).get('staff_id') == new_staff_id for u in users):
                    st.error("Staff ID already exists.")
                else:
                    new_user = {
                        "username": new_username,
                        "password": pbkdf2_sha256.hash(new_password),
                        "role": new_role,
                        "profile": {
                            "name": new_name,
                            "staff_id": new_staff_id,
                            "date_of_birth": new_dob.isoformat(),
                            "gender": new_gender,
                            "grade_level": new_grade_level,
                            "department": new_department,
                            "education_background": new_education,
                            "professional_experience": new_experience,
                            "address": new_address,
                            "phone_number": new_phone,
                            "email_address": new_email,
                            "training_attended": [],
                            "work_anniversary": new_work_anniversary.isoformat()
                        }
                    }
                    users.append(new_user)
                    save_data(users, USERS_FILE)
                    st.success(f"User '{new_username}' added successfully!")
                    st.rerun()
            else:
                st.error("Please fill in username, password, name, and staff ID.")

    st.subheader("Edit/Delete User")
    if users:
        user_to_edit_delete = st.selectbox("Select User by Username", [""] + [u['username'] for u in users])
        if user_to_edit_delete:
            user_data = next((u for u in users if u['username'] == user_to_edit_delete), None)
            if user_data:
                user_index = users.index(user_data)
                st.write(f"Editing user: {user_data['username']}")

                with st.form("edit_user_form"):
                    edited_name = st.text_input("Full Name", value=user_data['profile']['name'])
                    edited_staff_id = st.text_input("Staff ID", value=user_data['profile']['staff_id'], disabled=True) # Staff ID usually not editable
                    edited_dob = st.date_input("Date of Birth", value=date.fromisoformat(user_data['profile']['date_of_birth']))
                    edited_gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(user_data['profile']['gender']))
                    edited_grade_level = st.text_input("Grade Level", value=user_data['profile']['grade_level'])
                    edited_department = st.text_input("Department", value=user_data['profile']['department'])
                    edited_education = st.text_area("Education Background", value=user_data['profile']['education_background'])
                    edited_experience = st.text_area("Professional Experience", value=user_data['profile']['professional_experience'])
                    edited_address = st.text_area("Address", value=user_data['profile']['address'])
                    edited_phone = st.text_input("Phone Number", value=user_data['profile']['phone_number'])
                    edited_email = st.text_input("Email Address", value=user_data['profile']['email_address'])
                    edited_work_anniversary = st.date_input("Work Anniversary", value=date(datetime.now().year, 1, 1))
                    edited_role = st.selectbox("Role", ["staff", "admin"], index=["staff", "admin"].index(user_data['role']))

                    col_edit, col_delete = st.columns(2)
                    with col_edit:
                        edit_user_submitted = st.form_submit_button("Update User")
                    with col_delete:
                        delete_user_submitted = st.form_submit_button("Delete User")

                    if edit_user_submitted:
                        users[user_index]['profile']['name'] = edited_name
                        users[user_index]['profile']['date_of_birth'] = edited_dob.isoformat()
                        users[user_index]['profile']['gender'] = edited_gender
                        users[user_index]['profile']['grade_level'] = edited_grade_level
                        users[user_index]['profile']['department'] = edited_department
                        users[user_index]['profile']['education_background'] = edited_education
                        users[user_index]['profile']['professional_experience'] = edited_experience
                        users[user_index]['profile']['address'] = edited_address
                        users[user_index]['profile']['phone_number'] = edited_phone
                        users[user_index]['profile']['email_address'] = edited_email
                        users[user_index]['profile']['work_anniversary'] = edited_work_anniversary.isoformat()
                        users[user_index]['role'] = edited_role
                        save_data(users, USERS_FILE)
                        st.success(f"User '{user_to_edit_delete}' updated successfully!")
                        st.rerun()

                    if delete_user_submitted:
                        if st.session_state.current_user['username'] == user_to_edit_delete:
                            st.error("You cannot delete your own account while logged in.")
                        else:
                            del users[user_index]
                            save_data(users, USERS_FILE)
                            st.success(f"User '{user_to_edit_delete}' deleted successfully!")
                            st.rerun()
    else:
        st.info("No users to edit or delete.")

# --- Leave Management (Staff & Admin) ---
def request_leave():
    st.header("Request Leave")
    current_user_staff_id = st.session_state.current_user['profile']['staff_id']
    leave_requests = load_data(LEAVE_REQUESTS_FILE)

    st.subheader("Submit New Leave Request")
    with st.form("leave_request_form"):
        leave_type = st.selectbox("Leave Type", ["Annual Leave", "Sick Leave", "Maternity Leave", "Paternity Leave", "Compassionate Leave", "Study Leave", "Other"])
        start_date = st.date_input("Start Date", value=datetime.now().date())
        end_date = st.date_input("End Date", value=datetime.now().date() + timedelta(days=7))
        reason = st.text_area("Reason for Leave")
        supporting_document = st.file_uploader("Upload Supporting Document (Optional)", type=["pdf", "jpg", "png"])

        submitted = st.form_submit_button("Submit Request")

        if submitted:
            if start_date > end_date:
                st.error("End Date cannot be before Start Date.")
            else:
                duration_days = (end_date - start_date).days + 1
                doc_path = save_uploaded_file(supporting_document, "leave_documents")
                new_request = {
                    "request_id": str(uuid.uuid4()),
                    "requester_staff_id": current_user_staff_id,
                    "requester_name": st.session_state.current_user['profile']['name'],
                    "leave_type": leave_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "duration_days": duration_days,
                    "reason": reason,
                    "document_path": doc_path,
                    "status": "Pending", # Initial status
                    "request_date": datetime.now().isoformat()
                }
                leave_requests.append(new_request)
                save_data(leave_requests, LEAVE_REQUESTS_FILE)
                st.success("Leave request submitted successfully! Awaiting HR approval.")
                st.rerun()

    st.subheader("Your Leave Request History")
    user_requests = [req for req in leave_requests if req['requester_staff_id'] == current_user_staff_id]
    if user_requests:
        df_user_requests = pd.DataFrame(user_requests)
        # Display relevant columns
        # Ensure 'duration_days' and 'request_date' columns exist before displaying
        display_cols = ['request_id', 'leave_type', 'start_date', 'end_date', 'status']
        if 'duration_days' in df_user_requests.columns:
            display_cols.append('duration_days')
        if 'request_date' in df_user_requests.columns:
            display_cols.append('request_date')
        
        st.dataframe(df_user_requests[display_cols])
    else:
        st.info("You have not submitted any leave requests yet.")

def admin_manage_leave():
    st.header("Manage Leave Requests (HR)")
    leave_requests = load_data(LEAVE_REQUESTS_FILE)

    if not leave_requests:
        st.info("No leave requests submitted yet.")
        return

    st.subheader("All Leave Requests")
    df_leave_requests = pd.DataFrame(leave_requests)
    st.dataframe(df_leave_requests)

    st.subheader("Leave Request Statistics")
    if not df_leave_requests.empty:
        # Pie chart for Leave Type Distribution
        leave_type_counts = df_leave_requests['leave_type'].value_counts().reset_index()
        leave_type_counts.columns = ['Leave Type', 'Count']
        fig_leave_type = px.pie(leave_type_counts, values='Count', names='Leave Type',
                                title='Leave Type Distribution',
                                hole=.3)
        st.plotly_chart(fig_leave_type, use_container_width=True)

        # Bar chart for Total Leave Days by Type
        # Ensure 'duration_days' column exists before grouping
        if 'duration_days' in df_leave_requests.columns:
            leave_days_by_type = df_leave_requests.groupby('leave_type')['duration_days'].sum().reset_index()
            leave_days_by_type.columns = ['Leave Type', 'Total Days']
            fig_leave_days = px.bar(leave_days_by_type, x='Leave Type', y='Total Days',
                                    title='Total Leave Days Taken by Type',
                                    color='Leave Type',
                                    template='plotly_white')
            st.plotly_chart(fig_leave_days, use_container_width=True)
        else:
            st.info("Cannot display 'Total Leave Days Taken by Type' chart: 'duration_days' column not found in leave requests.")
    else:
        st.info("No leave data to generate statistics.")


    st.subheader("Approve/Reject Leave Requests")
    pending_requests = [req for req in leave_requests if req['status'] == 'Pending']
    if pending_requests:
        request_to_review = st.selectbox(
            "Select a pending request to review:",
            [""] + [f"{req['requester_name']} ({req['leave_type']} from {req['start_date']} to {req['end_date']})"
                    for req in pending_requests],
            format_func=lambda x: x if x else "Select a request"
        )

        if request_to_review:
            selected_request = next(req for req in pending_requests if f"{req['requester_name']} ({req['leave_type']} from {req['start_date']} to {req['end_date']})" == request_to_review)
            st.write(f"**Requester:** {selected_request['requester_name']}")
            st.write(f"**Staff ID:** {selected_request['requester_staff_id']}")
            st.write(f"**Leave Type:** {selected_request['leave_type']}")
            st.write(f"**Dates:** {selected_request['start_date']} to {selected_request['end_date']} ({selected_request.get('duration_days', 'N/A')} days)") # Use .get with default
            st.write(f"**Reason:** {selected_request['reason']}")
            if selected_request['document_path'] and os.path.exists(selected_request['document_path']):
                with open(selected_request['document_path'], "rb") as file:
                    btn = st.download_button(
                        label="Download Supporting Document",
                        data=file,
                        file_name=os.path.basename(selected_request['document_path']),
                        mime="application/octet-stream"
                    )
            else:
                st.info("No supporting document provided.")

            col_approve, col_reject = st.columns(2)
            with col_approve:
                if st.button("Approve Request"):
                    selected_request['status'] = 'Approved'
                    save_data(leave_requests, LEAVE_REQUESTS_FILE)
                    st.success("Leave request approved!")
                    st.rerun()
            with col_reject:
                if st.button("Reject Request"):
                    selected_request['status'] = 'Rejected'
                    save_data(leave_requests, LEAVE_REQUESTS_FILE)
                    st.warning("Leave request rejected.")
                    st.rerun()
    else:
        st.info("No pending leave requests to review.")

# --- OPEX/CAPEX Management (Staff & Admin/Approvers) ---
def request_opex_capex():
    st.header("OPEX/CAPEX Requisition")
    current_user_staff_id = st.session_state.current_user['profile']['staff_id']
    current_user_name = st.session_state.current_user['profile']['name']
    current_user_department = st.session_state.current_user['profile']['department']
    opex_capex_requests = load_data(OPEX_CAPEX_REQUESTS_FILE)
    users = load_data(USERS_FILE) # Needed to find approvers

    st.subheader("Submit New Requisition")
    with st.form("opex_capex_form"):
        request_type = st.selectbox("Request Type", ["OPEX (Operational Expenditure)", "CAPEX (Capital Expenditure)"])
        item_description = st.text_area("Item Description/Purpose")
        expense_line = st.selectbox("Expense Line", list(EXPENSE_LINES_BUDGET.keys()))
        material_cost = st.number_input("Material Cost (NGN)", min_value=0.0, format="%.2f")
        labor_cost = st.number_input("Labor Cost (NGN)", min_value=0.0, format="%.2f")
        justification = st.text_area("Justification")
        vendor_name = st.text_input("Vendor Name")
        vendor_account_name = st.text_input("Vendor Account Name")
        vendor_account_no = st.text_input("Vendor Account Number")
        vendor_bank = st.text_input("Vendor Bank")
        supporting_document = st.file_uploader("Upload Supporting Document (e.g., Invoice, Quote)", type=["pdf", "jpg", "png"])

        submitted = st.form_submit_button("Submit Requisition")

        if submitted:
            total_amount = material_cost + labor_cost
            wht_percentage = 0.05 # Example Withholding Tax
            wht_amount = total_amount * wht_percentage
            net_amount_payable = total_amount - wht_amount
            budgeted_amount = EXPENSE_LINES_BUDGET.get(expense_line, 0.0)
            budget_balance = budgeted_amount - total_amount # Simplified for now

            # Determine the first approver based on the chain
            first_approver_role = APPROVAL_CHAIN[0]['role_name']
            first_approver_dept = APPROVAL_CHAIN[0]['department']
            first_approver_grade = APPROVAL_CHAIN[0]['grade_level']
            first_approver_name = get_approver_name_by_criteria(users, first_approver_dept, first_approver_grade)

            if not first_approver_name:
                st.error(f"Error: Could not find an approver for the first stage ({first_approver_role}). Please contact HR.")
                return

            doc_path = save_uploaded_file(supporting_document, "opex_capex_documents")

            new_request = {
                "request_id": str(uuid.uuid4()),
                "requester_staff_id": current_user_staff_id,
                "requester_name": current_user_name,
                "requester_department": current_user_department,
                "request_type": request_type,
                "item_description": item_description,
                "expense_line": expense_line,
                "budgeted_amount": budgeted_amount,
                "material_cost": material_cost,
                "labor_cost": labor_cost,
                "total_amount": total_amount,
                "wht_percentage": wht_percentage,
                "wht_amount": wht_amount,
                "net_amount_payable": net_amount_payable,
                "budget_balance": budget_balance,
                "justification": justification,
                "vendor_name": vendor_name,
                "vendor_account_name": vendor_account_name,
                "vendor_account_no": vendor_account_no,
                "vendor_bank": vendor_bank,
                "document_path": doc_path,
                "submission_date": datetime.now().isoformat(),
                "current_approver_role": first_approver_role, # Role of the next person to approve
                "current_approval_stage": 0, # Index in APPROVAL_CHAIN
                "final_status": "Pending",
                "approval_history": []
            }
            opex_capex_requests.append(new_request)
            save_data(opex_capex_requests, OPEX_CAPEX_REQUESTS_FILE)
            st.success(f"OPEX/CAPEX request submitted successfully! Awaiting approval from {first_approver_name} ({first_approver_role}).")
            st.rerun()

    st.subheader("Your Requisition History")
    user_requests = [req for req in opex_capex_requests if req['requester_staff_id'] == current_user_staff_id]
    if user_requests:
        df_user_requests = pd.DataFrame(user_requests)
        st.dataframe(df_user_requests[['request_id', 'request_type', 'item_description', 'total_amount', 'final_status', 'current_approver_role', 'submission_date']])

        # Option to view details and PDF
        selected_request_id = st.selectbox("View details of a request:", [""] + [req['request_id'] for req in user_requests])
        if selected_request_id:
            selected_request = next(req for req in user_requests if req['request_id'] == selected_request_id)
            # Removed st.json(selected_request) as per user's feedback for scattering
            st.subheader(f"Details for Request ID: {selected_request_id}")
            # Manually display key details for better formatting
            st.write(f"**Requester Name:** {selected_request.get('requester_name')}")
            st.write(f"**Request Type:** {selected_request.get('request_type')}")
            st.write(f"**Item Description:** {selected_request.get('item_description')}")
            st.write(f"**Total Amount:** NGN {selected_request.get('total_amount', 0.0):,.2f}")
            st.write(f"**Net Amount Payable:** NGN {selected_request.get('net_amount_payable', 0.0):,.2f}")
            st.write(f"**Justification:** {selected_request.get('justification')}")
            st.write(f"**Vendor:** {selected_request.get('vendor_name')} (Account: {selected_request.get('vendor_account_no')}, Bank: {selected_request.get('vendor_bank')})")
            
            st.markdown("---")
            st.subheader("Approval History")
            if selected_request.get('approval_history'):
                for entry in selected_request['approval_history']:
                    st.write(f"- **{entry.get('approver_role')}** by {entry.get('approver_name')} on {datetime.fromisoformat(entry['date']).strftime('%Y-%m-%d %H:%M:%S') if entry.get('date') else 'N/A'}: **{entry.get('status')}**. Comment: {entry.get('comment', 'No comment.')}")
            else:
                st.info("No approval history for this request.")

            pdf_path = generate_opex_capex_pdf(selected_request)
            if pdf_path:
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="Download Requisition PDF",
                        data=pdf_file,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )
    else:
        st.info("You have not submitted any OPEX/CAPEX requisitions yet.")

def admin_manage_opex_capex_approvals():
    st.header("Manage OPEX/CAPEX Approvals")
    current_user_profile = st.session_state.current_user.get('profile', {})
    current_user_department = current_user_profile.get('department')
    current_user_grade = current_user_profile.get('grade_level')
    current_user_name = current_user_profile.get('name')
    opex_capex_requests = load_data(OPEX_CAPEX_REQUESTS_FILE)
    users = load_data(USERS_FILE)

    # Determine the current user's role in the approval chain
    current_approver_role_in_chain = None
    for role_info in APPROVAL_CHAIN:
        if (role_info['department'] == current_user_department and
                role_info['grade_level'] == current_user_grade):
            current_approver_role_in_chain = role_info['role_name']
            break

    if not current_approver_role_in_chain:
        st.warning("You are not configured as an approver in the OPEX/CAPEX approval chain.")
        return

    st.subheader(f"Requests Pending Your Approval ({current_approver_role_in_chain})")
    pending_for_this_approver = [
        req for req in opex_capex_requests
        if req.get('current_approver_role') == current_approver_role_in_chain and req.get('final_status') == 'Pending'
    ]

    if not pending_for_this_approver:
        st.info("No OPEX/CAPEX requests currently pending your approval.")
        return

    df_pending = pd.DataFrame(pending_for_this_approver)
    st.dataframe(df_pending[['request_id', 'requester_name', 'request_type', 'item_description', 'total_amount', 'submission_date']])

    request_to_review_id = st.selectbox(
        "Select Request ID to Review:",
        [""] + [req['request_id'] for req in pending_for_this_approver]
    )

    if request_to_review_id:
        selected_request = next(req for req in pending_for_this_approver if req['request_id'] == request_to_review_id)
        st.subheader(f"Reviewing Request: {selected_request['request_id']}")

        # Display full request details in a structured way
        st.write(f"**Requester Name:** {selected_request.get('requester_name')}")
        st.write(f"**Requester Staff ID:** {selected_request.get('requester_staff_id')}")
        st.write(f"**Requester Department:** {selected_request.get('requester_department')}")
        st.write(f"**Request Type:** {selected_request.get('request_type')}")
        st.write(f"**Item Description/Purpose:** {selected_request.get('item_description')}")
        st.write(f"**Expense Line:** {selected_request.get('expense_line')}")
        st.write(f"**Budgeted Amount:** NGN {selected_request.get('budgeted_amount', 0.0):,.2f}")
        st.write(f"**Material Cost:** NGN {selected_request.get('material_cost', 0.0):,.2f}")
        st.write(f"**Labor Cost:** NGN {selected_request.get('labor_cost', 0.0):,.2f}")
        st.write(f"**Total Amount:** NGN {selected_request.get('total_amount', 0.0):,.2f}")
        st.write(f"**WHT Percentage:** {selected_request.get('wht_percentage', 0.0)*100:.2f}%")
        st.write(f"**WHT Amount:** NGN {selected_request.get('wht_amount', 0.0):,.2f}")
        st.write(f"**Net Amount Payable:** NGN {selected_request.get('net_amount_payable', 0.0):,.2f}")
        st.write(f"**Budget Balance:** NGN {selected_request.get('budget_balance', 0.0):,.2f}")
        st.write(f"**Justification:** {selected_request.get('justification')}")
        st.write(f"**Vendor Name:** {selected_request.get('vendor_name')}")
        st.write(f"**Vendor Account Name:** {selected_request.get('vendor_account_name')}")
        st.write(f"**Vendor Account Number:** {selected_request.get('vendor_account_no')}")
        st.write(f"**Vendor Bank:** {selected_request.get('vendor_bank')}")
        st.write(f"**Submission Date:** {datetime.fromisoformat(selected_request['submission_date']).strftime('%Y-%m-%d %H:%M:%S') if selected_request.get('submission_date') else 'N/A'}")
        st.write(f"**Final Status:** {selected_request.get('final_status')}")
        st.write(f"**Current Approver Role:** {selected_request.get('current_approver_role')}")
        
        st.markdown("---")
        st.subheader("Approval History")
        if selected_request.get('approval_history'):
            for entry in selected_request['approval_history']:
                st.write(f"- **{entry.get('approver_role')}** by {entry.get('approver_name')} on {datetime.fromisoformat(entry['date']).strftime('%Y-%m-%d %H:%M:%S') if entry.get('date') else 'N/A'}: **{entry.get('status')}**. Comment: {entry.get('comment', 'No comment.')}")
        else:
            st.info("No approval history for this request.")


        # Download supporting document
        if selected_request['document_path'] and os.path.exists(selected_request['document_path']):
            with open(selected_request['document_path'], "rb") as file:
                btn = st.download_button(
                    label="Download Supporting Document",
                    data=file,
                    file_name=os.path.basename(selected_request['document_path']),
                    mime="application/octet-stream"
                )
        else:
            st.info("No supporting document provided for this request.")

        comment = st.text_area("Add a comment for this approval/rejection:")

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("Approve"):
                selected_request['approval_history'].append({
                    "approver_role": current_approver_role_in_chain,
                    "approver_name": current_user_name,
                    "date": datetime.now().isoformat(),
                    "status": "Approved",
                    "comment": comment
                })
                # Move to next stage or finalize
                next_stage_index = selected_request['current_approval_stage'] + 1
                if next_stage_index < len(APPROVAL_CHAIN):
                    next_approver_info = APPROVAL_CHAIN[next_stage_index]
                    selected_request['current_approver_role'] = next_approver_info['role_name']
                    selected_request['current_approval_stage'] = next_stage_index
                    st.success(f"Request {request_to_review_id} approved. Moving to {next_approver_info['role_name']} for review.")
                else:
                    selected_request['final_status'] = 'Approved'
                    selected_request['current_approver_role'] = 'Final Approval'
                    st.success(f"Request {request_to_review_id} fully approved!")

                save_data(opex_capex_requests, OPEX_CAPEX_REQUESTS_FILE)
                st.rerun()

        with col_reject:
            if st.button("Reject"):
                selected_request['approval_history'].append({
                    "approver_role": current_approver_role_in_chain,
                    "approver_name": current_user_name,
                    "date": datetime.now().isoformat(),
                    "status": "Rejected",
                    "comment": comment
                })
                selected_request['final_status'] = 'Rejected'
                selected_request['current_approver_role'] = 'Rejected'
                save_data(opex_capex_requests, OPEX_CAPEX_REQUESTS_FILE)
                st.warning(f"Request {request_to_review_id} rejected.")
                st.rerun()

    st.subheader("All OPEX/CAPEX Requests")
    if opex_capex_requests:
        df_all_requests = pd.DataFrame(opex_capex_requests)
        st.dataframe(df_all_requests)
    else:
        st.info("No OPEX/CAPEX requests have been submitted yet.")

# --- Performance Goals (Staff & Admin) ---
def manage_performance_goals():
    st.header("Manage Performance Goals")
    current_user_staff_id = st.session_state.current_user['profile']['staff_id']
    performance_goals = load_data(PERFORMANCE_GOALS_FILE)

    st.subheader("Set New Goal")
    with st.form("set_goal_form"):
        goal_description = st.text_area("Goal Description")
        collaborating_department = st.text_input("Collaborating Department (if any)")
        # Added "Pending Review" to status options for consistency
        status = st.selectbox("Current Status", ["Not Started", "In Progress", "On Hold", "Complete", "Pending Review"])
        employee_remark_update = st.text_area("Employee Remark/Update")
        start_date_input = st.date_input("Start Date", value=datetime.now().date())
        end_date_input = st.date_input("End Date", value=datetime.now().date() + timedelta(days=90))
        weighting_percent = st.number_input("Weighting (%)", min_value=0, max_value=100, value=0)

        submitted = st.form_submit_button("Set Goal")

        if submitted:
            if start_date_input > end_date_input:
                st.error("End Date cannot be before Start Date.")
            else:
                duration = (end_date_input - start_date_input).days
                new_goal = {
                    "goal_id": str(uuid.uuid4()),
                    "staff_id": current_user_staff_id,
                    "goal_description": goal_description,
                    "collaborating_department": collaborating_department,
                    "status": status,
                    "employee_remark_update": employee_remark_update,
                    "start_date": start_date_input.isoformat(),
                    "end_date": end_date_input.isoformat(),
                    "duration": f"{duration} days",
                    "weighting_percent": weighting_percent,
                    "set_date": datetime.now().isoformat(),
                    "progress_updates": [],
                    "self_rating": None, # Initialize for appraisal
                    "line_manager_rating": None # Initialize for appraisal
                }
                performance_goals.append(new_goal)
                save_data(performance_goals, PERFORMANCE_GOALS_FILE)
                st.success("Performance goal set successfully!")
                st.rerun()

    st.subheader("Your Current Goals")
    user_goals = [goal for goal in performance_goals if goal['staff_id'] == current_user_staff_id]
    if user_goals:
        # Create a DataFrame for display
        df_goals = pd.DataFrame(user_goals)
        # Select and reorder columns as per user's request
        display_columns = [
            "goal_description", "collaborating_department", "status",
            "employee_remark_update", "start_date", "end_date", "duration", "weighting_percent"
        ]
        # Add S/N
        df_goals_display = df_goals[display_columns].copy()
        df_goals_display.insert(0, 'S/N', range(1, 1 + len(df_goals_display)))
        df_goals_display.columns = [
            "S/N", "Goals", "Collaborating Department", "Status",
            "Employee Remark/Update", "Start Date", "End Date", "Duration", "Weighting (%)"
        ]
        st.dataframe(df_goals_display, use_container_width=True)

        st.subheader("Update Existing Goal")
        goal_options = {goal['goal_description']: goal['goal_id'] for goal in user_goals}
        selected_goal_desc = st.selectbox("Select Goal to Update:", [""] + list(goal_options.keys()))

        if selected_goal_desc:
            selected_goal_id = goal_options[selected_goal_desc]
            selected_goal = next(goal for goal in performance_goals if goal['goal_id'] == selected_goal_id)
            goal_index = performance_goals.index(selected_goal)

            with st.form("update_goal_form"):
                updated_goal_description = st.text_area("Goal Description", value=selected_goal['goal_description'])
                updated_collaborating_department = st.text_input("Collaborating Department", value=selected_goal['collaborating_department'])
                # Added "Pending Review" to status options for consistency
                updated_status = st.selectbox("Current Status", ["Not Started", "In Progress", "On Hold", "Complete", "Pending Review"], index=["Not Started", "In Progress", "On Hold", "Complete", "Pending Review"].index(selected_goal['status']))
                updated_employee_remark_update = st.text_area("Employee Remark/Update", value=selected_goal['employee_remark_update'])
                updated_start_date = st.date_input("Start Date", value=date.fromisoformat(selected_goal['start_date']))
                updated_end_date = st.date_input("End Date", value=date.fromisoformat(selected_goal['end_date']))
                updated_weighting_percent = st.number_input("Weighting (%)", min_value=0, max_value=100, value=selected_goal['weighting_percent'])

                col_update, col_delete = st.columns(2)
                with col_update:
                    update_submitted = st.form_submit_button("Update Goal")
                with col_delete:
                    delete_submitted = st.form_submit_button("Delete Goal")

                if update_submitted:
                    if updated_start_date > updated_end_date:
                        st.error("End Date cannot be before Start Date.")
                    else:
                        duration = (updated_end_date - updated_start_date).days
                        performance_goals[goal_index]['goal_description'] = updated_goal_description
                        performance_goals[goal_index]['collaborating_department'] = updated_collaborating_department
                        performance_goals[goal_index]['status'] = updated_status
                        performance_goals[goal_index]['employee_remark_update'] = updated_employee_remark_update
                        performance_goals[goal_index]['start_date'] = updated_start_date.isoformat()
                        performance_goals[goal_index]['end_date'] = updated_end_date.isoformat()
                        performance_goals[goal_index]['duration'] = f"{duration} days"
                        performance_goals[goal_index]['weighting_percent'] = updated_weighting_percent
                        save_data(performance_goals, PERFORMANCE_GOALS_FILE)
                        st.success("Goal updated successfully!")
                        st.rerun()

                if delete_submitted:
                    del performance_goals[goal_index]
                    save_data(performance_goals, PERFORMANCE_GOALS_FILE)
                    st.success("Goal deleted successfully!")
                    st.rerun()
    else:
        st.info("You have not set any performance goals yet.")

def admin_view_performance_goals():
    st.header("View All Performance Goals (Admin/HR)")
    performance_goals = load_data(PERFORMANCE_GOALS_FILE)
    users = load_data(USERS_FILE)
    staff_id_to_name = {user['profile']['staff_id']: user['profile']['name'] for user in users}

    if not performance_goals:
        st.info("No performance goals have been set yet.")
        return

    df_goals = pd.DataFrame(performance_goals)
    df_goals['Employee Name'] = df_goals['staff_id'].map(staff_id_to_name)

    st.subheader("Performance Goal Statistics")
    if not df_goals.empty:
        # Pie chart for Goal Status Distribution
        status_counts = df_goals['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.pie(status_counts, values='Count', names='Status',
                            title='Overall Goal Status Distribution',
                            hole=.3)
        st.plotly_chart(fig_status, use_container_width=True)

        # Bar chart for Average Self-Rating by Department
        df_goals_with_dept = df_goals.copy()
        # Fix: Safely get department, handling cases where get_user_profile might return None
        df_goals_with_dept['Department'] = df_goals_with_dept['staff_id'].apply(
            lambda x: get_user_profile(x).get('department', 'N/A') if get_user_profile(x) else 'N/A'
        )
        
        # Filter out rows where self_rating is None before calculating mean
        df_rated_goals = df_goals_with_dept.dropna(subset=['self_rating'])
        if not df_rated_goals.empty:
            avg_self_rating = df_rated_goals.groupby('Department')['self_rating'].mean().reset_index()
            fig_self_rating = px.bar(avg_self_rating, x='Department', y='self_rating',
                                    title='Average Self-Rating by Department',
                                    labels={'self_rating': 'Average Rating (1-5)'},
                                    color='Department',
                                    template='plotly_white')
            st.plotly_chart(fig_self_rating, use_container_width=True)
        else:
            st.info("No self-ratings available to display average self-rating by department.")

        # Bar chart for Average Line Manager's Rating by Department
        df_lm_rated_goals = df_goals_with_dept.dropna(subset=['line_manager_rating'])
        if not df_lm_rated_goals.empty:
            avg_lm_rating = df_lm_rated_goals.groupby('Department')['line_manager_rating'].mean().reset_index()
            fig_lm_rating = px.bar(avg_lm_rating, x='Department', y='line_manager_rating',
                                   title='Average Line Manager\'s Rating by Department',
                                   labels={'line_manager_rating': 'Average Rating (1-5)'},
                                   color='Department',
                                   template='plotly_white')
            st.plotly_chart(fig_lm_rating, use_container_width=True)
        else:
            st.info("No line manager ratings available to display average line manager's rating by department.")
    else:
        st.info("No performance goal data to generate statistics.")


    st.subheader("All Performance Goals Table")
    # Reorder columns for display
    display_columns = [
        "Employee Name", "goal_description", "collaborating_department", "status",
        "employee_remark_update", "start_date", "end_date", "duration", "weighting_percent",
        "self_rating", "line_manager_rating"
    ]
    df_goals_display = df_goals[display_columns].copy()
    df_goals_display.columns = [
        "Employee Name", "Goals", "Collaborating Department", "Status",
        "Employee Remark/Update", "Start Date", "End Date", "Duration", "Weighting (%)",
        "Self Rating", "Line Manager's Rating"
    ]
    st.dataframe(df_goals_display, use_container_width=True)

    st.subheader("Filter Goals")
    all_departments = sorted(list(set(user['profile']['department'] for user in users if 'profile' in user and 'department' in user['profile'])))
    selected_department = st.selectbox("Filter by Department:", ["All"] + all_departments)

    if selected_department != "All":
        filtered_staff_ids = [user['profile']['staff_id'] for user in users if user.get('profile', {}).get('department') == selected_department]
        df_filtered_goals = df_goals_display[df_goals_display['Employee Name'].isin([staff_id_to_name.get(sid) for sid in filtered_staff_ids])]
        st.dataframe(df_filtered_goals, use_container_width=True)
    else:
        st.dataframe(df_goals_display, use_container_width=True)

# --- Self-Appraisal (Staff & Admin/Manager) ---
def submit_self_appraisal():
    st.header("Submit Your Self-Appraisal")
    current_user = st.session_state.current_user
    current_user_staff_id = current_user['profile']['staff_id']
    current_user_name = current_user['profile']['name']
    current_user_designation = current_user['profile']['grade_level'] # Using grade_level as designation
    current_user_department = current_user['profile']['department']

    appraisals = load_data(SELF_APPRAISALS_FILE)
    performance_goals = load_data(PERFORMANCE_GOALS_FILE)

    # Find existing appraisal for the current user and period, or create a new one
    current_year = str(datetime.now().year)
    user_appraisal = next((app for app in appraisals if app['staff_id'] == current_user_staff_id and app['appraisal_period'] == current_year), None)

    if user_appraisal is None:
        user_appraisal = {
            "appraisal_id": str(uuid.uuid4()),
            "staff_id": current_user_staff_id,
            "appraisal_period": current_year,
            "employee_data": {
                "name": current_user_name,
                "designation": current_user_designation,
                "department": current_user_department,
                "date": datetime.now().isoformat().split('T')[0]
            },
            "key_status_ratings": {
                "Not Started": 0, "In Progress": 0, "On Hold": 0, "Complete": 0,
                "Exceeds Expectation": 5, "Meet Expectations": 4, "Average": 3,
                "Requires Improvement": 2, "Unsatisfactory": 1
            },
            "section_a_goals": [],
            "section_b_qualitative": {
                "leadership_team_development": {"remark": "", "self_rating": None, "line_manager_rating": None},
                "coordinate_optimize_resources": {"remark": "", "self_rating": None, "line_manager_rating": None},
                "interpersonal": {"remark": "", "self_rating": None, "line_manager_rating": None}
            },
            "training_recommendation": "",
            "hr_remark": "",
            "md_remark": ""
        }
        appraisals.append(user_appraisal) # Add to list if new

    st.markdown("---")
    st.markdown("### Instruction:")
    st.markdown("The goals agreed on at the beginning of the year which are specific, measurable, achievable, time-bound and relevant should be written in the goals' column. It can be distributed and assigned weights based on the value of the goal. Section A totals 70% while Section B totals 30% to make a sum of 100%. The remark column would state the achievements. Where applicable, date of commencement and when the goal is completed to be stated in the start and end date column. Scores should be filled in the appropriate column.")
    st.markdown("---")

    col_emp_data, col_ratings_key = st.columns([1, 1])

    with col_emp_data:
        st.subheader("Employee Data")
        st.write(f"**Employee Name:** {user_appraisal['employee_data']['name']}")
        st.write(f"**Designation:** {user_appraisal['employee_data']['designation']}")
        st.write(f"**Department:** {user_appraisal['employee_data']['department']}")
        st.write(f"**Date:** {user_appraisal['employee_data']['date']}")

    with col_ratings_key:
        st.subheader("Key Status & Ratings")
        ratings_data = {
            "POINTS": [5, 4, 3, 2, 1],
            "DESCRIPTION": ["Exceeds Expectation", "Meet Expectations", "Average", "Requires Improvement", "Unsatisfactory"],
            "RATINGS": ["100% And Above", "80 - 99%", "60 - 79%", "40 - 59%", "0 - 39%"]
        }
        df_ratings = pd.DataFrame(ratings_data)
        st.dataframe(df_ratings, hide_index=True)

    st.markdown("---")
    st.subheader("SECTION A: Performance Goals (70%)")

    # Get user's performance goals to pre-populate Section A
    user_performance_goals = [goal for goal in performance_goals if goal['staff_id'] == current_user_staff_id]

    # Initialize section_a_goals in appraisal with current performance goals
    # This ensures that goals set previously are reflected and can be appraised
    user_appraisal['section_a_goals'] = []
    for goal in user_performance_goals:
        appraisal_goal = next((g for g in user_appraisal['section_a_goals'] if g.get('goal_id') == goal['goal_id']), None)
        if not appraisal_goal:
            # Add new goals from performance_goals to appraisal if not already there
            user_appraisal['section_a_goals'].append({
                "goal_id": goal['goal_id'],
                "goal_description": goal['goal_description'],
                "collaborating_department": goal['collaborating_department'],
                "status": goal['status'],
                "employee_remark_update": goal['employee_remark_update'],
                "start_date": goal['start_date'],
                "end_date": goal['end_date'],
                "duration": goal['duration'],
                "weighting_percent": goal['weighting_percent'],
                "self_rating": goal['self_rating'], # Use existing self_rating from goal if available
                "line_manager_rating": goal['line_manager_rating'] # Use existing line_manager_rating from goal if available
            })

    # Display and allow editing for Section A goals
    st.write("Please review and update your goals and self-ratings:")
    for i, goal in enumerate(user_appraisal['section_a_goals']):
        st.markdown(f"**Goal {i+1}:**")
        goal['goal_description'] = st.text_area(f"Goals {i+1}", value=goal['goal_description'], key=f"goal_desc_{i}")
        goal['collaborating_department'] = st.text_input(f"Collaborating Department {i+1}", value=goal['collaborating_department'], key=f"collab_dept_{i}")
        
        # Ensure 'status' value from loaded data is in the selectbox options
        status_options = ["Not Started", "In Progress", "On Hold", "Complete", "Pending Review"]
        current_status_index = status_options.index(goal['status']) if goal['status'] in status_options else 0
        goal['status'] = st.selectbox(f"Status {i+1}", status_options, index=current_status_index, key=f"status_{i}")
        
        goal['employee_remark_update'] = st.text_area(f"Employee Remark/Update {i+1}", value=goal['employee_remark_update'], key=f"remark_{i}")
        
        # Convert date strings to date objects for date_input
        start_date_val = date.fromisoformat(goal['start_date']) if isinstance(goal['start_date'], str) else goal['start_date']
        end_date_val = date.fromisoformat(goal['end_date']) if isinstance(goal['end_date'], str) else goal['end_date']

        goal['start_date'] = st.date_input(f"Start Date {i+1}", value=start_date_val, key=f"start_date_{i}").isoformat()
        goal['end_date'] = st.date_input(f"End Date {i+1}", value=end_date_val, key=f"end_date_{i}").isoformat()
        
        # Recalculate duration
        try:
            duration_days = (date.fromisoformat(goal['end_date']) - date.fromisoformat(goal['start_date'])).days + 1
            goal['duration'] = f"{duration_days} days"
        except (ValueError, TypeError):
            goal['duration'] = "N/A" # Handle invalid date formats

        goal['weighting_percent'] = st.number_input(f"Weighting (%) {i+1}", min_value=0, max_value=100, value=goal['weighting_percent'], key=f"weighting_{i}")
        
        # Self Rating input
        current_self_rating = goal['self_rating'] if goal['self_rating'] is not None else 0
        goal['self_rating'] = st.slider(f"Self Rating (1-5) {i+1}", min_value=1, max_value=5, value=current_self_rating, key=f"self_rating_{i}")
        
        # Line Manager's Rating (read-only for employee, editable by manager)
        current_line_manager_rating = goal['line_manager_rating'] if goal['line_manager_rating'] is not None else 0
        st.slider(f"Line Manager's Rating (1-5) {i+1}", min_value=1, max_value=5, value=current_line_manager_rating, disabled=True, key=f"lm_rating_display_{i}")
        
        st.markdown("---")

    # Add button for more goals (if needed, though goals should ideally come from performance goals)
    # For now, we'll assume goals are primarily managed in "Set Performance Goals"
    # If users need to add ad-hoc goals during appraisal, this logic would need to be expanded.

    st.subheader("SECTION B: Qualitative Assessment (30%)")
    st.write("Please provide your remarks and self-ratings for the following areas:")

    # Leadership & Team Development
    st.markdown("**Leadership & Team Development**")
    user_appraisal['section_b_qualitative']['leadership_team_development']['remark'] = st.text_area(
        "Remark on Leadership & Team Development:",
        value=user_appraisal['section_b_qualitative']['leadership_team_development']['remark'],
        key="leadership_remark"
    )
    current_b1_self_rating = user_appraisal['section_b_qualitative']['leadership_team_development']['self_rating'] if user_appraisal['section_b_qualitative']['leadership_team_development']['self_rating'] is not None else 0
    user_appraisal['section_b_qualitative']['leadership_team_development']['self_rating'] = st.slider(
        "Self Rating (1-5) for Leadership & Team Development:",
        min_value=1, max_value=5, value=current_b1_self_rating, key="leadership_self_rating"
    )
    current_b1_lm_rating = user_appraisal['section_b_qualitative']['leadership_team_development']['line_manager_rating'] if user_appraisal['section_b_qualitative']['leadership_team_development']['line_manager_rating'] is not None else 0
    st.slider(
        "Line Manager's Rating (1-5) for Leadership & Team Development:",
        min_value=1, max_value=5, value=current_b1_lm_rating, disabled=True, key="leadership_lm_rating_display"
    )
    st.markdown("---")

    # Coordinate and Optimize Resources
    st.markdown("**Coordinate and Optimize the Use of Resources**")
    user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['remark'] = st.text_area(
        "Remark on Resource Coordination:",
        value=user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['remark'],
        key="resources_remark"
    )
    current_b2_self_rating = user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['self_rating'] if user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['self_rating'] is not None else 0
    user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['self_rating'] = st.slider(
        "Self Rating (1-5) for Resource Coordination:",
        min_value=1, max_value=5, value=current_b2_self_rating, key="resources_self_rating"
    )
    current_b2_lm_rating = user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['line_manager_rating'] if user_appraisal['section_b_qualitative']['coordinate_optimize_resources']['line_manager_rating'] is not None else 0
    st.slider(
        "Line Manager's Rating (1-5) for Resource Coordination:",
        min_value=1, max_value=5, value=current_b2_lm_rating, disabled=True, key="resources_lm_rating_display"
    )
    st.markdown("---")

    # Interpersonal
    st.markdown("**Interpersonal**")
    user_appraisal['section_b_qualitative']['interpersonal']['remark'] = st.text_area(
        "Remark on Interpersonal Skills:",
        value=user_appraisal['section_b_qualitative']['interpersonal']['remark'],
        key="interpersonal_remark"
    )
    current_b3_self_rating = user_appraisal['section_b_qualitative']['interpersonal']['self_rating'] if user_appraisal['section_b_qualitative']['interpersonal']['self_rating'] is not None else 0
    user_appraisal['section_b_qualitative']['interpersonal']['self_rating'] = st.slider(
        "Self Rating (1-5) for Interpersonal Skills:",
        min_value=1, max_value=5, value=current_b3_self_rating, key="interpersonal_self_rating"
    )
    current_b3_lm_rating = user_appraisal['section_b_qualitative']['interpersonal']['line_manager_rating'] if user_appraisal['section_b_qualitative']['interpersonal']['line_manager_rating'] is not None else 0
    st.slider(
        "Line Manager's Rating (1-5) for Interpersonal Skills:",
        min_value=1, max_value=5, value=current_b3_lm_rating, disabled=True, key="interpersonal_lm_rating_display"
    )
    st.markdown("---")

    st.subheader("Training Recommendation")
    user_appraisal['training_recommendation'] = st.text_area(
        "Training Recommendation:",
        value=user_appraisal['training_recommendation'],
        key="training_recommendation"
    )
    st.markdown("---")

    st.subheader("HR's Remark")
    st.text_area("HR's Remark:", value=user_appraisal['hr_remark'], disabled=True, key="hr_remark_display")
    st.markdown("---")

    st.subheader("MD's Remark")
    st.text_area("MD's Remark:", value=user_appraisal['md_remark'], disabled=True, key="md_remark_display")
    st.markdown("---")

    if st.button("Save Self-Appraisal"):
        # Update the original performance_goals list with the self-ratings from appraisal
        for app_goal in user_appraisal['section_a_goals']:
            for i, p_goal in enumerate(performance_goals):
                if p_goal.get('goal_id') == app_goal.get('goal_id'):
                    performance_goals[i]['self_rating'] = app_goal['self_rating']
                    performance_goals[i]['employee_remark_update'] = app_goal['employee_remark_update'] # Also update remark
                    performance_goals[i]['status'] = app_goal['status'] # Also update status
                    break
        save_data(performance_goals, PERFORMANCE_GOALS_FILE) # Save updated goals

        # Find the index of the current appraisal in the list to update it
        try:
            idx = next(i for i, app in enumerate(appraisals) if app['appraisal_id'] == user_appraisal['appraisal_id'])
            appraisals[idx] = user_appraisal
        except StopIteration:
            # This case should ideally not happen if user_appraisal was found or appended
            st.error("Error: Could not find appraisal to update. Please refresh.")
            return

        save_data(appraisals, SELF_APPRAISALS_FILE)
        st.success("Self-Appraisal saved successfully!")
        st.rerun()


def admin_manage_appraisals():
    st.header("Manage Employee Appraisals (HR/Manager/MD)")
    appraisals = load_data(SELF_APPRAISALS_FILE)
    users = load_data(USERS_FILE)
    staff_id_to_name = {user['profile']['staff_id']: user['profile']['name'] for user in users}

    if not appraisals:
        st.info("No appraisals have been submitted yet.")
        return

    # Filter appraisals by current year for easier management
    current_year = str(datetime.now().year)
    current_year_appraisals = [app for app in appraisals if app['appraisal_period'] == current_year]

    if not current_year_appraisals:
        st.info(f"No appraisals submitted for the year {current_year}.")
        return

    # Select an employee's appraisal to review
    appraisal_options = {
        f"{staff_id_to_name.get(app['staff_id'], 'Unknown')} ({app['staff_id']}) - {app['appraisal_period']}": app['appraisal_id']
        for app in current_year_appraisals
    }
    selected_appraisal_key = st.selectbox("Select an employee's appraisal to review:", [""] + list(appraisal_options.keys()))

    if selected_appraisal_key:
        selected_appraisal_id = appraisal_options[selected_appraisal_key]
        selected_appraisal = next(app for app in appraisals if app['appraisal_id'] == selected_appraisal_id)
        appraisal_index = appraisals.index(selected_appraisal)

        st.subheader(f"Reviewing Appraisal for {selected_appraisal['employee_data']['name']}")

        # Display Employee Data
        st.markdown("### Employee Data")
        st.write(f"**Employee Name:** {selected_appraisal['employee_data']['name']}")
        st.write(f"**Designation:** {selected_appraisal['employee_data']['designation']}")
        st.write(f"**Department:** {selected_appraisal['employee_data']['department']}")
        st.write(f"**Date:** {selected_appraisal['employee_data']['date']}")

        # Display Key Status & Ratings
        st.markdown("### Key Status & Ratings Guide")
        ratings_data = {
            "POINTS": [5, 4, 3, 2, 1],
            "DESCRIPTION": ["Exceeds Expectation", "Meet Expectations", "Average", "Requires Improvement", "Unsatisfactory"],
            "RATINGS": ["100% And Above", "80 - 99%", "60 - 79%", "40 - 59%", "0 - 39%"] # Corrected typo 40-59%
        }
        df_ratings = pd.DataFrame(ratings_data)
        st.dataframe(df_ratings, hide_index=True)

        st.markdown("---")
        st.subheader("SECTION A: Performance Goals (70%)")

        # Define is_manager here to ensure it's always set
        is_manager = st.session_state.current_user['profile']['grade_level'] == 'Manager' or st.session_state.current_user['role'] == 'admin'

        # Display and allow manager to rate Section A goals
        for i, goal in enumerate(selected_appraisal['section_a_goals']):
            st.markdown(f"**Goal {i+1}:** {goal['goal_description']}")
            st.write(f"**Collaborating Department:** {goal['collaborating_department']}")
            st.write(f"**Status:** {goal['status']}")
            st.write(f"**Employee Remark/Update:** {goal['employee_remark_update']}")
            st.write(f"**Start Date:** {goal['start_date']}")
            st.write(f"**End Date:** {goal['end_date']}")
            st.write(f"**Duration:** {goal['duration']}")
            st.write(f"**Weighting (%):** {goal['weighting_percent']}")
            st.write(f"**Self Rating (1-5):** {goal['self_rating'] if goal['self_rating'] is not None else 'Not Rated'}")

            current_lm_rating = goal['line_manager_rating'] if goal['line_manager_rating'] is not None else 0
            selected_appraisal['section_a_goals'][i]['line_manager_rating'] = st.slider(
                f"Line Manager's Rating (1-5) for Goal {i+1}",
                min_value=1, max_value=5, value=current_lm_rating,
                disabled=not is_manager, key=f"lm_rating_goal_{i}_{selected_appraisal_id}"
            )
            st.markdown("---")

        st.subheader("SECTION B: Qualitative Assessment (30%)")
        is_hr_or_md = st.session_state.current_user['profile']['department'] in ["HR", "Executive"] or st.session_state.current_user['role'] == 'admin'

        # Leadership & Team Development
        st.markdown("**Leadership & Team Development**")
        st.write(f"**Employee Remark:** {selected_appraisal['section_b_qualitative']['leadership_team_development']['remark']}")
        st.write(f"**Self Rating (1-5):** {selected_appraisal['section_b_qualitative']['leadership_team_development']['self_rating'] if selected_appraisal['section_b_qualitative']['leadership_team_development']['self_rating'] is not None else 'Not Rated'}")
        current_b1_lm_rating = selected_appraisal['section_b_qualitative']['leadership_team_development']['line_manager_rating'] if selected_appraisal['section_b_qualitative']['leadership_team_development']['line_manager_rating'] is not None else 0
        selected_appraisal['section_b_qualitative']['leadership_team_development']['line_manager_rating'] = st.slider(
            "Line Manager's Rating (1-5) for Leadership & Team Development:",
            min_value=1, max_value=5, value=current_b1_lm_rating,
            disabled=not is_manager, key=f"lm_rating_b1_{selected_appraisal_id}"
        )
        st.markdown("---")

        # Coordinate and Optimize Resources
        st.markdown("**Coordinate and Optimize the Use of Resources**")
        st.write(f"**Employee Remark:** {selected_appraisal['section_b_qualitative']['coordinate_optimize_resources']['remark']}")
        st.write(f"**Self Rating (1-5):** {selected_appraisal['section_b_qualitative']['coordinate_optimize_resources']['self_rating'] if selected_appraisal['section_b_qualitative']['coordinate_optimize_resources']['self_rating'] is not None else 'Not Rated'}")
        current_b2_lm_rating = selected_appraisal['section_b_qualitative']['coordinate_optimize_resources']['line_manager_rating'] if selected_appraisal['section_b_qualitative']['coordinate_optimize_resources']['line_manager_rating'] is not None else 0
        selected_appraisal['section_b_qualitative']['coordinate_optimize_resources']['line_manager_rating'] = st.slider(
            "Line Manager's Rating (1-5) for Resource Coordination:",
            min_value=1, max_value=5, value=current_b2_lm_rating,
            disabled=not is_manager, key=f"lm_rating_b2_{selected_appraisal_id}"
        )
        st.markdown("---")

        # Interpersonal
        st.markdown("**Interpersonal**")
        st.write(f"**Employee Remark:** {selected_appraisal['section_b_qualitative']['interpersonal']['remark']}")
        st.write(f"**Self Rating (1-5):** {selected_appraisal['section_b_qualitative']['interpersonal']['self_rating'] if selected_appraisal['section_b_qualitative']['interpersonal']['self_rating'] is not None else 'Not Rated'}")
        current_b3_lm_rating = selected_appraisal['section_b_qualitative']['interpersonal']['line_manager_rating'] if selected_appraisal['section_b_qualitative']['interpersonal']['line_manager_rating'] is not None else 0
        selected_appraisal['section_b_qualitative']['interpersonal']['line_manager_rating'] = st.slider(
            "Line Manager's Rating (1-5) for Interpersonal Skills:",
            min_value=1, max_value=5, value=current_b3_lm_rating,
            disabled=not is_manager, key=f"lm_rating_b3_{selected_appraisal_id}"
        )
        st.markdown("---")

        st.subheader("Training Recommendation")
        selected_appraisal['training_recommendation'] = st.text_area(
            "Training Recommendation:",
            value=selected_appraisal['training_recommendation'],
            disabled=not is_manager, # Only managers/admin can recommend training
            key=f"training_rec_{selected_appraisal_id}"
        )
        st.markdown("---")

        st.subheader("HR's Remark")
        selected_appraisal['hr_remark'] = st.text_area(
            "HR's Remark:",
            value=selected_appraisal['hr_remark'],
            disabled=not (st.session_state.current_user['profile']['department'] == "HR" or st.session_state.current_user['role'] == 'admin'),
            key=f"hr_remark_{selected_appraisal_id}"
        )
        st.markdown("---")

        st.subheader("MD's Remark")
        selected_appraisal['md_remark'] = st.text_area(
            "MD's Remark:",
            value=selected_appraisal['md_remark'],
            disabled=not (st.session_state.current_user['profile']['grade_level'] == "MD" or st.session_state.current_user['role'] == 'admin'),
            key=f"md_remark_{selected_appraisal_id}"
        )
        st.markdown("---")

        if st.button("Save Appraisal Review"):
            # Update the original performance_goals list with the line_manager_ratings from appraisal
            performance_goals_data = load_data(PERFORMANCE_GOALS_FILE) # Reload to ensure latest
            for app_goal in selected_appraisal['section_a_goals']:
                for i, p_goal in enumerate(performance_goals_data):
                    if p_goal.get('goal_id') == app_goal.get('goal_id'):
                        performance_goals_data[i]['line_manager_rating'] = app_goal['line_manager_rating']
                        break
            save_data(performance_goals_data, PERFORMANCE_GOALS_FILE) # Save updated goals

            appraisals[appraisal_index] = selected_appraisal
            save_data(appraisals, SELF_APPRAISALS_FILE)
            st.success("Appraisal review saved successfully!")
            st.rerun()

# --- Chat Feature (Personalized) ---
def get_unread_messages(recipient_staff_id):
    chat_messages = load_data(CHAT_MESSAGES_FILE)
    unread_count = 0
    for msg in chat_messages:
        if msg['receiver_staff_id'] == recipient_staff_id and not msg.get('read', False):
            unread_count += 1
    return unread_count

def chat_page():
    st.header("Personalized Chat")
    current_user_staff_id = st.session_state.current_user['profile']['staff_id']
    current_user_name = st.session_state.current_user['profile']['name']
    all_users = load_data(USERS_FILE)
    chat_messages = load_data(CHAT_MESSAGES_FILE)

    # Get a list of other users to chat with
    other_users = [user for user in all_users if user['profile']['staff_id'] != current_user_staff_id]
    
    if not other_users:
        st.info("No other users available to chat with.")
        return

    # Create a mapping from staff_id to full name for display
    staff_id_to_name = {user['profile']['staff_id']: user['profile']['name'] for user in all_users}

    # Select recipient
    recipient_options = {user['profile']['name']: user['profile']['staff_id'] for user in other_users}
    selected_recipient_name = st.selectbox("Chat with:", [""] + list(recipient_options.keys()))

    selected_recipient_staff_id = None
    if selected_recipient_name:
        selected_recipient_staff_id = recipient_options[selected_recipient_name]
        st.subheader(f"Chat with {selected_recipient_name}")

        # Filter messages between current user and selected recipient
        # Messages where current user is sender AND selected recipient is receiver
        # OR messages where selected recipient is sender AND current user is receiver
        conversation_messages = [
            msg for msg in chat_messages
            if (msg['sender_staff_id'] == current_user_staff_id and msg['receiver_staff_id'] == selected_recipient_staff_id) or
               (msg['sender_staff_id'] == selected_recipient_staff_id and msg['receiver_staff_id'] == current_user_staff_id)
        ]

        # Sort messages by timestamp
        conversation_messages.sort(key=lambda x: x['timestamp'])

        # Display messages
        chat_container = st.container(height=400, border=True)
        if conversation_messages:
            for msg in conversation_messages:
                sender_name = staff_id_to_name.get(msg['sender_staff_id'], 'Unknown')
                message_time = datetime.fromisoformat(msg['timestamp']).strftime("%Y-%m-%d %H:%M")
                
                if msg['sender_staff_id'] == current_user_staff_id:
                    chat_container.markdown(f"**You** ({message_time}): {msg['message']}")
                else:
                    chat_container.markdown(f"**{sender_name}** ({message_time}): {msg['message']}")
                
                # Mark message as read if current user is the receiver and it's unread
                if msg['receiver_staff_id'] == current_user_staff_id and not msg.get('read', False):
                    msg['read'] = True # Mark as read
                    # This modification needs to be saved back to the file
                    # To avoid saving on every message display, we'll save when a new message is sent or page is reloaded.
                    # For now, let's just update the in-memory object.
                    # A more robust solution would involve a 'mark all as read' button or saving on page exit.
        else:
            chat_container.info("No messages in this conversation yet.")

        # Message input
        new_message = st.text_input("Type your message here:", key="chat_input")
        if st.button("Send Message"):
            if new_message:
                new_chat_entry = {
                    "message_id": str(uuid.uuid4()),
                    "sender_staff_id": current_user_staff_id,
                    "receiver_staff_id": selected_recipient_staff_id,
                    "timestamp": datetime.now().isoformat(),
                    "message": new_message,
                    "read": False # Message is unread by recipient initially
                }
                chat_messages.append(new_chat_entry)
                save_data(chat_messages, CHAT_MESSAGES_FILE)
                st.success("Message sent!")
                st.rerun() # Rerun to clear input and show new message

    # After sending a message or selecting a new chat, ensure all displayed messages are marked as read for the current user
    # This is a simple approach to mark messages as read. A more sophisticated system might involve
    # a separate 'read status' for each user or a 'mark as read' button.
    for msg in chat_messages:
        if msg['receiver_staff_id'] == current_user_staff_id and not msg.get('read', False):
            if selected_recipient_staff_id and (msg['sender_staff_id'] == selected_recipient_staff_id):
                msg['read'] = True
            elif not selected_recipient_staff_id: # If no specific chat selected, but on chat page
                 msg['read'] = True # Mark all as read when user enters chat page
    save_data(chat_messages, CHAT_MESSAGES_FILE) # Save the read status updates


# --- View Payslip (Staff) ---
def view_payslip_page():
    st.header("View Your Payslips")
    current_user_staff_id = st.session_state.current_user['profile']['staff_id']
    payroll_data = load_data(PAYROLL_FILE)

    user_payslips = [p for p in payroll_data if p['staff_id'] == current_user_staff_id]

    if not user_payslips:
        st.info("No payslips available for you yet.")
        return

    # Sort payslips by pay_date in descending order
    user_payslips.sort(key=lambda x: x.get('pay_date', '0000-00-00'), reverse=True)

    payslip_options = {f"{p['pay_period']} (Paid: {p['pay_date']})": p['payslip_id'] for p in user_payslips}
    selected_payslip_key = st.selectbox("Select Pay Period:", [""] + list(payslip_options.keys()))

    if selected_payslip_key:
        selected_payslip_id = payslip_options[selected_payslip_key]
        selected_payslip = next(p for p in user_payslips if p['payslip_id'] == selected_payslip_id)

        st.subheader(f"Payslip for {selected_payslip['pay_period']}")
        st.markdown(f"**Pay Date:** {selected_payslip.get('pay_date', 'N/A')}")
        # Ensure values are numeric before formatting
        gross_pay = float(selected_payslip.get('gross_pay', 0.0))
        deductions = float(selected_payslip.get('deductions', 0.0))
        net_pay = float(selected_payslip.get('net_pay', 0.0))

        st.markdown(f"**Gross Pay:** NGN {gross_pay:,.2f}")
        st.markdown(f"**Total Deductions:** NGN {deductions:,.2f}")
        st.markdown(f"**Net Pay:** NGN {net_pay:,.2f}")

        st.markdown("---")
        st.write("*(Note: This is a simplified payslip view. A full payslip would include detailed breakdowns of earnings, taxes, and other deductions.)*")

        # Add a simple bar chart for gross vs net pay
        payslip_data = pd.DataFrame({
            'Category': ['Gross Pay', 'Deductions', 'Net Pay'],
            'Amount': [gross_pay, deductions, net_pay]
        })
        fig_payslip = px.bar(payslip_data, x='Category', y='Amount',
                             title='Payslip Summary',
                             color='Category',
                             template='plotly_white')
        st.plotly_chart(fig_payslip, use_container_width=True)


# --- View Company Policy (Staff) ---
def view_company_policy_page():
    st.header("Company Policies")
    hr_policies = load_data(HR_POLICIES_FILE)

    if not hr_policies:
        st.info("No company policies available yet.")
        return

    policy_titles = {policy['title']: policy['policy_id'] for policy in hr_policies if isinstance(policy, dict) and 'title' in policy}
    selected_policy_title = st.selectbox("Select a policy to view:", [""] + list(policy_titles.keys()))

    if selected_policy_title:
        selected_policy_id = policy_titles[selected_policy_title]
        selected_policy = next(p for p in hr_policies if p.get('policy_id') == selected_policy_id)

        st.subheader(selected_policy['title'])
        st.markdown(selected_policy['content'])
        st.info(f"Last Updated: {selected_policy.get('last_updated', 'N/A')}")

# --- Admin Policy Management ---
def admin_manage_policies():
    st.header("Manage Company Policies (Admin/HR)")
    hr_policies = load_data(HR_POLICIES_FILE)

    st.subheader("Existing Policies")
    if hr_policies:
        # Filter out any non-dictionary entries before creating DataFrame
        displayable_policies = [p for p in hr_policies if isinstance(p, dict) and 'title' in p and 'last_updated' in p]
        if displayable_policies:
            df_policies = pd.DataFrame(displayable_policies)
            st.dataframe(df_policies[['title', 'last_updated']])
        else:
            st.info("No valid policies to display.")
    else:
        st.info("No policies have been added yet.")

    st.subheader("Add New Policy")
    with st.form("add_policy_form"):
        new_policy_title = st.text_input("Policy Title")
        new_policy_content = st.text_area("Policy Content", height=300)
        add_policy_submitted = st.form_submit_button("Add Policy")

        if add_policy_submitted:
            if new_policy_title and new_policy_content:
                if any(p.get('title', '').lower() == new_policy_title.lower() for p in hr_policies if isinstance(p, dict)):
                    st.error("A policy with this title already exists.")
                else:
                    new_policy = {
                        "policy_id": str(uuid.uuid4()),
                        "title": new_policy_title,
                        "content": new_policy_content,
                        "last_updated": datetime.now().isoformat().split('T')[0]
                    }
                    hr_policies.append(new_policy)
                    save_data(hr_policies, HR_POLICIES_FILE)
                    st.success("Policy added successfully!")
                    st.rerun()
            else:
                st.error("Please fill in both title and content.")

    st.subheader("Edit/Delete Policy")
    if hr_policies:
        # Filter for valid policies to present in selectbox
        valid_policy_titles = [p['title'] for p in hr_policies if isinstance(p, dict) and 'title' in p]
        policy_to_edit_delete = st.selectbox("Select Policy by Title", [""] + valid_policy_titles)
        if policy_to_edit_delete:
            selected_policy = next((p for p in hr_policies if p.get('title') == policy_to_edit_delete), None)
            if selected_policy:
                policy_index = hr_policies.index(selected_policy)

                with st.form("edit_policy_form"):
                    edited_policy_title = st.text_input("Policy Title", value=selected_policy['title'], disabled=True) # Title usually not editable after creation
                    edited_policy_content = st.text_area("Policy Content", value=selected_policy['content'], height=300)

                    col_edit, col_delete = st.columns(2)
                    with col_edit:
                        edit_policy_submitted = st.form_submit_button("Update Policy")
                    with col_delete:
                        delete_policy_submitted = st.form_submit_button("Delete Policy")

                    if edit_policy_submitted:
                        hr_policies[policy_index]['content'] = edited_policy_content
                        hr_policies[policy_index]['last_updated'] = datetime.now().isoformat().split('T')[0]
                        save_data(hr_policies, HR_POLICIES_FILE)
                        st.success("Policy updated successfully!")
                        st.rerun()

                    if delete_policy_submitted:
                        del hr_policies[policy_index]
                        save_data(hr_policies, HR_POLICIES_FILE)
                        st.success("Policy deleted successfully!")
                        st.rerun()
            else:
                st.warning("Selected policy not found or is malformed.")
    else:
        st.info("No policies to edit or delete.")

# --- Admin Disciplinary Records Management ---
def admin_manage_disciplinary_records():
    st.header("Manage Disciplinary Records (HR/Admin)")
    disciplinary_records = load_data(DISCIPLINARY_RECORDS_FILE)
    users = load_data(USERS_FILE)
    staff_id_to_name = {user['profile']['staff_id']: user['profile']['name'] for user in users}

    st.subheader("Existing Disciplinary Records")
    if disciplinary_records:
        df_records = pd.DataFrame(disciplinary_records)
        df_records['Employee Name'] = df_records['staff_id'].map(staff_id_to_name)
        st.dataframe(df_records[['Employee Name', 'staff_id', 'incident_date', 'incident_type', 'action_taken', 'status']])
    else:
        st.info("No disciplinary records found.")

    st.subheader("Add New Disciplinary Record")
    with st.form("add_disciplinary_record_form"):
        # Select employee from existing users
        employee_options = {user['profile']['name']: user['profile']['staff_id'] for user in users if user['role'] == 'staff'}
        selected_employee_name = st.selectbox("Select Employee:", [""] + list(employee_options.keys()))
        selected_staff_id = employee_options.get(selected_employee_name)

        incident_date = st.date_input("Incident Date", value=datetime.now().date())
        incident_type = st.text_input("Incident Type (e.g., Lateness, Misconduct, Policy Violation)")
        description = st.text_area("Description of Incident")
        action_taken = st.text_area("Action Taken (e.g., Verbal Warning, Written Warning, Suspension)")
        status = st.selectbox("Status", ["Open", "Closed", "Under Review"])
        add_record_submitted = st.form_submit_button("Add Record")

        if add_record_submitted:
            if selected_staff_id and incident_type and description and action_taken:
                new_record = {
                    "record_id": str(uuid.uuid4()),
                    "staff_id": selected_staff_id,
                    "incident_date": incident_date.isoformat(),
                    "incident_type": incident_type,
                    "description": description,
                    "action_taken": action_taken,
                    "status": status,
                    "recorded_by": st.session_state.current_user['profile']['name'],
                    "recorded_date": datetime.now().isoformat()
                }
                disciplinary_records.append(new_record)
                save_data(disciplinary_records, DISCIPLINARY_RECORDS_FILE)
                st.success("Disciplinary record added successfully!")
                st.rerun()
            else:
                st.error("Please fill in all required fields.")

    st.subheader("Edit/Close Disciplinary Record")
    if disciplinary_records:
        record_options = {f"{staff_id_to_name.get(r['staff_id'], 'Unknown')} - {r['incident_type']} ({r['incident_date']})": r['record_id'] for r in disciplinary_records}
        selected_record_key = st.selectbox("Select Record to Edit/Close:", [""] + list(record_options.keys()))

        if selected_record_key:
            selected_record_id = record_options[selected_record_key]
            selected_record = next(r for r in disciplinary_records if r['record_id'] == selected_record_id)
            record_index = disciplinary_records.index(selected_record)

            with st.form("edit_disciplinary_record_form"):
                st.write(f"**Employee:** {staff_id_to_name.get(selected_record['staff_id'])}")
                edited_incident_date = st.date_input("Incident Date", value=date.fromisoformat(selected_record['incident_date']))
                edited_incident_type = st.text_input("Incident Type", value=selected_record['incident_type'])
                edited_description = st.text_area("Description of Incident", value=selected_record['description'])
                edited_action_taken = st.text_area("Action Taken", value=selected_record['action_taken'])
                edited_status = st.selectbox("Status", ["Open", "Closed", "Under Review"], index=["Open", "Closed", "Under Review"].index(selected_record['status']))

                col_edit, col_delete = st.columns(2)
                with col_edit:
                    edit_record_submitted = st.form_submit_button("Update Record")
                with col_delete:
                    delete_record_submitted = st.form_submit_button("Delete Record")

                if edit_record_submitted:
                    disciplinary_records[record_index]['incident_date'] = edited_incident_date.isoformat()
                    disciplinary_records[record_index]['incident_type'] = edited_incident_type
                    disciplinary_records[record_index]['description'] = edited_description
                    disciplinary_records[record_index]['action_taken'] = edited_action_taken
                    disciplinary_records[record_index]['status'] = edited_status
                    save_data(disciplinary_records, DISCIPLINARY_RECORDS_FILE)
                    st.success("Disciplinary record updated successfully!")
                    st.rerun()

                if delete_record_submitted:
                    del disciplinary_records[record_index]
                    save_data(disciplinary_records, DISCIPLINARY_RECORDS_FILE)
                    st.success("Disciplinary record deleted successfully!")
                    st.rerun()
    else:
        st.info("No records to edit or delete.")

# --- Time Attendance Functions (New) ---
def record_attendance():
    st.header("Time Attendance")
    current_user_staff_id = st.session_state.current_user['profile']['staff_id']
    attendance_records = load_data(ATTENDANCE_RECORDS_FILE)
    today = date.today().isoformat()

    # Find today's record for the current user
    today_record = next((rec for rec in attendance_records if rec['staff_id'] == current_user_staff_id and rec['date'] == today), None)

    st.subheader("Clock In/Out")

    if today_record and today_record.get('clock_in_time') and not today_record.get('clock_out_time'):
        # Ensure clock_in_time is not None before formatting
        clock_in_display = datetime.fromisoformat(today_record['clock_in_time']).strftime('%H:%M:%S') if today_record['clock_in_time'] else 'N/A'
        st.info(f"You are currently clocked in since {clock_in_display}.")
        if st.button("Clock Out"):
            clock_out_time = datetime.now().isoformat()
            today_record['clock_out_time'] = clock_out_time
            
            # Calculate duration
            in_time = datetime.fromisoformat(today_record['clock_in_time'])
            out_time = datetime.fromisoformat(clock_out_time)
            duration = out_time - in_time
            today_record['duration_hours'] = round(duration.total_seconds() / 3600, 2) # Duration in hours

            save_data(attendance_records, ATTENDANCE_RECORDS_FILE)
            st.success(f"Clocked out successfully at {datetime.fromisoformat(clock_out_time).strftime('%H:%M:%S')}! Worked for {today_record['duration_hours']} hours.")
            st.rerun()
    else:
        if st.button("Clock In"):
            new_record = {
                "record_id": str(uuid.uuid4()),
                "staff_id": current_user_staff_id,
                "date": today,
                "clock_in_time": datetime.now().isoformat(),
                "clock_out_time": None,
                "duration_hours": 0.0
            }
            attendance_records.append(new_record)
            save_data(attendance_records, ATTENDANCE_RECORDS_FILE)
            st.success(f"Clocked in successfully at {datetime.now().strftime('%H:%M:%S')}!")
            st.rerun()
        if today_record and today_record.get('clock_out_time'):
            # Ensure clock_out_time is not None before formatting
            clock_out_display = datetime.fromisoformat(today_record['clock_out_time']).strftime('%H:%M:%S') if today_record['clock_out_time'] else 'N/A'
            st.info(f"You have already clocked out today. Last clocked out at {clock_out_display}. Total hours: {today_record['duration_hours']} hours.")
        elif today_record and not today_record.get('clock_in_time'): # Case where record exists but clock_in_time is somehow missing
            st.warning("Your attendance record for today seems incomplete. Please clock in.")


    st.subheader("Your Attendance History")
    user_attendance = [rec for rec in attendance_records if rec['staff_id'] == current_user_staff_id]
    if user_attendance:
        df_attendance = pd.DataFrame(user_attendance)
        df_attendance['date'] = pd.to_datetime(df_attendance['date']).dt.date # Convert to date object for display
        df_attendance['clock_in_time_display'] = df_attendance['clock_in_time'].apply(lambda x: datetime.fromisoformat(x).strftime('%H:%M:%S') if x else 'N/A')
        df_attendance['clock_out_time_display'] = df_attendance['clock_out_time'].apply(lambda x: datetime.fromisoformat(x).strftime('%H:%M:%S') if x else 'N/A')
        
        st.dataframe(df_attendance[['date', 'clock_in_time_display', 'clock_out_time_display', 'duration_hours']].sort_values(by='date', ascending=False), use_container_width=True)
    else:
        st.info("No attendance records found for you.")

def admin_manage_attendance():
    st.header("Manage Attendance Records (Admin/HR)")
    attendance_records = load_data(ATTENDANCE_RECORDS_FILE)
    users = load_data(USERS_FILE)
    staff_id_to_name = {user['profile']['staff_id']: user['profile']['name'] for user in users}

    if not attendance_records:
        st.info("No attendance records found.")
        return

    df_attendance = pd.DataFrame(attendance_records)
    df_attendance['Employee Name'] = df_attendance['staff_id'].map(staff_id_to_name)
    df_attendance['date'] = pd.to_datetime(df_attendance['date']).dt.date

    st.subheader("Filter Attendance Records")
    all_staff_ids = sorted(list(staff_id_to_name.keys()))
    selected_staff_id = st.selectbox("Filter by Employee:", ["All"] + all_staff_ids, format_func=lambda x: staff_id_to_name.get(x, "All Employees"))

    col_start, col_end = st.columns(2)
    with col_start:
        start_date_filter = st.date_input("Start Date", value=df_attendance['date'].min() if not df_attendance.empty else datetime.now().date() - timedelta(days=30))
    with col_end:
        end_date_filter = st.date_input("End Date", value=df_attendance['date'].max() if not df_attendance.empty else datetime.now().date())

    filtered_df = df_attendance.copy()
    if selected_staff_id != "All":
        filtered_df = filtered_df[filtered_df['staff_id'] == selected_staff_id]
    
    filtered_df = filtered_df[(filtered_df['date'] >= start_date_filter) & (filtered_df['date'] <= end_date_filter)]

    st.subheader("Filtered Attendance Records")
    if not filtered_df.empty:
        filtered_df['clock_in_time_display'] = filtered_df['clock_in_time'].apply(lambda x: datetime.fromisoformat(x).strftime('%H:%M:%S') if x else 'N/A')
        filtered_df['clock_out_time_display'] = filtered_df['clock_out_time'].apply(lambda x: datetime.fromisoformat(x).strftime('%H:%M:%S') if x else 'N/A')
        
        st.dataframe(filtered_df[['Employee Name', 'staff_id', 'date', 'clock_in_time_display', 'clock_out_time_display', 'duration_hours']].sort_values(by='date', ascending=False), use_container_width=True)

        total_hours = filtered_df['duration_hours'].sum()
        st.markdown(f"**Total Hours Worked in Filtered Period:** {total_hours:.2f} hours")

        st.subheader("Attendance Statistics")
        # Bar chart for total hours worked per employee in the filtered period
        hours_by_employee = filtered_df.groupby('Employee Name')['duration_hours'].sum().reset_index()
        fig_hours = px.bar(hours_by_employee, x='Employee Name', y='duration_hours',
                           title='Total Hours Worked by Employee (Filtered Period)',
                           labels={'duration_hours': 'Total Hours'},
                           color='Employee Name',
                           template='plotly_white')
        st.plotly_chart(fig_hours, use_container_width=True)

        # Line chart for daily average hours (if multiple days selected)
        if len(filtered_df['date'].unique()) > 1:
            daily_avg_hours = filtered_df.groupby('date')['duration_hours'].mean().reset_index()
            fig_daily_avg = px.line(daily_avg_hours, x='date', y='duration_hours',
                                    title='Average Daily Hours Worked',
                                    labels={'duration_hours': 'Average Hours'},
                                    template='plotly_white')
            st.plotly_chart(fig_daily_avg, use_container_width=True)

    else:
        st.info("No records match the selected filters.")

# --- Profile Page (New) ---
def view_profile_page():
    st.header("My Profile")
    current_user = st.session_state.current_user
    current_user_profile = current_user['profile']
    users = load_data(USERS_FILE)

    st.subheader("Personal Information")
    st.write(f"**Full Name:** {current_user_profile.get('name', 'N/A')}")
    st.write(f"**Staff ID:** {current_user_profile.get('staff_id', 'N/A')}")
    st.write(f"**Username:** {current_user.get('username', 'N/A')}")
    st.write(f"**Role:** {current_user.get('role', 'N/A').capitalize()}")
    st.write(f"**Date of Birth:** {current_user_profile.get('date_of_birth', 'N/A')}")
    st.write(f"**Gender:** {current_user_profile.get('gender', 'N/A')}")

    st.subheader("Employment Details")
    st.write(f"**Department:** {current_user_profile.get('department', 'N/A')}")
    st.write(f"**Grade Level:** {current_user_profile.get('grade_level', 'N/A')}")
    st.write(f"**Work Anniversary:** {current_user_profile.get('work_anniversary', 'N/A')}")
    st.write(f"**Education Background:** {current_user_profile.get('education_background', 'N/A')}")
    st.write(f"**Professional Experience:** {current_user_profile.get('professional_experience', 'N/A')}")

    st.subheader("Contact Information")
    st.write(f"**Email Address:** {current_user_profile.get('email_address', 'N/A')}")
    st.write(f"**Phone Number:** {current_user_profile.get('phone_number', 'N/A')}")
    st.write(f"**Address:** {current_user_profile.get('address', 'N/A')}")

    st.subheader("Training Attended")
    if current_user_profile.get('training_attended'):
        for i, training in enumerate(current_user_profile['training_attended']):
            st.write(f"- {training}")
    else:
        st.info("No training records found.")

    st.subheader("Update Your Profile")
    st.info("You can update your contact information and add training records here.")

    with st.form("update_profile_form"):
        # Editable fields
        updated_phone_number = st.text_input("Phone Number", value=current_user_profile.get('phone_number', ''))
        updated_address = st.text_area("Address", value=current_user_profile.get('address', ''))
        
        # Add new training
        new_training_entry = st.text_input("Add New Training Attended (e.g., 'Project Management Certification, 2023')")
        
        submit_update = st.form_submit_button("Update Profile")

        if submit_update:
            # Find the user in the main users list and update their profile
            user_found = False
            for i, user in enumerate(users):
                if user.get('username') == current_user.get('username'):
                    users[i]['profile']['phone_number'] = updated_phone_number
                    users[i]['profile']['address'] = updated_address
                    if new_training_entry and new_training_entry not in users[i]['profile'].get('training_attended', []):
                        if 'training_attended' not in users[i]['profile'] or users[i]['profile']['training_attended'] is None:
                            users[i]['profile']['training_attended'] = []
                        users[i]['profile']['training_attended'].append(new_training_entry)
                    st.session_state.current_user['profile'] = users[i]['profile'] # Update session state
                    save_data(users, USERS_FILE)
                    user_found = True
                    st.success("Profile updated successfully!")
                    st.rerun()
                    break
            if not user_found:
                st.error("Could not find your user record to update. Please contact support.")


# --- Main Application Logic ---
def main():
    setup_initial_data()

    # Initialize session state for page navigation and authentication
    if "current_page" not in st.session_state:
        st.session_state.current_page = "login"
    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    display_logo_and_title()

    if st.session_state.current_user is None:
        # User is not logged in
        st.sidebar.title("Login")
        username = st.sidebar.text_input("Username (Email)")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            user = authenticate_user(username, password)
            if user:
                st.session_state.current_user = user
                st.session_state.current_page = "dashboard"
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.sidebar.error("Invalid username or password.")
        # Option to register (for demo purposes, could be removed in production)
        if st.sidebar.button("Register New Account"):
            st.session_state.current_page = "register"
            st.rerun()
        if st.session_state.current_page == "register":
            register_new_user()
        st.info("Please log in to access the portal.") # This line should be here, inside the 'if st.session_state.current_user is None' block
        st.session_state.current_page = "login" # Ensure redirect to login if not logged in
    else:
        # User is logged in
        st.sidebar.title("Navigation")
        # Determine user role
        user_role = st.session_state.current_user.get('role', 'staff')
        user_profile = st.session_state.current_user.get('profile', {})
        user_department = user_profile.get('department')
        user_grade = user_profile.get('grade_level')

        menu_options = {
            "Dashboard": "dashboard",
            "My Profile": "my_profile", # New profile page option
            "Request Leave": "request_leave",
            "Request OPEX/CAPEX": "request_opex_capex",
            "Set Performance Goals": "set_performance_goals",
            "Submit Self-Appraisal": "submit_self_appraisal",
            "Time Attendance": "time_attendance", # New time attendance option
            "Chat": "chat", # New chat option
            "View Payslip": "view_payslip", # New payslip option
            "View Company Policy": "view_company_policy", # New policy option
        }

        # Add admin-specific menu options
        if user_role == "admin":
            menu_options["Manage Users"] = "admin_manage_users"
            menu_options["Manage Leave (HR)"] = "admin_manage_leave"
            menu_options["Manage OPEX/CAPEX Approvals"] = "manage_opex_capex_approvals"
            menu_options["View All Performance Goals"] = "admin_view_performance_goals"
            menu_options["Manage Appraisals"] = "admin_manage_appraisals" # New admin appraisal management
            menu_options["Manage HR Policies"] = "admin_manage_policies" # New admin policy management
            menu_options["Manage Disciplinary Records"] = "admin_manage_disciplinary_records" # New disciplinary records
            menu_options["Manage Attendance"] = "admin_manage_attendance" # New admin attendance management

        # Add approver-specific menu option for OPEX/CAPEX
        is_approver = False
        for role_info in APPROVAL_CHAIN:
            if (role_info['department'] == user_department and
                    role_info['grade_level'] == user_grade):
                is_approver = True
                break
        if is_approver and user_role != "admin": # Non-admin approvers
            menu_options["Manage OPEX/CAPEX Approvals"] = "manage_opex_capex_approvals"
        
        # HR Manager also manages leave
        if user_department == "HR" and user_grade == "Manager" and user_role != "admin":
            menu_options["Manage Leave (HR)"] = "admin_manage_leave"
            menu_options["Manage Appraisals"] = "admin_manage_appraisals"
            menu_options["Manage HR Policies"] = "admin_manage_policies"
            menu_options["Manage Disciplinary Records"] = "admin_manage_disciplinary_records"
            menu_options["Manage Attendance"] = "admin_manage_attendance"

        # MD also manages appraisals
        if user_grade == "MD" and user_role != "admin":
            menu_options["Manage Appraisals"] = "admin_manage_appraisals"

        selected_page_name = st.sidebar.radio(
            "Go to",
            list(menu_options.keys()),
            index=list(menu_options.keys()).index(next(k for k, v in menu_options.items() if v == st.session_state.current_page) if st.session_state.current_page in menu_options.values() else "Dashboard")
        )
        st.session_state.current_page = menu_options[selected_page_name]

        st.sidebar.markdown("---")
        st.sidebar.write(f"Logged in as: {st.session_state.current_user['profile']['name']}")
        st.sidebar.write(f"Role: {st.session_state.current_user['role'].capitalize()}")
        if st.sidebar.button("Logout"):
            st.session_state.current_user = None
            st.session_state.current_page = "login"
            st.success("Logged out successfully.")
            st.rerun()

        # --- Page Routing ---
        if st.session_state.current_page == "dashboard":
            display_dashboard()
        elif st.session_state.current_page == "my_profile":
            view_profile_page()
        elif st.session_state.current_page == "request_leave":
            request_leave()
        elif st.session_state.current_page == "request_opex_capex":
            request_opex_capex()
        elif st.session_state.current_page == "set_performance_goals":
            manage_performance_goals()
        elif st.session_state.current_page == "submit_self_appraisal":
            submit_self_appraisal()
        elif st.session_state.current_page == "time_attendance":
            record_attendance()
        elif st.session_state.current_page == "chat":
            chat_page()
        elif st.session_state.current_page == "view_payslip":
            view_payslip_page()
        elif st.session_state.current_page == "view_company_policy":
            view_company_policy_page()
        # Admin/Approver pages
        elif st.session_state.current_page == "admin_manage_users" and user_role == "admin":
            admin_manage_users()
        elif st.session_state.current_page == "admin_manage_leave" and (user_role == "admin" or (user_department == "HR" and user_grade == "Manager")):
            admin_manage_leave()
        elif st.session_state.current_page == "manage_opex_capex_approvals" and (user_role == "admin" or is_approver):
            admin_manage_opex_capex_approvals()
        elif st.session_state.current_page == "admin_view_performance_goals" and user_role == "admin":
            admin_view_performance_goals()
        elif st.session_state.current_page == "admin_manage_appraisals" and (user_role == "admin" or (user_department == "HR" and user_grade == "Manager") or user_grade == "MD"):
            admin_manage_appraisals()
        elif st.session_state.current_page == "admin_manage_policies" and (user_role == "admin" or (user_department == "HR" and user_grade == "Manager")):
            admin_manage_policies()
        elif st.session_state.current_page == "admin_manage_disciplinary_records" and (user_role == "admin" or (user_department == "HR" and user_grade == "Manager")):
            admin_manage_disciplinary_records()
        elif st.session_state.current_page == "admin_manage_attendance" and (user_role == "admin" or (user_department == "HR" and user_grade == "Manager")):
            admin_manage_attendance()
        else:
            st.error("Access Denied: Page not found or you do not have permission to view this page.")
            st.session_state.current_page = "dashboard" # Redirect to dashboard
            st.rerun()


def register_new_user():
    st.header("Register New Account")
    st.info("Please note: New registrations default to 'staff' role. Admin approval might be required for full access in a real-world scenario.")
    
    users = load_data(USERS_FILE)

    with st.form("register_form"):
        new_username = st.text_input("Choose a Username (Email)")
        new_password = st.text_input("Create Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        st.markdown("---")
        st.subheader("Your Profile Details")
        new_name = st.text_input("Full Name")
        new_staff_id = st.text_input("Staff ID (e.g., POL/2024/XXX)")
        new_dob = st.date_input("Date of Birth", value=date(2000, 1, 1))
        new_gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        new_grade_level = st.text_input("Grade Level (e.g., Officer, Manager)")
        new_department = st.text_input("Department")
        new_education = st.text_area("Education Background")
        new_experience = st.text_area("Professional Experience")
        new_address = st.text_area("Residential Address")
        new_phone = st.text_input("Phone Number")
        new_email = st.text_input("Email Address (should match username)")
        new_work_anniversary = st.date_input("Work Anniversary (Optional)", value=date(datetime.now().year, 1, 1))

        register_submitted = st.form_submit_button("Register")

        if register_submitted:
            if not (new_username and new_password and confirm_password and new_name and new_staff_id and new_department):
                st.error("Please fill in all required fields (Username, Password, Name, Staff ID, Department).")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif any(u['username'] == new_username for u in users):
                st.error("Username already exists. Please choose another.")
            elif any(u.get('profile', {}).get('staff_id') == new_staff_id for u in users):
                st.error("Staff ID already exists. Please use a unique Staff ID.")
            else:
                new_user_data = {
                    "username": new_username,
                    "password": pbkdf2_sha256.hash(new_password),
                    "role": "staff", # Default role for new registrations
                    "profile": {
                        "name": new_name,
                        "staff_id": new_staff_id,
                        "date_of_birth": new_dob.isoformat(),
                        "gender": new_gender,
                        "grade_level": new_grade_level,
                        "department": new_department,
                        "education_background": new_education,
                        "professional_experience": new_experience,
                        "address": new_address,
                        "phone_number": new_phone,
                        "email_address": new_email,
                        "training_attended": [],
                        "work_anniversary": new_work_anniversary.isoformat()
                    }
                }
                users.append(new_user_data)
                save_data(users, USERS_FILE)
                st.success("Account registered successfully! You can now log in.")
                st.session_state.current_page = "login"
                st.rerun()
    st.markdown("---")
    if st.button("Back to Login"):
        st.session_state.current_page = "login"
        st.rerun()

if __name__ == "__main__":
    main()
