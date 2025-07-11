import streamlit as st
import json
from datetime import datetime, timedelta, date
import os
import pandas as pd
import plotly.express as px
from fpdf import FPDF
import base64
from passlib.hash import pbkdf2_sha256 # For password hashing

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
HR_POLICIES_FILE = os.path.join(DATA_DIR, "hr_policies.json") # New

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
                return json.load(file)
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

    pdf.set_font("Arial", "", 10)
    
    # Updated keys to reflect new fields
    for key, value in request_data.items():
        if key in ['request_id', 'requester_name', 'requester_staff_id', 'requester_department',
                            'request_type', 'item_description', 'expense_line', 'budgeted_amount',
                            'material_cost', 'labor_cost', 'total_amount', 'wht_percentage',
                            'wht_amount', 'net_amount_payable', 'budget_balance',
                            'justification', 'vendor_name', 'vendor_account_name', 'vendor_account_no',
                            'vendor_bank', 'submission_date', 'final_status']:
            pdf.set_font("Arial", "B", 10)
            pdf.cell(50, 7, f"{key.replace('_', ' ').title()}:", 0, 0)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 7, str(value))
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "Approval History:", 0, 1)
    pdf.set_font("Arial", "", 10)
    if request_data.get('approval_history'):
        for entry in request_data['approval_history']:
            pdf.multi_cell(0, 7, f"- {entry.get('approver_role')} by {entry.get('approver_name')} on {entry.get('date')}: {entry.get('status')}. Comment: {entry.get('comment', 'No comment.')}")
    else:
        pdf.multi_cell(0, 7, "No approval history recorded.")

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
                "department": "IT", # Changed from Administration to IT for variety
                "education_background": "B.Sc. Computer Science",
                "professional_experience": "2 years in IT support",
                "address": "404 Tech Road, Enugu",
                "phone_number": "+2348078901234",
                "email_address": "king.queen@example.com",
                "training_attended": [],
                "work_anniversary": "2023-11-01"
            }
        }
    ]
    
    # Only create initial users if the file doesn't exist or is empty
    if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
        save_data(initial_users, USERS_FILE)
        st.success("Initial user data created.")

    # Initial HR Policies
    initial_policies = {
        "Staff Handbook": "This handbook outlines the policies, procedures, and expectations for all employees of Polaris Digitech. It covers topics such as conduct, benefits, and company culture...",
        "HSE Policy": "Polaris Digitech is committed to providing a safe and healthy working environment for all employees, contractors, and visitors. This policy details our approach to Health, Safety, and Environment management...",
        "Data Privacy Security Policy": "This policy establishes guidelines for the collection, use, storage, and disclosure of personal data to ensure compliance with data protection laws and safeguard sensitive information...",
        "Procurement Policy": "This policy governs all procurement activities at Polaris Digitech, ensuring transparency, fairness, and cost-effectiveness in acquiring goods and services...",
        "Password Secrecy Policy": "This policy sets forth the requirements for creating, using, and protecting passwords within Polaris Digitech to safeguard company information systems and data from unauthorized access."
    }
    if not os.path.exists(HR_POLICIES_FILE) or os.path.getsize(HR_POLICIES_FILE) == 0:
        save_data(initial_policies, HR_POLICIES_FILE)
        st.success("Initial HR policies created.")

    # Initial Beneficiaries Data (from prompt)
    initial_beneficiaries = {
        "Bestway Engineering Services Ltd": {"Account Name": "Benjamin", "Account No": "1234567890", "Bank": "GTB"},
        "Alpha Link Technical Services": {"Account Name": "Oladele", "Account No": "2345678900", "Bank": "Access Bank"},
        "AFLAC COM SPECs": {"Account Name": "Fasco", "Account No": "1234567890", "Bank": "Opay"},
        "Emmafem Resources Nig. Ent.": {"Account Name": "Radius", "Account No": "2345678901", "Bank": "UBA"},
        "Neptune Global Services": {"Account Name": "Folashade", "Account No": "12345678911", "Bank": "Union Bank"},
        "Other (Manually Enter Details)": {"Account Name": "", "Account No": "", "Bank": ""} # Option for manual entry
    }
    if not os.path.exists(BENEFICIARIES_FILE) or os.path.getsize(BENEFICIARIES_FILE) == 0:
        save_data(initial_beneficiaries, BENEFICIARIES_FILE)
        st.success("Initial Beneficiaries data created.")

# --- Session State Initialization ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state: # Stores full user object if logged in
    st.session_state.current_user = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "login"

# Load all persistent data into session state
st.session_state.users = load_data(USERS_FILE)
st.session_state.leave_requests = load_data(LEAVE_REQUESTS_FILE, [])
st.session_state.opex_capex_requests = load_data(OPEX_CAPEX_REQUESTS_FILE, [])
st.session_state.performance_goals = load_data(PERFORMANCE_GOALS_FILE, [])
st.session_state.self_appraisals = load_data(SELF_APPRAISALS_FILE, [])
st.session_state.payroll_data = load_data(PAYROLL_FILE, []) # New payroll data
st.session_state.beneficiaries = load_data(BENEFICIARIES_FILE, {}) # New beneficiaries data
st.session_state.hr_policies = load_data(HR_POLICIES_FILE, {}) # New policies data

# Ensure payroll data has necessary columns for DataFrame creation
# This handles cases where payroll.json might be empty or malformed initially
if not st.session_state.payroll_data:
    st.session_state.payroll_data = [] # Ensure it's an empty list if data is missing

# --- Common UI Elements ---
def display_logo():
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=150)
    else:
        st.error(f"Company logo not found at: {LOGO_PATH}")
        st.warning(f"Please ensure '{LOGO_FILE_NAME}' is in '{ICON_BASE_DIR}'.")

def display_sidebar():
    st.sidebar.image(LOGO_PATH, width=200)
    st.sidebar.title("Navigation")
    st.sidebar.markdown("---")

    # Dynamic sidebar based on user role
    if st.session_state.logged_in:
        st.sidebar.button("📊 Dashboard", key="nav_dashboard", on_click=lambda: st.session_state.update(current_page="dashboard"))
        st.sidebar.button("📝 My Profile", key="nav_my_profile", on_click=lambda: st.session_state.update(current_page="my_profile"))
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("My Applications")
        st.sidebar.button("🏖️ Apply for Leave", key="nav_apply_leave", on_click=lambda: st.session_state.update(current_page="leave_request"))
        st.sidebar.button("👀 View My Leave", key="nav_view_my_leave", on_click=lambda: st.session_state.update(current_page="view_my_leave")) # New
        st.sidebar.button("💲 OPEX/CAPEX Requisition", key="nav_submit_opex_capex", on_click=lambda: st.session_state.update(current_page="opex_capex_form"))
        st.sidebar.button("👀 View My OPEX/CAPEX", key="nav_view_my_opex_capex", on_click=lambda: st.session_state.update(current_page="view_my_opex_capex")) # New
        st.sidebar.button("📈 Performance Goal Setting", key="nav_performance_goals", on_click=lambda: st.session_state.update(current_page="performance_goal_setting"))
        st.sidebar.button("👀 View My Goals", key="nav_view_my_goals", on_click=lambda: st.session_state.update(current_page="view_my_goals")) # New
        st.sidebar.button("✍️ Self-Appraisal", key="nav_self_appraisal", on_click=lambda: st.session_state.update(current_page="self_appraisal"))
        st.sidebar.button("👀 View My Appraisals", key="nav_view_my_appraisals", on_click=lambda: st.session_state.update(current_page="view_my_appraisals")) # New
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("Company Resources")
        st.sidebar.button("📄 HR Policies", key="nav_hr_policies", on_click=lambda: st.session_state.update(current_page="hr_policies"))
        st.sidebar.button("💰 My Payslips", key="nav_my_payslips", on_click=lambda: st.session_state.update(current_page="my_payslips")) # New

        # Determine if the current user is an approver for OPEX/CAPEX or Leave
        is_approver = False
        current_user_profile = st.session_state.current_user.get('profile', {})
        current_user_department = current_user_profile.get('department')
        current_user_grade = current_user_profile.get('grade_level')

        # Check if the user's role/department/grade matches any of the approval chain roles
        if st.session_state.current_user['role'] == 'admin': # Admin can manage all
            is_approver = True
        else: # Check if the staff member is a manager in a department that is part of the approval chain
            for approver_role_info in APPROVAL_CHAIN:
                if (current_user_department == approver_role_info['department'] and
                        current_user_grade == approver_role_info['grade_level']):
                    is_approver = True
                    break

        # Show admin/approver functions conditionally
        if st.session_state.current_user and (st.session_state.current_user['role'] == 'admin' or is_approver):
            st.sidebar.markdown("---")
            st.sidebar.subheader("Admin & Approver Functions")
            if st.session_state.current_user['role'] == 'admin':
                st.sidebar.button("👥 Manage Users", key="admin_manage_users", on_click=lambda: st.session_state.update(current_page="manage_users")) # New
                st.sidebar.button("📤 Upload Payroll", key="admin_upload_payroll", on_click=lambda: st.session_state.update(current_page="upload_payroll")) # New
                st.sidebar.button("🏦 Manage Beneficiaries", key="admin_manage_beneficiaries", on_click=lambda: st.session_state.update(current_page="manage_beneficiaries")) # New
                st.sidebar.button("📜 Manage HR Policies", key="admin_manage_policies", on_click=lambda: st.session_state.update(current_page="manage_hr_policies")) # New
            
            # These buttons are visible to all eligible approvers (including admin)
            st.sidebar.button("✅ Manage OPEX/CAPEX Approvals", key="admin_manage_approvals", on_click=lambda: st.session_state.update(current_page="manage_opex_capex_approvals")) # New
            st.sidebar.button("✅ Manage Leave Approvals", key="admin_manage_leave_approvals", on_click=lambda: st.session_state.update(current_page="manage_leave_approvals")) # NEWLY ADDED

        st.sidebar.markdown("---")
        st.sidebar.button("Logout", key="nav_logout", on_click=logout)
    else:
        st.sidebar.info("Please log in to access the portal.")

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.current_page = "login"
    st.rerun()

# --- Login Form ---
def login_form():
    st.title("Polaris Digitech Staff Portal - Login")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username_input = st.text_input("User ID", key="login_username_input")
        password_input = st.text_input("Password", type="password", key="login_password_input")

        if st.button("Login", key="login_button"):
            found_user = None
            for user in st.session_state.users:
                # Check for both username and email (for admin login)
                if user['username'] == username_input:
                    if pbkdf2_sha256.verify(password_input, user['password']):
                        found_user = user
                        break
            
            if found_user:
                st.session_state.logged_in = True
                st.session_state.current_user = found_user
                st.success("Logged in successfully!")
                st.session_state.current_page = "dashboard"
                st.rerun()
            else:
                st.error("Invalid credentials")

# --- Dashboard Display ---
def display_dashboard():
    st.title("📊 Polaris Digitech HR Portal - Dashboard")

    if st.session_state.current_user:
        current_user_profile = st.session_state.current_user.get('profile', {})
        st.markdown(f"## Welcome, {current_user_profile.get('name', st.session_state.current_user['username']).title()}!")
        
        # Ensure staff_id is displayed from profile
        staff_id_display = current_user_profile.get('staff_id', 'N/A')
        st.write(f"Your Staff ID: **{staff_id_display}**")
        
        st.write(f"Department: **{current_user_profile.get('department', 'N/A')}**")

        st.markdown("---")
        st.subheader("Upcoming Birthdays")
        today = date.today()
        upcoming_birthdays = []
        for user in st.session_state.users:
            profile = user.get('profile', {})
            dob_str = profile.get('date_of_birth')
            name = profile.get('name')
            if dob_str and name:
                try:
                    dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    # Calculate birthday for current year
                    birthday_this_year = dob.replace(year=today.year)
                    # If birthday already passed this year, check next year
                    if birthday_this_year < today:
                        birthday_this_year = dob.replace(year=today.year + 1)
                    
                    days_until_birthday = (birthday_this_year - today).days

                    if 0 <= days_until_birthday <= 30: # Within next 30 days
                        upcoming_birthdays.append({
                            "Name": name,
                            "Birthday": birthday_this_year.strftime('%B %d'),
                            "Days Until": days_until_birthday
                        })
                except ValueError:
                    continue # Skip if DOB is malformed

        if upcoming_birthdays:
            df_birthdays = pd.DataFrame(upcoming_birthdays).sort_values(by="Days Until")
            st.dataframe(df_birthdays, use_container_width=True, hide_index=True)
            if any(b['Days Until'] == 0 for b in upcoming_birthdays):
                st.balloons()
                st.success("🎉 Happy Birthday to our staff members today! 🎉")
        else:
            st.info("No upcoming birthdays in the next 30 days.")

        st.markdown("---")
        st.subheader("HR Analytics Overview")

        total_employees = len(st.session_state.users)
        st.metric("Total Employees", total_employees)

        # Staff Distribution by Department
        if st.session_state.users:
            departments = [user.get('profile', {}).get('department', 'Unassigned') for user in st.session_state.users]
            df_departments = pd.DataFrame(departments, columns=['Department'])
            dept_counts = df_departments['Department'].value_counts().reset_index()
            dept_counts.columns = ['Department', 'Count']
            fig_dept = px.pie(dept_counts, values='Count', names='Department', title='Staff Distribution by Department', hole=0.3)
            st.plotly_chart(fig_dept, use_container_width=True)

            # Staff Distribution by Gender
            genders = [user.get('profile', {}).get('gender', 'N/A') for user in st.session_state.users]
            df_genders = pd.DataFrame(genders, columns=['Gender'])
            gender_counts = df_genders['Gender'].value_counts().reset_index()
            gender_counts.columns = ['Gender', 'Count']
            fig_gender = px.pie(gender_counts, values='Count', names='Gender', title='Staff Distribution by Gender', hole=0.3)
            st.plotly_chart(fig_gender, use_container_width=True)
        else:
            st.info("No staff data to display distributions.")

        # Staff On Leave
        current_on_leave = 0
        today = date.today()
        for req in st.session_state.leave_requests:
            try:
                start_date = datetime.strptime(req.get('start_date', '1900-01-01'), '%Y-%m-%d').date()
                end_date = datetime.strptime(req.get('end_date', '1900-01-01'), '%Y-%m-%d').date()
                if start_date <= today <= end_date and req.get('status') == 'Approved':
                    current_on_leave += 1
            except ValueError:
                continue # Skip malformed date entries
        st.metric("Staff Currently On Leave (Approved)", current_on_leave)

        st.markdown("---")
        st.subheader("Your Pending Requests")
    # 🔔 Notify if current user is an approver on any pending requests
    current_user_profile = st.session_state.current_user.get('profile', {})
    current_user_department = current_user_profile.get('department')
    current_user_grade = current_user_profile.get('grade_level')
    
    pending_approver_tasks_count = 0
    
    for req in st.session_state.opex_capex_requests:
        # Determine the current approver role for this request
        current_stage_index = req.get('current_approval_stage', 0)
        if current_stage_index < len(APPROVAL_CHAIN):
            expected_approver_stage = APPROVAL_CHAIN[current_stage_index]
            
            # Check if the current user matches the expected approver for this stage
            is_current_approver = (
                current_user_department == expected_approver_stage['department'] and
                current_user_grade == expected_approver_stage['grade_level'] and
                req.get('final_status') == "Pending" # Ensure overall request is still pending
            )
            if is_current_approver:
                # Additional check to see if this specific stage is pending
                stage_status_key = f"status_{expected_approver_stage['role_name'].lower().replace(' ', '_')}"
                if req.get(stage_status_key) == "Pending":
                    pending_approver_tasks_count += 1

    # Check for pending leave requests for admin
    pending_leave_approvals_count = len([req for req in st.session_state.leave_requests if req.get('status') == 'Pending' and st.session_state.current_user['role'] == 'admin'])
    if pending_leave_approvals_count > 0:
        st.warning(f"🔔 You have {pending_leave_approvals_count} leave request(s) awaiting your approval.")
        pending_approver_tasks_count += pending_leave_approvals_count # Sum up all pending approvals


    if pending_approver_tasks_count > 0:
        st.warning(f"🔔 You have {pending_approver_tasks_count} pending approval task(s) in total.")

        
        user_pending_leave = [
            req for req in st.session_state.leave_requests 
            if req.get('staff_id') == current_user_profile.get('staff_id') and req.get('status') == 'Pending'
        ]
        user_pending_opex_capex = [
            req for req in st.session_state.opex_capex_requests 
            if req.get('requester_staff_id') == current_user_profile.get('staff_id') and req.get('final_status') == 'Pending'
        ]

        if user_pending_leave:
            st.info(f"You have {len(user_pending_leave)} pending leave requests.")
        if user_pending_opex_capex:
            st.info(f"You have {len(user_pending_opex_capex)} pending OPEX/CAPEX requests.")
        if not user_pending_leave and not user_pending_opex_capex and pending_approver_tasks_count == 0:
            st.info("You have no pending requests.")


    else:
        st.info("You have no pending requests.") # Changed from warning to info when no pending tasks
        # If no pending tasks for approver, still show user's own requests
        user_pending_leave = [
            req for req in st.session_state.leave_requests 
            if req.get('staff_id') == current_user_profile.get('staff_id') and req.get('status') == 'Pending'
        ]
        user_pending_opex_capex = [
            req for req in st.session_state.opex_capex_requests 
            if req.get('requester_staff_id') == current_user_profile.get('staff_id') and req.get('final_status') == 'Pending'
        ]

        if user_pending_leave:
            st.info(f"You have {len(user_pending_leave)} pending leave requests.")
        if user_pending_opex_capex:
            st.info(f"You have {len(user_pending_opex_capex)} pending OPEX/CAPEX requests.")
        if not user_pending_leave and not user_pending_opex_capex:
            st.info("You have no pending requests (either as requester or approver).")

    st.markdown("---")
    st.subheader("Quick Access: Your Applications")
    current_user_staff_id = current_user_profile.get('staff_id', 'N/A')

    # Display Your Leave History on Dashboard
    st.markdown("#### Your Leave Applications")
    user_leave_history = [
        req for req in st.session_state.leave_requests
        if req.get('staff_id') == current_user_staff_id # Use the corrected staff ID
    ]
    if user_leave_history:
        df_leave = pd.DataFrame(user_leave_history)
        df_leave_display = df_leave[['submission_date', 'leave_type', 'start_date', 'end_date', 'num_days', 'status']]
        st.dataframe(df_leave_display, use_container_width=True, hide_index=True)
    else:
        st.info("You have not submitted any leave requests yet.")
    st.button("View All My Leave Applications", key="dashboard_view_all_leave", on_click=lambda: st.session_state.update(current_page="view_my_leave"))

    st.markdown("#### Your OPEX/CAPEX Requisitions")
    user_opex_capex_history = [
        req for req in st.session_state.opex_capex_requests
        if req.get('requester_staff_id') == current_user_staff_id # Use the corrected staff ID
    ]
    if user_opex_capex_history:
        df_opex_capex = pd.DataFrame(user_opex_capex_history)
        display_cols = [
            'submission_date', 'request_type', 'item_description', 'expense_line',
            'material_cost', 'labor_cost', 'total_amount', 'wht_percentage',
            'wht_amount', 'net_amount_payable', 'budget_balance',
            'final_status'
        ]
        # Add individual stage statuses if they exist and are relevant
        for stage in APPROVAL_CHAIN:
            display_cols.append(f"status_{stage['role_name'].lower().replace(' ', '_')}")
            
        # Filter for only existing columns to prevent errors if older entries don't have new fields
        existing_cols = [col for col in display_cols if col in df_opex_capex.columns]
        st.dataframe(df_opex_capex[existing_cols], use_container_width=True, hide_index=True)
    else:
        st.info("You have not submitted any OPEX/CAPEX requisitions yet.")
    st.button("View All My OPEX/CAPEX Requisitions", key="dashboard_view_all_opex_capex", on_click=lambda: st.session_state.update(current_page="view_my_opex_capex"))

# --- My Profile Display ---
def display_my_profile():
    st.title("📝 My Profile")
    user_profile = st.session_state.current_user.get('profile', {})
    
    if user_profile:
        st.subheader("Personal Information")
        st.write(f"**Name:** {user_profile.get('name')}")
        st.write(f"**Staff ID:** {user_profile.get('staff_id')}")
        st.write(f"**Date of Birth:** {user_profile.get('date_of_birth')}")
        st.write(f"**Gender:** {user_profile.get('gender')}")
        st.write(f"**Address:** {user_profile.get('address')}")
        st.write(f"**Phone Number:** {user_profile.get('phone_number')}")
        st.write(f"**Email Address:** {user_profile.get('email_address')}")

        st.subheader("Employment Details")
        st.write(f"**Department:** {user_profile.get('department')}")
        st.write(f"**Grade Level:** {user_profile.get('grade_level')}")
        st.write(f"**Work Anniversary:** {user_profile.get('work_anniversary')}")
        
        st.subheader("Education & Experience")
        st.write(f"**Education Background:** {user_profile.get('education_background')}")
        st.write(f"**Professional Experience:** {user_profile.get('professional_experience')}")

        st.subheader("Training Attended")
        if user_profile.get('training_attended'):
            for i, training in enumerate(user_profile['training_attended']):
                st.write(f"- {training}")
        else:
            st.info("No training records found.")
    else:
        st.error("User profile not found.")

# --- Leave Request Form ---
def leave_request_form():
    st.title("🏖️ Apply for Leave")
    current_user_profile = st.session_state.current_user.get('profile', {})
    requester_name = current_user_profile.get('name', 'N/A')
    requester_staff_id = current_user_profile.get('staff_id', 'N/A')

    st.write(f"Requesting as: **{requester_name}** (Staff ID: **{requester_staff_id}**)")

    with st.form("leave_request_form", clear_on_submit=True):
        leave_type = st.selectbox("Leave Type", ["Annual Leave", "Sick Leave", "Maternity Leave", "Paternity Leave", "Compassionate Leave", "Study Leave", "Unpaid Leave"])
        start_date = st.date_input("Start Date", date.today())
        end_date = st.date_input("End Date", date.today() + timedelta(days=7))
        reason = st.text_area("Reason for Leave", "e.g., Annual vacation, Medical appointment, Family emergency.")
        
        uploaded_file = st.file_uploader("Upload Supporting Document (Optional)", type=["pdf", "jpg", "png"], key="leave_doc_uploader")

        submitted = st.form_submit_button("Submit Leave Request")

        if submitted:
            if start_date > end_date:
                st.error("End Date cannot be before Start Date.")
            else:
                num_days = (end_date - start_date).days + 1
                new_request_id = f"LEAVE-{len(st.session_state.leave_requests) + 1:04d}"
                
                file_path = save_uploaded_file(uploaded_file, "leave_documents") if uploaded_file else None

                new_request = {
                    "request_id": new_request_id,
                    "staff_id": requester_staff_id,
                    "requester_name": requester_name,
                    "leave_type": leave_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "num_days": num_days,
                    "reason": reason,
                    "document_path": file_path,
                    "submission_date": datetime.now().isoformat(),
                    "status": "Pending", # Initial status
                    "admin_comment": "" # To be filled by admin
                }
                st.session_state.leave_requests.append(new_request)
                save_data(st.session_state.leave_requests, LEAVE_REQUESTS_FILE)
                st.success("Leave request submitted successfully! It is now pending approval.")
                st.rerun()

# --- View My Leave Requests ---
def view_my_leave_requests():
    st.title("👀 My Leave Applications")
    current_user_staff_id = st.session_state.current_user.get('profile', {}).get('staff_id')

    user_leave_requests = [
        req for req in st.session_state.leave_requests
        if req.get('staff_id') == current_user_staff_id
    ]

    if user_leave_requests:
        df_leave = pd.DataFrame(user_leave_requests)
        df_leave_display = df_leave[['request_id', 'submission_date', 'leave_type', 'start_date', 'end_date', 'num_days', 'status', 'reason']]
        st.dataframe(df_leave_display, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Request Details and Documents")
        selected_request_id = st.selectbox("Select a Request to View Details", [req['request_id'] for req in user_leave_requests])
        
        if selected_request_id:
            selected_request = next((req for req in user_leave_requests if req['request_id'] == selected_request_id), None)
            if selected_request:
                st.json(selected_request)
                if selected_request.get('document_path') and os.path.exists(selected_request['document_path']):
                    st.write("### Supporting Document:")
                    with open(selected_request['document_path'], "rb") as file:
                        btn = st.download_button(
                            label="Download Document",
                            data=file,
                            file_name=os.path.basename(selected_request['document_path']),
                            mime="application/octet-stream"
                        )
                else:
                    st.info("No supporting document uploaded for this request.")
    else:
        st.info("You have not submitted any leave requests yet.")


# --- OPEX/CAPEX Requisition Form ---
def opex_capex_form():
    st.title("💲 OPEX/CAPEX Requisition")
    current_user_profile = st.session_state.current_user.get('profile', {})
    requester_name = current_user_profile.get('name', 'N/A')
    requester_staff_id = current_user_profile.get('staff_id', 'N/A')
    requester_department = current_user_profile.get('department', 'N/A')

    st.write(f"Requesting as: **{requester_name}** (Staff ID: **{requester_staff_id}**)")
    st.write(f"Department: **{requester_department}**")

    # Load beneficiaries for the dropdown
    beneficiary_options = list(st.session_state.beneficiaries.keys())
    # Add an option for manual entry if it's not already there
    if "Other (Manually Enter Details)" not in beneficiary_options:
        beneficiary_options.append("Other (Manually Enter Details)")


    with st.form("opex_capex_form", clear_on_submit=True):
        request_type = st.selectbox("Request Type", ["OPEX (Operating Expenditure)", "CAPEX (Capital Expenditure)"])
        item_description = st.text_area("Item/Service Description", help="e.g., Purchase of new server, Office furniture repair, Consulting services")

        # NEW: Expense Line dropdown and Budgeted Amount display
        expense_line_options = ["Select an Expense Line"] + sorted(list(EXPENSE_LINES_BUDGET.keys()))
        selected_expense_line = st.selectbox("Expense Line", expense_line_options)

        budgeted_amount = 0.0
        if selected_expense_line != "Select an Expense Line":
            budgeted_amount = EXPENSE_LINES_BUDGET.get(selected_expense_line, 0.0)
            st.info(f"Budgeted Amount for '{selected_expense_line}': ₦{budgeted_amount:,.2f}")
        else:
            st.warning("Please select an Expense Line to see the budgeted amount.")
        
        st.markdown("---")
        st.subheader("Cost Breakdown")
        col_mat, col_lab = st.columns(2)
        with col_mat:
            material_cost = st.number_input("Material Cost (₦)", min_value=0.0, format="%.2f")
        with col_lab:
            labor_cost = st.number_input("Labor Cost (₦)", min_value=0.0, format="%.2f")

        total_amount = material_cost + labor_cost
        st.markdown(f"**Total Amount: ₦{total_amount:,.2f}**")

        # NEW: WHT and Net Amount Payable
        wht_options = {"0%": 0.0, "5%": 0.05, "10%": 0.10, "15%": 0.15}
        selected_wht_label = st.selectbox("Withholding Tax (WHT) on Labor Cost", list(wht_options.keys()), index=0)
        wht_percentage = wht_options[selected_wht_label]
        
        wht_amount = labor_cost * wht_percentage
        net_amount_payable = total_amount - wht_amount

        st.info(f"WHT Amount ({selected_wht_label} of Labor Cost): ₦{wht_amount:,.2f}")
        st.success(f"**Net Amount Payable: ₦{net_amount_payable:,.2f}**")

        # NEW: Budget Balance
        budget_balance = budgeted_amount - net_amount_payable
        if selected_expense_line != "Select an Expense Line":
            st.metric("Budget Balance", f"₦{budget_balance:,.2f}")
            if budget_balance < 0:
                st.error("Warning: This request exceeds the budgeted amount for the selected Expense Line!")
        else:
            st.info("Select an Expense Line to see the budget balance.")
        st.markdown("---")


        justification = st.text_area("Justification/Purpose of Request", help="Clearly explain why this item/service is needed and its benefit.")

        st.subheader("Vendor Details")
        selected_beneficiary_name = st.selectbox("Select Vendor/Beneficiary", beneficiary_options)
        
        vendor_name = ""
        vendor_account_name = ""
        vendor_account_no = ""
        vendor_bank = ""

        if selected_beneficiary_name == "Other (Manually Enter Details)":
            vendor_name = st.text_input("Vendor Name (as on invoice/account)", key="manual_vendor_name")
            vendor_account_name = st.text_input("Vendor Account Name", key="manual_account_name")
            vendor_account_no = st.text_input("Vendor Account Number", key="manual_account_no")
            vendor_bank = st.text_input("Vendor Bank Name", key="manual_bank_name")
        elif selected_beneficiary_name: # A pre-defined beneficiary was selected
            vendor_details = st.session_state.beneficiaries.get(selected_beneficiary_name, {})
            vendor_name = selected_beneficiary_name
            vendor_account_name = vendor_details.get("Account Name", "")
            vendor_account_no = vendor_details.get("Account No", "")
            vendor_bank = vendor_details.get("Bank", "")
            st.text_input("Vendor Account Name", value=vendor_account_name, disabled=True)
            st.text_input("Vendor Account Number", value=vendor_account_no, disabled=True)
            st.text_input("Vendor Bank Name", value=vendor_bank, disabled=True)


        uploaded_invoice = st.file_uploader("Upload Invoice/Quotation (PDF, JPG, PNG)", type=["pdf", "jpg", "png"], key="opex_capex_doc_uploader")

        submitted = st.form_submit_button("Submit Requisition")

        if submitted:
            if not item_description or total_amount <= 0 or not justification or not vendor_name or not vendor_account_name or not vendor_account_no or not vendor_bank:
                st.error("Please fill in all required fields and ensure Total Amount is greater than zero.")
            elif selected_expense_line == "Select an Expense Line":
                st.error("Please select an Expense Line.")
            else:
                new_request_id = f"REQ-{len(st.session_state.opex_capex_requests) + 1:04d}"
                file_path = save_uploaded_file(uploaded_invoice, "opex_capex_documents") if uploaded_invoice else None

                # Initialize approval statuses for each stage to "Pending"
                approval_statuses = {f"status_{stage['role_name'].lower().replace(' ', '_')}": "Pending" for stage in APPROVAL_CHAIN}

                new_request = {
                    "request_id": new_request_id,
                    "requester_staff_id": requester_staff_id,
                    "requester_name": requester_name,
                    "requester_department": requester_department,
                    "request_type": request_type,
                    "item_description": item_description,
                    "expense_line": selected_expense_line, # NEW
                    "budgeted_amount": budgeted_amount, # NEW
                    "material_cost": material_cost, # NEW
                    "labor_cost": labor_cost, # NEW
                    "total_amount": total_amount,
                    "wht_percentage": selected_wht_label, # NEW
                    "wht_amount": wht_amount, # NEW
                    "net_amount_payable": net_amount_payable, # NEW
                    "budget_balance": budget_balance, # NEW
                    "justification": justification,
                    "vendor_name": vendor_name,
                    "vendor_account_name": vendor_account_name,
                    "vendor_account_no": vendor_account_no,
                    "vendor_bank": vendor_bank,
                    "document_path": file_path,
                    "submission_date": datetime.now().isoformat(),
                    "current_approval_stage": 0, # Index of the current approver in APPROVAL_CHAIN
                    "approval_history": [], # To log who approved/rejected when
                    "final_status": "Pending", # Overall status of the request
                    **approval_statuses # Unpack initial pending statuses for each stage
                }
                st.session_state.opex_capex_requests.append(new_request)
                save_data(st.session_state.opex_capex_requests, OPEX_CAPEX_REQUESTS_FILE)
                st.success("OPEX/CAPEX requisition submitted successfully! It is now pending approval.")
                st.rerun()

# --- View My OPEX/CAPEX Requisitions ---
def view_my_opex_capex_requests():
    st.title("📄 My OPEX/CAPEX Requests")

    current_user_username = st.session_state.current_user['username']
    my_requests = [
        req for req in st.session_state.opex_capex_requests
        if req.get('requester_username') == current_user_username
    ]

    if not my_requests:
        st.info("You have not submitted any OPEX/CAPEX requests yet.")
        return

    # Prepare data for DataFrame, including deriving 'current_approver_role'
    requests_for_df = []
    for req in my_requests:
        # Get the current approval stage index
        current_stage_index = req.get('current_approval_stage', 0)
        
        # Determine the current approver's role name
        current_approver_role_name = "N/A"
        if req.get('final_status') == 'Pending' and current_stage_index < len(APPROVAL_CHAIN):
            current_approver_role_name = APPROVAL_CHAIN[current_stage_index]['role_name']
        elif req.get('final_status') in ["Approved", "Rejected"]:
            current_approver_role_name = "Finalized" # Or a more appropriate status

        requests_for_df.append({
            'request_id': req.get('request_id'),
            'submission_date': req.get('submission_date'),
            'request_type': req.get('request_type'),
            'item_description': req.get('item_description'),
            'total_amount': req.get('total_amount'),
            'final_status': req.get('final_status', 'Pending'),
            'current_approver_role': current_approver_role_name, # Derived column
            'document_path': req.get('document_path') # Include document path for download
        })

    df_my_requests = pd.DataFrame(requests_for_df)

    # Convert submission_date to datetime objects for proper sorting and display
    if 'submission_date' in df_my_requests.columns:
        df_my_requests['submission_date'] = pd.to_datetime(df_my_requests['submission_date'], errors='coerce').dt.date

    # Convert relevant numeric columns to string for display to avoid ArrowInvalid
    numeric_cols_to_string = [
        'total_amount'
    ]
    for col in numeric_cols_to_string:
        if col in df_my_requests.columns:
            df_my_requests[col] = df_my_requests[col].apply(lambda x: f"NGN {x:,.2f}" if pd.notna(x) else 'N/A')


    st.dataframe(df_my_requests[[
        'request_id', 'submission_date', 'request_type', 'item_description',
        'total_amount', 'final_status', 'current_approver_role'
    ]], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("View/Download Request Details")
    
    # Ensure options for selectbox are only valid string request IDs
    selected_request_id = st.selectbox(
        "Select a request to view details or download PDF:",
        options=[""] + [req['request_id'] for req in requests_for_df if req.get('request_id')],
        key="select_my_opex_capex_request"
    )

    if selected_request_id:
        selected_request = next((req for req in my_requests if req.get('request_id') == selected_request_id), None)

        if selected_request:
            st.markdown("---")
            st.subheader(f"Details for Request: {selected_request_id}")
            
            # Display all request details in a readable format
            st.write(f"**Request ID:** {selected_request.get('request_id', 'N/A')}")
            st.write(f"**Submission Date:** {selected_request.get('submission_date', 'N/A')}")
            st.write(f"**Request Type:** {selected_request.get('request_type', 'N/A')}")
            st.write(f"**Item Description:** {selected_request.get('item_description', 'N/A')}")
            st.write(f"**Expense Line:** {selected_request.get('expense_line', 'N/A')}")
            st.write(f"**Budgeted Amount:** NGN {selected_request.get('budgeted_amount', 0):,.2f}")
            st.write(f"**Material Cost:** NGN {selected_request.get('material_cost', 0):,.2f}")
            st.write(f"**Labor Cost:** NGN {selected_request.get('labor_cost', 0):,.2f}")
            st.write(f"**Total Amount:** NGN {selected_request.get('total_amount', 0):,.2f}")
            st.write(f"**WHT Percentage:** {selected_request.get('wht_percentage', 0)}%")
            st.write(f"**WHT Amount:** NGN {selected_request.get('wht_amount', 0):,.2f}")
            st.write(f"**Net Amount Payable:** NGN {selected_request.get('net_amount_payable', 0):,.2f}")
            st.write(f"**Budget Balance (After Request):** NGN {selected_request.get('budget_balance', 0):,.2f}")
            st.write(f"**Justification:** {selected_request.get('justification', 'N/A')}")
            st.write(f"**Vendor Name:** {selected_request.get('vendor_name', 'N/A')}")
            st.write(f"**Vendor Account Name:** {selected_request.get('vendor_account_name', 'N/A')}")
            st.write(f"**Vendor Account No:** {selected_request.get('vendor_account_no', 'N/A')}")
            st.write(f"**Vendor Bank:** {selected_request.get('vendor_bank', 'N/A')}")
            st.write(f"**Current Status:** **{selected_request.get('final_status', 'Pending')}**")
            
            # Display current approver role if not finalized
            if selected_request.get('final_status') == 'Pending':
                current_stage_idx = selected_request.get('current_approval_stage', 0)
                if current_stage_idx < len(APPROVAL_CHAIN):
                    current_approver_info = APPROVAL_CHAIN[current_stage_idx]
                    st.write(f"**Next Approver:** {current_approver_info['role_name']} ({current_approver_info['department']} - {current_approver_info['grade_level']})")
                else:
                    st.write("**Next Approver:** Awaiting final review/processing (beyond defined chain)")
            else:
                st.write(f"**Approval Process:** {selected_request.get('final_status')}")

            # Display approval history
            st.subheader("Approval History")
            if selected_request.get('approval_history'):
                for entry in selected_request['approval_history']:
                    st.write(f"- **{entry.get('approver_role')}** by **{entry.get('approver_name')}** on **{entry.get('date')}**: **{entry.get('status')}**. Comment: {entry.get('comment', 'No comment.')}")
            else:
                st.info("No approval history for this request yet.")

            # Download PDF button
            if selected_request.get('pdf_path') and os.path.exists(selected_request['pdf_path']):
                with open(selected_request['pdf_path'], "rb") as pdf_file:
                    st.download_button(
                        label="Download OPEX/CAPEX Request PDF",
                        data=pdf_file.read(),
                        file_name=os.path.basename(selected_request['pdf_path']),
                        mime="application/pdf",
                        key=f"download_opex_capex_pdf_{selected_request_id}"
                    )
            else:
                st.info("PDF not yet generated or found for this request.")

            # Display attached document if any
            if selected_request.get('document_path') and os.path.exists(selected_request['document_path']):
                st.download_button(
                    label=f"Download Attached Document: {os.path.basename(selected_request['document_path'])}",
                    data=open(selected_request['document_path'], "rb").read(),
                    file_name=os.path.basename(selected_request['document_path']),
                    mime="application/octet-stream",
                    key=f"download_doc_{selected_request_id}"
                )
            else:
                st.info("No attached document for this request.")
        else:
            st.warning("Selected request not found.")

# --- Performance Goal Setting ---
def performance_goal_setting():
    st.title("📈 Performance Goal Setting")
    if st.session_state.logged_in and st.session_state.current_user:
        current_user_profile = st.session_state.current_user.get('profile', {})
        employee_name = current_user_profile.get('name', st.session_state.current_user['username'])
        employee_staff_id = current_user_profile.get('staff_id', 'N/A')

        st.write(f"**Setting goals for:** {employee_name} (Staff ID: {employee_staff_id})")

        with st.form("goal_setting_form", clear_on_submit=True):
            goal_period = st.selectbox("Goal Period", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "Annual 2024"])
            goal_category = st.selectbox("Goal Category", ["Individual Performance", "Team Contribution", "Professional Development", "Innovation"])
            goal_description = st.text_area("Goal Description (SMART: Specific, Measurable, Achievable, Relevant, Time-bound)", max_chars=1000)
            target_metric = st.text_input("Target Metric (e.g., 'Increase sales by 10%', 'Complete 2 certifications')")
            due_date = st.date_input("Due Date", min_value=date.today())
            submit_button = st.form_submit_button("Set Goal")

            if submit_button:
                if not goal_description or not target_metric:
                    st.error("Please fill in all required goal details.")
                else:
                    goal_id = f"GOAL-{len(st.session_state.performance_goals) + 1:04d}"
                    new_goal = {
                        "goal_id": goal_id,
                        "staff_id": employee_staff_id,
                        "employee_name": employee_name,
                        "goal_period": goal_period,
                        "goal_category": goal_category,
                        "goal_description": goal_description,
                        "target_metric": target_metric,
                        "due_date": due_date.isoformat(),
                        "set_date": datetime.now().isoformat(),
                        "status": "Active", # Active, Completed, Overdue, Cancelled
                        "achieved_progress": "",
                        "manager_comment": ""
                    }
                    st.session_state.performance_goals.append(new_goal)
                    save_data(st.session_state.performance_goals, PERFORMANCE_GOALS_FILE)
                    st.success(f"Performance goal '{goal_id}' set successfully!")
                    st.rerun()
    else:
        st.warning("Please log in to set performance goals.")

# --- Performance Goal Setting ---
def performance_goal_setting():
    st.title("📈 Performance Goal Setting")
    current_user_profile = st.session_state.current_user.get('profile', {})
    staff_id = current_user_profile.get('staff_id', 'N/A')
    staff_name = current_user_profile.get('name', 'N/A')

    st.write(f"Setting goals for: **{staff_name}** (Staff ID: **{staff_id}**)")

    with st.form("goal_setting_form", clear_on_submit=True):
        goal_title = st.text_input("Goal Title", help="e.g., Improve customer satisfaction, Reduce operational costs")
        goal_description = st.text_area("Goal Description", help="Provide a detailed explanation of the goal.")
        target_metric = st.text_input("Target Metric", help="e.g., 90% customer satisfaction rating, 15% cost reduction")
        due_date = st.date_input("Due Date", date.today() + timedelta(days=90))
        
        submitted = st.form_submit_button("Set Goal")

        if submitted:
            if not goal_title or not goal_description or not target_metric:
                st.error("Please fill in all required fields.")
            else:
                new_goal = {
                    "goal_id": f"GOAL-{len(st.session_state.performance_goals) + 1:04d}",
                    "staff_id": staff_id,
                    "staff_name": staff_name,
                    "goal_title": goal_title,
                    "goal_description": goal_description,
                    "target_metric": target_metric,
                    "due_date": due_date.isoformat(),
                    "status": "Active", # Active, Completed, On Hold, Canceled
                    "set_date": datetime.now().isoformat(),
                    "progress_notes": []
                }
                st.session_state.performance_goals.append(new_goal)
                save_data(st.session_state.performance_goals, PERFORMANCE_GOALS_FILE)
                st.success("Performance goal set successfully!")
                st.rerun()

# --- View My Goals ---
def view_my_goals():
    st.title("👀 My Performance Goals")
    current_user_staff_id = st.session_state.current_user.get('profile', {}).get('staff_id')

    user_goals = [
        goal for goal in st.session_state.performance_goals
        if goal.get('staff_id') == current_user_staff_id
    ]

    if user_goals:
        df_goals = pd.DataFrame(user_goals)
        df_goals_display = df_goals[['goal_id', 'set_date', 'goal_title', 'target_metric', 'due_date', 'status']]
        st.dataframe(df_goals_display, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Goal Details and Progress Update")
        selected_goal_id = st.selectbox("Select a Goal to View/Update", [goal['goal_id'] for goal in user_goals])

        if selected_goal_id:
            selected_goal_index = next((i for i, goal in enumerate(user_goals) if goal['goal_id'] == selected_goal_id), None)
            if selected_goal_index is not None:
                selected_goal = user_goals[selected_goal_index]
                
                st.write(f"**Goal Title:** {selected_goal.get('goal_title')}")
                st.write(f"**Description:** {selected_goal.get('goal_description')}")
                st.write(f"**Target Metric:** {selected_goal.get('target_metric')}")
                st.write(f"**Due Date:** {selected_goal.get('due_date')}")
                st.write(f"**Status:** {selected_goal.get('status')}")

                st.markdown("##### Progress Notes:")
                if selected_goal.get('progress_notes'):
                    for note_entry in selected_goal['progress_notes']:
                        st.write(f"- {note_entry.get('date')}: {note_entry.get('note')}")
                else:
                    st.info("No progress notes yet.")

                st.markdown("---")
                st.subheader("Add Progress Note")
                new_note = st.text_area("New Progress Note", key=f"progress_note_{selected_goal_id}")
                
                # Use a unique key for the status selectbox
                new_status = st.selectbox(
                    "Update Status", 
                    ["Active", "Completed", "On Hold", "Canceled"], 
                    index=["Active", "Completed", "On Hold", "Canceled"].index(selected_goal.get('status')),
                    key=f"status_update_{selected_goal_id}"
                )

                if st.button("Update Goal Progress", key=f"update_goal_btn_{selected_goal_id}"):
                    if new_note:
                        selected_goal['progress_notes'].append({
                            "date": datetime.now().isoformat(),
                            "note": new_note
                        })
                    selected_goal['status'] = new_status
                    
                    # Update the original list in session state
                    for i, goal in enumerate(st.session_state.performance_goals):
                        if goal['goal_id'] == selected_goal_id:
                            st.session_state.performance_goals[i] = selected_goal
                            break
                    save_data(st.session_state.performance_goals, PERFORMANCE_GOALS_FILE)
                    st.success("Goal updated successfully!")
                    st.rerun()
    else:
        st.info("You have not set any performance goals yet.")

# --- Self-Appraisal Form ---
def self_appraisal_form():
    st.title("✍️ Self-Appraisal")
    current_user_profile = st.session_state.current_user.get('profile', {})
    staff_id = current_user_profile.get('staff_id', 'N/A')
    staff_name = current_user_profile.get('name', 'N/A')

    st.write(f"Appraisal for: **{staff_name}** (Staff ID: **{staff_id}**)")

    # Fetch user's goals for reference
    user_goals = [
        goal for goal in st.session_state.performance_goals
        if goal.get('staff_id') == staff_id
    ]

    if not user_goals:
        st.warning("You currently have no performance goals set. Please set some goals before completing an appraisal.")
        return

    st.markdown("---")
    st.subheader("Appraisal Period")
    appraisal_period_start = st.date_input("Appraisal Period Start Date", value=date.today().replace(month=1, day=1), key="appraisal_start_date")
    appraisal_period_end = st.date_input("Appraisal Period End Date", value=date.today(), key="appraisal_end_date")

    st.markdown("---")
    st.subheader("Goal-Based Appraisal")
    st.info("Please review your performance against your set goals.")

    appraisal_goals = []
    for goal in user_goals:
        st.markdown(f"**Goal Title:** {goal.get('goal_title')}")
        st.write(f"**Description:** {goal.get('goal_description')}")
        st.write(f"**Target Metric:** {goal.get('target_metric')}")
        st.write(f"**Due Date:** {goal.get('due_date')}")
        st.write(f"**Current Status:** {goal.get('status')}")
        
        achieved = st.radio(f"Achieved for '{goal.get('goal_title')}'?", ["Fully Achieved", "Partially Achieved", "Not Achieved"], key=f"achieved_{goal.get('goal_id')}")
        self_assessment = st.text_area(f"Self-Assessment for '{goal.get('goal_title')}'", key=f"assessment_{goal.get('goal_id')}", 
                                       help="Describe your contributions and outcomes related to this goal.")
        
        appraisal_goals.append({
            "goal_id": goal.get('goal_id'),
            "goal_title": goal.get('goal_title'),
            "achieved_status": achieved,
            "self_assessment": self_assessment
        })
        st.markdown("---")

    st.subheader("Overall Self-Assessment")
    overall_strengths = st.text_area("Key Strengths & Contributions during this period", help="What did you do well? Where did you make the most impact?")
    overall_improvements = st.text_area("Areas for Development & Training Needs", help="What areas do you need to improve? What training would help?")
    future_aspirations = st.text_area("Future Aspirations & Career Growth", help="What are your career goals? How can the company support you?")

    with st.form("self_appraisal_submit_form", clear_on_submit=True):
        submitted = st.form_submit_button("Submit Self-Appraisal")

        if submitted:
            if not overall_strengths or not overall_improvements or not future_aspirations:
                st.error("Please fill in all overall self-assessment sections.")
            else:
                new_appraisal = {
                    "appraisal_id": f"APP-{len(st.session_state.self_appraisals) + 1:04d}",
                    "staff_id": staff_id,
                    "staff_name": staff_name,
                    "appraisal_date": datetime.now().isoformat(),
                    "appraisal_period_start": appraisal_period_start.isoformat(),
                    "appraisal_period_end": appraisal_period_end.isoformat(),
                    "goal_appraisals": appraisal_goals,
                    "overall_strengths": overall_strengths,
                    "overall_improvements": overall_improvements,
                    "future_aspirations": future_aspirations,
                    "manager_feedback": "", # To be filled by manager
                    "final_rating": "" # To be filled by manager
                }
                st.session_state.self_appraisals.append(new_appraisal)
                save_data(st.session_state.self_appraisals, SELF_APPRAISALS_FILE)
                st.success("Self-appraisal submitted successfully!")
                st.rerun()

# --- View My Appraisals ---
def view_my_appraisals():
    st.title("👀 My Self-Appraisals")
    current_user_staff_id = st.session_state.current_user.get('profile', {}).get('staff_id')

    user_appraisals = [
        app for app in st.session_state.self_appraisals
        if app.get('staff_id') == current_user_staff_id
    ]

    if user_appraisals:
        df_appraisals = pd.DataFrame(user_appraisals)
        df_appraisals_display = df_appraisals[['appraisal_id', 'appraisal_date', 'appraisal_period_start', 'appraisal_period_end', 'final_rating']]
        st.dataframe(df_appraisals_display, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Appraisal Details")
        selected_appraisal_id = st.selectbox("Select an Appraisal to View Details", [app['appraisal_id'] for app in user_appraisals])
        
        if selected_appraisal_id:
            selected_appraisal = next((app for app in user_appraisals if app['appraisal_id'] == selected_appraisal_id), None)
            if selected_appraisal:
                st.json(selected_appraisal) # Display full JSON for now for comprehensive view
    else:
        st.info("You have not submitted any self-appraisals yet.")

# --- My Payslips ---
def my_payslips():
    st.title("💰 My Payslips")
    current_user_staff_id = st.session_state.current_user.get('profile', {}).get('staff_id')

    # Filter payroll data for the current user
    user_payslips = [
        payslip for payslip in st.session_state.payroll_data
        if payslip.get('staff_id') == current_user_staff_id
    ]

    if user_payslips:
        # Convert to DataFrame for display
        df_payslips = pd.DataFrame(user_payslips)
        # Select relevant columns for display
        display_cols = ['pay_period', 'gross_pay', 'net_pay', 'deductions', 'bonus', 'pay_date']
        
        # Ensure all display columns exist in the dataframe, add missing ones as 'N/A'
        for col in display_cols:
            if col not in df_payslips.columns:
                df_payslips[col] = 'N/A'

        st.dataframe(df_payslips[display_cols], use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Payslip Details (Full)")
        # Allow user to select a payslip for full details
        selected_pay_period = st.selectbox(
            "Select Pay Period to View Details",
            [ps.get('pay_period') for ps in user_payslips]
        )
        if selected_pay_period:
            selected_payslip = next(
                (ps for ps in user_payslips if ps.get('pay_period') == selected_pay_period),
                None
            )
            if selected_payslip:
                st.json(selected_payslip)
            else:
                st.info("No details found for the selected payslip.")
    else:
        st.info("No payslips available for your Staff ID yet.")
        st.info("Payslips are uploaded by HR/Admin.")


# --- HR Policies ---
def hr_policies():
    st.title("📄 HR Policies")

    if st.session_state.hr_policies:
        selected_policy_name = st.selectbox("Select a Policy", list(st.session_state.hr_policies.keys()))
        if selected_policy_name:
            st.subheader(selected_policy_name)
            st.write(st.session_state.hr_policies[selected_policy_name])
    else:
        st.info("No HR policies available yet. Please check back later.")
        if st.session_state.current_user and st.session_state.current_user['role'] == 'admin':
            st.info("As an Admin, you can add policies via 'Manage HR Policies' section.")

# --- Admin Functions ---

# Manage Users (Admin)
def admin_manage_users():
    st.title("👥 Admin: Manage Users")

    # Display current users
    st.subheader("Current Users")
    if st.session_state.users:
        df_users = pd.DataFrame(st.session_state.users)
        df_users_display = df_users.apply(lambda x: x.astype(str) if x.name == 'password' else x) # Convert password hash to string for display
        
        # Flatten profile dictionary for better display in dataframe
        user_data_flat = []
        for user in st.session_state.users:
            flat_user = {k: v for k, v in user.items() if k != 'profile'}
            flat_user.update(user.get('profile', {}))
            user_data_flat.append(flat_user)
        
        df_users_display = pd.DataFrame(user_data_flat)
        # Reorder columns to show important profile info first
        if not df_users_display.empty:
            cols = ['name', 'staff_id', 'username', 'role', 'department', 'grade_level', 'email_address', 'phone_number']
            existing_cols = [col for col in cols if col in df_users_display.columns]
            other_cols = [col for col in df_users_display.columns if col not in existing_cols and col != 'password']
            display_cols = existing_cols + other_cols
            st.dataframe(df_users_display[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No users registered yet.")

    st.markdown("---")
    st.subheader("Add New User")
    with st.form("add_user_form", clear_on_submit=True):
        new_username = st.text_input("Username (Email Address)", help="This will be the login ID.")
        new_password = st.text_input("Temporary Password", type="password")
        new_role = st.selectbox("Role", ["staff", "admin"])

        st.markdown("##### User Profile Details")
        profile_name = st.text_input("Full Name")
        profile_staff_id = st.text_input("Staff ID (e.g., POL/2024/XXX)")
        profile_dob = st.date_input("Date of Birth", value=date(2000, 1, 1))
        profile_gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        profile_grade_level = st.selectbox("Grade Level", ["Officer", "Manager", "MD", "Executive"])
        profile_department = st.text_input("Department")
        profile_education = st.text_input("Education Background")
        profile_experience = st.text_area("Professional Experience")
        profile_address = st.text_area("Address")
        profile_phone = st.text_input("Phone Number")
        profile_email = st.text_input("Email Address")
        profile_work_anniversary = st.date_input("Work Anniversary", value=date.today())

        add_user_submitted = st.form_submit_button("Add User")

        if add_user_submitted:
            if not new_username or not new_password or not profile_name or not profile_staff_id or not profile_department:
                st.error("Please fill in all mandatory fields (Username, Password, Full Name, Staff ID, Department).")
            elif any(user['username'] == new_username for user in st.session_state.users):
                st.error("Username already exists. Please choose a different one.")
            else:
                new_user_obj = {
                    "username": new_username,
                    "password": pbkdf2_sha256.hash(new_password),
                    "role": new_role,
                    "profile": {
                        "name": profile_name,
                        "staff_id": profile_staff_id,
                        "date_of_birth": profile_dob.isoformat(),
                        "gender": profile_gender,
                        "grade_level": profile_grade_level,
                        "department": profile_department,
                        "education_background": profile_education,
                        "professional_experience": profile_experience,
                        "address": profile_address,
                        "phone_number": profile_phone,
                        "email_address": profile_email,
                        "training_attended": [], # Initialize as empty
                        "work_anniversary": profile_work_anniversary.isoformat()
                    }
                }
                st.session_state.users.append(new_user_obj)
                save_data(st.session_state.users, USERS_FILE)
                st.success(f"User '{new_username}' added successfully!")
                st.rerun()
    
    st.markdown("---")
    st.subheader("Edit / Delete User")
    user_to_modify = st.selectbox("Select User to Edit/Delete", [""] + [user['username'] for user in st.session_state.users], key="select_user_to_modify")
    
    if user_to_modify:
        selected_user = next((user for user in st.session_state.users if user['username'] == user_to_modify), None)
        if selected_user:
            with st.form("edit_delete_user_form", clear_on_submit=True):
                st.write(f"Editing User: **{selected_user['username']}**")
                
                # Pre-fill fields for editing
                edit_role = st.selectbox("Role", ["staff", "admin"], index=["staff", "admin"].index(selected_user['role']))
                
                st.markdown("##### User Profile Details")
                edit_profile_name = st.text_input("Full Name", value=selected_user['profile'].get('name', ''))
                edit_profile_staff_id = st.text_input("Staff ID", value=selected_user['profile'].get('staff_id', ''))
                
                # Handle date conversion for date_input default value
                try:
                    edit_profile_dob_val = datetime.strptime(selected_user['profile'].get('date_of_birth', '2000-01-01'), '%Y-%m-%d').date()
                except ValueError:
                    edit_profile_dob_val = date(2000, 1, 1) # Default if malformed
                edit_profile_dob = st.date_input("Date of Birth", value=edit_profile_dob_val)

                edit_profile_gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(selected_user['profile'].get('gender', 'Male')))
                edit_profile_grade_level = st.selectbox("Grade Level", ["Officer", "Manager", "MD", "Executive"], index=["Officer", "Manager", "MD", "Executive"].index(selected_user['profile'].get('grade_level', 'Officer')))
                edit_profile_department = st.text_input("Department", value=selected_user['profile'].get('department', ''))
                edit_profile_education = st.text_input("Education Background", value=selected_user['profile'].get('education_background', ''))
                edit_profile_experience = st.text_area("Professional Experience", value=selected_user['profile'].get('professional_experience', ''))
                edit_profile_address = st.text_area("Address", value=selected_user['profile'].get('address', ''))
                edit_profile_phone = st.text_input("Phone Number", value=selected_user['profile'].get('phone_number', ''))
                edit_profile_email = st.text_input("Email Address", value=selected_user['profile'].get('email_address', ''))
                
                try:
                    edit_profile_work_anniversary_val = datetime.strptime(selected_user['profile'].get('work_anniversary', str(date.today())), '%Y-%m-%d').date()
                except ValueError:
                    edit_profile_work_anniversary_val = date.today()
                edit_profile_work_anniversary = st.date_input("Work Anniversary", value=edit_profile_work_anniversary_val)

                col_edit_del = st.columns(2)
                with col_edit_del[0]:
                    edit_submitted = st.form_submit_button("Update User")
                with col_edit_del[1]:
                    delete_submitted = st.form_submit_button("Delete User")

                if edit_submitted:
                    for i, user in enumerate(st.session_state.users):
                        if user['username'] == user_to_modify:
                            st.session_state.users[i]['role'] = edit_role
                            st.session_state.users[i]['profile'] = {
                                "name": edit_profile_name,
                                "staff_id": edit_profile_staff_id,
                                "date_of_birth": edit_profile_dob.isoformat(),
                                "gender": edit_profile_gender,
                                "grade_level": edit_profile_grade_level,
                                "department": edit_profile_department,
                                "education_background": edit_profile_education,
                                "professional_experience": edit_profile_experience,
                                "address": edit_profile_address,
                                "phone_number": edit_profile_phone,
                                "email_address": edit_profile_email,
                                "training_attended": selected_user['profile'].get('training_attended', []), # Keep existing
                                "work_anniversary": edit_profile_work_anniversary.isoformat()
                            }
                            break
                    save_data(st.session_state.users, USERS_FILE)
                    st.success(f"User '{user_to_modify}' updated successfully!")
                    st.rerun()

                if delete_submitted:
                    st.session_state.users = [user for user in st.session_state.users if user['username'] != user_to_modify]
                    save_data(st.session_state.users, USERS_FILE)
                    st.warning(f"User '{user_to_modify}' deleted.")
                    st.rerun()


# Upload Payroll (Admin)
def admin_upload_payroll():
    st.title("📤 Admin: Upload Payroll Data")
    st.write("Upload a CSV file containing payroll information.")

    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df) # Display uploaded CSV for review

            required_cols = ['staff_id', 'pay_period', 'gross_pay', 'net_pay', 'deductions', 'bonus', 'pay_date']
            if not all(col in df.columns for col in required_cols):
                st.error(f"Missing required columns. Please ensure the CSV contains: {', '.join(required_cols)}")
                return

            if st.button("Process Payroll Upload"):
                new_payroll_entries = df.to_dict(orient='records')
                
                # Append new entries to existing payroll data, avoid duplicates if pay_period and staff_id match
                for new_entry in new_payroll_entries:
                    exists = False
                    for existing_entry in st.session_state.payroll_data:
                        if (existing_entry.get('staff_id') == new_entry.get('staff_id') and
                            existing_entry.get('pay_period') == new_entry.get('pay_period')):
                            exists = True
                            # Optionally, update existing entry instead of skipping
                            # existing_entry.update(new_entry) 
                            break
                    if not exists:
                        st.session_state.payroll_data.append(new_entry)

                save_data(st.session_state.payroll_data, PAYROLL_FILE)
                st.success("Payroll data uploaded and processed successfully!")
                st.rerun()

        except Exception as e:
            st.error(f"Error reading CSV file: {e}")

# Assuming FPDF and XPos, YPos are imported:
from fpdf import FPDF, XPos, YPos
import os # Ensure os module is imported for path handling

def generate_opex_capex_pdf(request_data):
    pdf = FPDF()
    pdf.add_page()

    # --- DEBUGGING FONT PATH ---
    # Print current working directory to help locate font files
    print(f"Current working directory: {os.getcwd()}")
    # --- END DEBUGGING ---

    # Define font file paths based on where you placed the .ttf files.
    # CHOOSE ONE OPTION BELOW AND UNCOMMENT IT. COMMENT OUT THE OTHER.

    # OPTION A: If you placed NotoSans-Regular.ttf and NotoSans-Bold.ttf
    # directly in the SAME DIRECTORY as your hr_app.py file:
    font_path_regular = 'NotoSans-Regular.ttf'
    font_path_bold = 'NotoSans-Bold.ttf'

    # OPTION B: If you placed them in a 'fonts' subdirectory within your DATA_DIR
    # (e.g., your_project_folder/hr_data/fonts/NotoSans-Regular.ttf):
    # Make sure DATA_DIR is defined globally in your script (e.g., DATA_DIR = "hr_data")
    # font_path_regular = os.path.join(DATA_DIR, 'fonts', 'NotoSans-Regular.ttf')
    # font_path_bold = os.path.join(DATA_DIR, 'fonts', 'NotoSans-Bold.ttf')


    default_font = 'Helvetica' # Fallback default
    
    try:
        # Check if the font files exist before adding them
        if os.path.exists(font_path_regular) and os.path.exists(font_path_bold):
            pdf.add_font('NotoSans', '', font_path_regular, uni=True)
            pdf.add_font('NotoSans', 'B', font_path_bold, uni=True)
            pdf.add_font('NotoSans', 'BU', font_path_bold, uni=True) # For bold and underline
            default_font = 'NotoSans'
        else:
            # If font files are not found, print a message to the console for debugging
            print(f"Warning: NotoSans font files not found at '{font_path_regular}' or '{font_path_bold}'. Falling back to Helvetica.")
            # No st.warning here, as it's for the app UI, not backend PDF generation
            default_font = 'Helvetica'
    except Exception as e:
        print(f"Error adding NotoSans font: {e}. Falling back to Helvetica.")
        default_font = 'Helvetica'

    # Set font for the entire document
    pdf.set_font(default_font, size=10)

    # Add a title
    pdf.set_font(default_font, 'B', 16)
    pdf.cell(0, 10, "OPEX/CAPEX Requisition Form", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(10) # Add some space

    # Set font for details
    pdf.set_font(default_font, size=10)

    # Define a consistent line height for multi_cell
    line_height = 6

    # Helper function to add key-value pairs
    def add_detail(key, value):
        pdf.set_font(default_font, 'B', 10)
        pdf.cell(50, line_height, f"{key}:", new_x=XPos.RIGHT) # Fixed width for key
        pdf.set_font(default_font, '', 10)
        available_width = pdf.w - pdf.l_margin - pdf.r_margin - 50 # 50 is key_cell_width
        pdf.multi_cell(available_width, line_height, str(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Request Details
    pdf.set_font(default_font, 'BU', 12)
    pdf.cell(0, 10, "Request Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    add_detail("Request ID", request_data.get('request_id', 'N/A'))
    add_detail("Submission Date", request_data.get('submission_date', 'N/A'))
    add_detail("Requester Name", request_data.get('requester_name', 'N/A'))
    add_detail("Requester Staff ID", request_data.get('requester_staff_id', 'N/A'))
    add_detail("Requester Department", request_data.get('requester_department', 'N/A'))
    add_detail("Request Type", request_data.get('request_type', 'N/A'))
    add_detail("Item Description", request_data.get('item_description', 'N/A'))
    add_detail("Expense Line", request_data.get('expense_line', 'N/A'))
    
    # Financial Details
    pdf.ln(5)
    pdf.set_font(default_font, 'BU', 12)
    pdf.cell(0, 10, "Financial Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Changed '₦' to 'NGN'
    add_detail("Budgeted Amount", f"NGN {request_data.get('budgeted_amount', 0):,.2f}")
    add_detail("Material Cost", f"NGN {request_data.get('material_cost', 0):,.2f}")
    add_detail("Labor Cost", f"NGN {request_data.get('labor_cost', 0):,.2f}")
    add_detail("Total Amount", f"NGN {request_data.get('total_amount', 0):,.2f}")
    add_detail("WHT Percentage", f"{request_data.get('wht_percentage', 0)}%")
    add_detail("WHT Amount", f"NGN {request_data.get('wht_amount', 0):,.2f}")
    add_detail("Net Amount Payable", f"NGN {request_data.get('net_amount_payable', 0):,.2f}")
    add_detail("Budget Balance (After Request)", f"NGN {request_data.get('budget_balance', 0):,.2f}")

    # Justification
    pdf.ln(5)
    pdf.set_font(default_font, 'BU', 12)
    pdf.cell(0, 10, "Justification", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    add_detail("Justification", request_data.get('justification', 'N/A'))

    # Vendor Details
    pdf.ln(5)
    pdf.set_font(default_font, 'BU', 12)
    pdf.cell(0, 10, "Vendor Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    add_detail("Vendor Name", request_data.get('vendor_name', 'N/A'))
    add_detail("Vendor Account Name", request_data.get('vendor_account_name', 'N/A'))
    add_detail("Vendor Account No", request_data.get('vendor_account_no', 'N/A'))
    add_detail("Vendor Bank", request_data.get('vendor_bank', 'N/A'))

    # Approval History
    pdf.ln(5)
    pdf.set_font(default_font, 'BU', 12)
    pdf.cell(0, 10, "Approval History", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    if request_data.get('approval_history'):
        for entry in request_data['approval_history']:
            pdf.set_font(default_font, 'B', 10)
            history_text = (
                f"- {entry.get('approver_role')} by {entry.get('approver_name')} "
                f"on {entry.get('date')}: {entry.get('status')}. "
                f"Comment: {entry.get('comment', 'No comment.')}"
            )
            pdf.multi_cell(0, line_height, history_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.set_font(default_font, '', 10)
        pdf.cell(0, line_height, "No approval history yet.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Final Status
    pdf.ln(5)
    pdf.set_font(default_font, 'BU', 12)
    pdf.cell(0, 10, "Final Status", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font(default_font, 'B', 10)
    pdf.cell(0, line_height, f"Status: {request_data.get('final_status', 'Pending')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


    # Save the PDF
    pdf_dir = os.path.join(DATA_DIR, "opex_capex_pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"opex_capex_{request_data['request_id']}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    pdf.output(pdf_path)
    return pdf_path

            
def handle_opex_capex_approval(request, user_approval_level, comment, status, approver_id, is_admin):
    # Ensure all_opex_capex_requests is loaded
    st.session_state.opex_capex_requests = load_data(OPEX_CAPEX_REQUESTS_FILE)

    # Find the request by ID
    found_request_index = -1
    for i, req in enumerate(st.session_state.opex_capex_requests):
        if req.get('request_id') == request['request_id']:
            found_request_index = i
            break

    if found_request_index == -1:
        st.error("Error: Request not found in the database.")
        return

    current_request = st.session_state.opex_capex_requests[found_request_index]
    current_stage_index = current_request.get('current_approval_stage', 0)
    
    # Check if the request is already finalized
    if current_request.get('final_status') in ["Approved", "Rejected"]:
        st.warning(f"This request has already been '{current_request['final_status']}'. No further action can be taken.")
        return

    # Check if the current user is authorized to approve at this stage
    if not is_admin:
        if user_approval_level != current_stage_index:
            st.error("You are not the current designated approver for this stage.")
            return
        
        # Ensure the current stage index is valid for APPROVAL_CHAIN
        if current_stage_index >= len(APPROVAL_CHAIN):
            st.error("Error: Approval chain index out of bounds for this request.")
            return

    # Get the current approver's role from the approval chain
    approver_role_info = APPROVAL_CHAIN[current_stage_index]
    approver_role = approver_role_info['role_name'] # This should always be a string

    # Ensure approver_role is a string before calling .lower() or using in string contexts
    # This check is a safeguard, as 'role_name' from APPROVAL_CHAIN should be a string.
    if not isinstance(approver_role, str):
        actual_approver_role_name = str(approver_role)
    else:
        actual_approver_role_name = approver_role

    # Construct the status key for the current approver
    # Use actual_approver_role_name which is guaranteed to be a string
    stage_key = f"status_{actual_approver_role_name.lower().replace(' ', '_')}"

    current_request[stage_key] = status
    current_request.setdefault('approval_history', []).append({
        "approver_role": actual_approver_role_name, # Use the string version of the role here
        "approver_name": approver_id,
        "comment": comment,
        "status": status,
        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

    # Move to next approval stage if approved and not final
    if status == "Approved" and current_stage_index + 1 < len(APPROVAL_CHAIN):
        current_request['current_approval_stage'] = current_stage_index + 1
        st.success(f"Request {request['request_id']} approved by {actual_approver_role_name}. Moving to next stage.")
    else:
        current_request['final_status'] = status  # Either final approval or rejection
        if status == "Approved":
            st.success(f"Request {request['request_id']} fully approved!")
            # Regenerate PDF if fully approved
            pdf_path = generate_opex_capex_pdf(current_request)
            current_request['pdf_path'] = pdf_path
        else:
            st.error(f"Request {request['request_id']} has been Rejected.")

    save_data(st.session_state.opex_capex_requests, OPEX_CAPEX_REQUESTS_FILE)
    st.rerun() # Rerun to update the UI

# Manage OPEX/CAPEX Approvals
def manage_opex_capex_approvals():
    st.title("✅ Manage OPEX/CAPEX Approvals")

    current_user_id = st.session_state.current_user['username']
    is_admin = st.session_state.current_user['role'] == 'admin'

    all_requests = st.session_state.opex_capex_requests

    # Determine the current user's approval level
    current_user_profile = st.session_state.current_user.get('profile', {})
    current_user_department = current_user_profile.get('department')
    current_user_grade = current_user_profile.get('grade_level')

    user_approval_level = -1 # -1 means not an approver
    if is_admin:
        user_approval_level = len(APPROVAL_CHAIN) # Admin can approve anything
    else:
        for i, approver_role_info in enumerate(APPROVAL_CHAIN):
            if (current_user_department == approver_role_info['department'] and
                    current_user_grade == approver_role_info['grade_level']):
                user_approval_level = i
                break

    if user_approval_level == -1:
        st.warning("You are not authorized to approve OPEX/CAPEX requests.")
        return

    pending_requests = []
    for req in all_requests:
        # Determine the required approval level for this request
        current_approval_index = req.get('current_approval_level', 0)
        final_status = req.get('final_status', 'Pending')

        # Check if the user is the next required approver OR an admin
        if final_status == 'Pending':
            if is_admin: # Admin can see all pending requests
                pending_requests.append(req)
            elif current_approval_index < len(APPROVAL_CHAIN):
                required_approver_info = APPROVAL_CHAIN[current_approval_index]
                if (current_user_department == required_approver_info['department'] and
                        current_user_grade == required_approver_info['grade_level']):
                    pending_requests.append(req)

    if not pending_requests:
        st.info("No OPEX/CAPEX requests pending your approval.")
        return

    # Ensure all requests have a 'request_id' before DataFrame conversion and display
    # Filter out any requests that might be malformed and missing 'request_id'
    valid_pending_requests = [req for req in pending_requests if 'request_id' in req]
    if not valid_pending_requests:
        st.info("No valid OPEX/CAPEX requests to display.")
        return

    df_pending = pd.DataFrame(valid_pending_requests)

    # Convert submission_date with format ISO8601, handling errors
    df_display = df_pending[['request_id', 'requester_name', 'request_type', 'item_description',
                             'total_amount', 'submission_date', 'final_status']].copy()

    df_display['submission_date'] = pd.to_datetime(df_display['submission_date'], errors='coerce', format='ISO8601').dt.date

    # Safely convert 'request_id' to string type to avoid ArrowInvalid if it's mixed
    df_display['request_id'] = df_display['request_id'].astype(str)

    st.subheader("Pending OPEX/CAPEX Requests")
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Ensure options for selectbox are only valid string request IDs
    selected_request_id = st.selectbox(
        "Select Request to Review:",
        options=[""] + [str(req['request_id']) for req in valid_pending_requests],
        key="select_opex_capex_request"
    )

    if selected_request_id:
        selected_request = next((req for req in valid_pending_requests if str(req['request_id']) == selected_request_id), None)

        if selected_request:
            st.markdown("---")
            st.subheader(f"Reviewing Request: {selected_request_id}")

            # Display request details
            st.write(f"**Requester Name:** {selected_request.get('requester_name', 'N/A')}")
            st.write(f"**Requester Staff ID:** {selected_request.get('requester_staff_id', 'N/A')}")
            st.write(f"**Requester Department:** {selected_request.get('requester_department', 'N/A')}")
            st.write(f"**Request Type:** {selected_request.get('request_type', 'N/A')}")
            st.write(f"**Item Description:** {selected_request.get('item_description', 'N/A')}")
            st.write(f"**Expense Line:** {selected_request.get('expense_line', 'N/A')}")
            st.write(f"**Budgeted Amount:** ₦{selected_request.get('budgeted_amount', 0):,.2f}")
            st.write(f"**Material Cost:** ₦{selected_request.get('material_cost', 0):,.2f}")
            st.write(f"**Labor Cost:** ₦{selected_request.get('labor_cost', 0):,.2f}")
            st.write(f"**Total Amount:** ₦{selected_request.get('total_amount', 0):,.2f}")
            st.write(f"**WHT Percentage:** {selected_request.get('wht_percentage', 0)}%")
            st.write(f"**WHT Amount:** ₦{selected_request.get('wht_amount', 0):,.2f}")
            st.write(f"**Net Amount Payable:** ₦{selected_request.get('net_amount_payable', 0):,.2f}")
            st.write(f"**Budget Balance (After Request):** ₦{selected_request.get('budget_balance', 0):,.2f}")
            st.write(f"**Justification:** {selected_request.get('justification', 'N/A')}")
            st.write(f"**Vendor Name:** {selected_request.get('vendor_name', 'N/A')}")
            st.write(f"**Vendor Account Name:** {selected_request.get('vendor_account_name', 'N/A')}")
            st.write(f"**Vendor Account No:** {selected_request.get('vendor_account_no', 'N/A')}")
            st.write(f"**Vendor Bank:** {selected_request.get('vendor_bank', 'N/A')}")
            st.write(f"**Submission Date:** {selected_request.get('submission_date', 'N/A')}")
            st.write(f"**Current Status:** **{selected_request.get('final_status', 'Pending')}**")

            # Display attached document if any
            if selected_request.get('document_path') and os.path.exists(selected_request['document_path']):
                st.download_button(
                    label=f"Download Attached Document: {os.path.basename(selected_request['document_path'])}",
                    data=open(selected_request['document_path'], "rb").read(),
                    file_name=os.path.basename(selected_request['document_path']),
                    mime="application/octet-stream",
                    key=f"download_doc_{selected_request_id}"
                )
            else:
                st.info("No document attached to this request.")

            st.markdown("---")
            st.subheader("Approval Action")
            comment = st.text_area("Your Comment:", key=f"approval_comment_{selected_request_id}")

            col_approve, col_reject = st.columns(2)
            with col_approve:
                if st.button("Approve", key=f"approve_opex_capex_{selected_request_id}"):
                    handle_opex_capex_approval(selected_request, user_approval_level, comment, 'Approved', current_user_id, is_admin)
            with col_reject:
                if st.button("Reject", key=f"reject_opex_capex_{selected_request_id}"):
                    handle_opex_capex_approval(selected_request, user_approval_level, comment, 'Rejected', current_user_id, is_admin)

            st.markdown("---")
            st.subheader("Approval History")
            if selected_request.get('approval_history'):
                for entry in selected_request['approval_history']:
                    st.write(f"- **{entry.get('approver_role')}** by **{entry.get('approver_name')}** on **{entry.get('date')}**: **{entry.get('status')}**. Comment: {entry.get('comment', 'No comment.')}")
            else:
                st.info("No approval history for this request yet.")
        else: # This 'else' is correctly aligned with 'if selected_request:'
            st.warning("Selected request not found.")

# Manage Leave Approvals (Admin)
def admin_manage_leave_approvals():
    st.title("✅ Manage Leave Approvals")

    # Ensure all_leave_requests is loaded
    all_leave_requests = st.session_state.leave_requests

    # Filter for pending requests
    pending_requests = [req for req in all_leave_requests if req.get('status') == 'Pending']

    if not pending_requests:
        st.info("No leave requests pending approval.")
        return

    # Preprocess requests to flatten requester_name and staff_id for DataFrame
    processed_requests = []
    for req in pending_requests:
        # Find the user associated with the request to get their profile details
        requester_username = req.get('requester_username')
        requester_user = next((user for user in st.session_state.users if user['username'] == requester_username), None)
        
        requester_name = "N/A"
        staff_id = "N/A"
        if requester_user and 'profile' in requester_user:
            requester_name = requester_user['profile'].get('name', 'N/A')
            staff_id = requester_user['profile'].get('staff_id', 'N/A')

        processed_req = req.copy() # Create a copy to avoid modifying original session state data directly
        processed_req['requester_name'] = requester_name
        processed_req['staff_id'] = staff_id
        processed_requests.append(processed_req)

    df_pending = pd.DataFrame(processed_requests)

    # Convert 'request_id' to string type to avoid ArrowInvalid error
    if 'request_id' in df_pending.columns:
        df_pending['request_id'] = df_pending['request_id'].astype(str)
    
    # Convert 'num_days' to string type to avoid ArrowInvalid if it contains mixed types
    if 'num_days' in df_pending.columns:
        df_pending['num_days'] = df_pending['num_days'].astype(str)

    # Convert date columns to datetime objects, handling errors
    for col in ['submission_date', 'start_date', 'end_date']:
        if col in df_pending.columns:
            df_pending[col] = pd.to_datetime(df_pending[col], errors='coerce').dt.date

    # Define columns to display
    display_cols = ['request_id', 'submission_date', 'requester_name', 'staff_id', 'leave_type', 'start_date', 'end_date', 'num_days', 'reason', 'status']
    
    # Filter display_cols to only include columns actually present in df_pending
    display_cols = [col for col in display_cols if col in df_pending.columns]

    st.subheader("Pending Leave Requests")
    st.dataframe(df_pending[display_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Approve/Decline Leave Request")

    selected_request_id = st.selectbox(
        "Select Request ID to review:",
        options=[""] + df_pending['request_id'].tolist(),
        key="admin_leave_select_request"
    )

    if selected_request_id:
        selected_request = next((req for req in processed_requests if req['request_id'] == selected_request_id), None)

        if selected_request:
            st.write(f"**Requester:** {selected_request.get('requester_name', 'N/A')} ({selected_request.get('staff_id', 'N/A')})")
            st.write(f"**Leave Type:** {selected_request.get('leave_type', 'N/A')}")
            st.write(f"**Period:** {selected_request.get('start_date', 'N/A')} to {selected_request.get('end_date', 'N/A')} ({selected_request.get('num_days', 'N/A')} days)")
            st.write(f"**Reason:** {selected_request.get('reason', 'N/A')}")
            st.write(f"**Current Status:** **{selected_request.get('status', 'Pending')}**")

            comment = st.text_area("Add a comment (optional):", key=f"admin_leave_comment_{selected_request_id}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve", key=f"approve_leave_{selected_request_id}"):
                    handle_leave_approval(selected_request['request_id'], 'Approved', comment)
            with col2:
                if st.button("Decline", key=f"decline_leave_{selected_request_id}"):
                    handle_leave_approval(selected_request['request_id'], 'Declined', comment)
        else:
            st.warning("Selected request not found.")

    st.markdown("---")
    st.subheader("All Leave Requests (Overview)")
    
    # Preprocess all requests for overview DataFrame
    all_processed_requests = []
    for req in all_leave_requests:
        requester_username = req.get('requester_username')
        requester_user = next((user for user in st.session_state.users if user['username'] == requester_username), None)
        
        requester_name = "N/A"
        staff_id = "N/A"
        if requester_user and 'profile' in requester_user:
            requester_name = requester_user['profile'].get('name', 'N/A')
            staff_id = requester_user['profile'].get('staff_id', 'N/A')

        processed_req = req.copy()
        processed_req['requester_name'] = requester_name
        processed_req['staff_id'] = staff_id
        all_processed_requests.append(processed_req)

    if all_processed_requests:
        df_all_requests = pd.DataFrame(all_processed_requests)

        # Convert 'request_id' to string type
        if 'request_id' in df_all_requests.columns:
            df_all_requests['request_id'] = df_all_requests['request_id'].astype(str)
        
        # Convert 'num_days' to string type
        if 'num_days' in df_all_requests.columns:
            df_all_requests['num_days'] = df_all_requests['num_days'].astype(str)

        # Convert date columns to datetime objects, handling errors
        for col in ['submission_date', 'start_date', 'end_date']:
            if col in df_all_requests.columns:
                df_all_requests[col] = pd.to_datetime(df_all_requests[col], errors='coerce').dt.date

        # Define columns for the overview table
        overview_display_cols = ['request_id', 'submission_date', 'requester_name', 'staff_id', 'leave_type', 'start_date', 'end_date', 'num_days', 'reason', 'status']
        overview_display_cols = [col for col in overview_display_cols if col in df_all_requests.columns]

        st.dataframe(df_all_requests[overview_display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No leave requests submitted yet.")


# Manage Beneficiaries (Admin)
def admin_manage_beneficiaries():
    st.title("🏦 Admin: Manage Beneficiaries")

    st.subheader("Current Beneficiaries")
    if st.session_state.beneficiaries:
        # Convert dictionary to a list of dicts for DataFrame
        beneficiary_list = [{"Name": name, **details} for name, details in st.session_state.beneficiaries.items()]
        df_beneficiaries = pd.DataFrame(beneficiary_list)
        st.dataframe(df_beneficiaries, use_container_width=True, hide_index=True)
    else:
        st.info("No beneficiaries configured yet.")

    st.markdown("---")
    st.subheader("Add New Beneficiary")
    with st.form("add_beneficiary_form", clear_on_submit=True):
        new_beneficiary_name = st.text_input("Beneficiary Name (Company/Individual)")
        new_account_name = st.text_input("Account Name")
        new_account_no = st.text_input("Account Number")
        new_bank = st.text_input("Bank Name")
        
        add_bene_submitted = st.form_submit_button("Add Beneficiary")

        if add_bene_submitted:
            if not new_beneficiary_name or not new_account_name or not new_account_no or not new_bank:
                st.error("Please fill in all beneficiary details.")
            elif new_beneficiary_name in st.session_state.beneficiaries:
                st.error("Beneficiary with this name already exists.")
            else:
                st.session_state.beneficiaries[new_beneficiary_name] = {
                    "Account Name": new_account_name,
                    "Account No": new_account_no,
                    "Bank": new_bank
                }
                save_data(st.session_state.beneficiaries, BENEFICIARIES_FILE)
                st.success(f"Beneficiary '{new_beneficiary_name}' added successfully!")
                st.rerun()
    
    st.markdown("---")
    st.subheader("Edit / Delete Beneficiary")
    # Exclude "Other (Manually Enter Details)" from selectable options for editing/deleting
    editable_beneficiaries = [b for b in list(st.session_state.beneficiaries.keys()) if b != "Other (Manually Enter Details)"]
    bene_to_modify = st.selectbox("Select Beneficiary to Edit/Delete", [""] + editable_beneficiaries, key="select_bene_to_modify")
    
    if bene_to_modify:
        selected_bene = st.session_state.beneficiaries.get(bene_to_modify)
        if selected_bene:
            with st.form("edit_delete_beneficiary_form", clear_on_submit=True):
                st.write(f"Editing Beneficiary: **{bene_to_modify}**")
                
                edit_account_name = st.text_input("Account Name", value=selected_bene.get('Account Name', ''))
                edit_account_no = st.text_input("Account Number", value=selected_bene.get('Account No', ''))
                edit_bank = st.text_input("Bank Name", value=selected_bene.get('Bank', ''))

                col_edit_del_bene = st.columns(2)
                with col_edit_del_bene[0]:
                    edit_bene_submitted = st.form_submit_button("Update Beneficiary")
                with col_edit_del_bene[1]:
                    delete_bene_submitted = st.form_submit_button("Delete Beneficiary")

                if edit_bene_submitted:
                    st.session_state.beneficiaries[bene_to_modify] = {
                        "Account Name": edit_account_name,
                        "Account No": edit_account_no,
                        "Bank": edit_bank
                    }
                    save_data(st.session_state.beneficiaries, BENEFICIARIES_FILE)
                    st.success(f"Beneficiary '{bene_to_modify}' updated successfully!")
                    st.rerun()

                if delete_bene_submitted:
                    del st.session_state.beneficiaries[bene_to_modify]
                    save_data(st.session_state.beneficiaries, BENEFICIARIES_FILE)
                    st.warning(f"Beneficiary '{bene_to_modify}' deleted.")
                    st.rerun()

# Manage HR Policies (Admin)
def admin_manage_hr_policies():
    st.title("📜 Admin: Manage HR Policies")

    st.subheader("Current HR Policies")
    if st.session_state.hr_policies:
        for policy_name, policy_content in st.session_state.hr_policies.items():
            with st.expander(f"**{policy_name}**"):
                st.write(policy_content)
    else:
        st.info("No HR policies defined yet.")

    st.markdown("---")
    st.subheader("Add New Policy")
    with st.form("add_policy_form", clear_on_submit=True):
        new_policy_name = st.text_input("Policy Title")
        new_policy_content = st.text_area("Policy Content", height=200)
        
        add_policy_submitted = st.form_submit_button("Add Policy")

        if add_policy_submitted:
            if not new_policy_name or not new_policy_content:
                st.error("Please fill in both policy title and content.")
            elif new_policy_name in st.session_state.hr_policies:
                st.error("Policy with this title already exists.")
            else:
                st.session_state.hr_policies[new_policy_name] = new_policy_content
                save_data(st.session_state.hr_policies, HR_POLICIES_FILE)
                st.success(f"Policy '{new_policy_name}' added successfully!")
                st.rerun()

    st.markdown("---")
    st.subheader("Edit / Delete Policy")
    policy_to_modify = st.selectbox("Select Policy to Edit/Delete", [""] + list(st.session_state.hr_policies.keys()), key="select_policy_to_modify")
    
    if policy_to_modify:
        selected_policy_content = st.session_state.hr_policies.get(policy_to_modify, "")
        with st.form("edit_delete_policy_form", clear_on_submit=True):
            st.write(f"Editing Policy: **{policy_to_modify}**")
            
            edit_policy_content = st.text_area("Policy Content", value=selected_policy_content, height=200)

            col_edit_del_policy = st.columns(2)
            with col_edit_del_policy[0]:
                edit_policy_submitted = st.form_submit_button("Update Policy")
            with col_edit_del_policy[1]:
                delete_policy_submitted = st.form_submit_button("Delete Policy")

            if edit_policy_submitted:
                st.session_state.hr_policies[policy_to_modify] = edit_policy_content
                save_data(st.session_state.hr_policies, HR_POLICIES_FILE)
                st.success(f"Policy '{policy_to_modify}' updated successfully!")
                st.rerun()

            if delete_policy_submitted:
                del st.session_state.hr_policies[policy_to_modify]
                save_data(st.session_state.hr_policies, HR_POLICIES_FILE)
                st.warning(f"Policy '{policy_to_modify}' deleted.")
                st.rerun()


# --- Main Application Logic ---
def main():
    setup_initial_data() # Ensure initial data is set up

    if not st.session_state.logged_in:
        login_form()
    else:
        display_sidebar()
        # Main content area based on current_page
        if st.session_state.current_page == "dashboard":
            display_dashboard()
        elif st.session_state.current_page == "my_profile":
            display_my_profile()
        elif st.session_state.current_page == "leave_request":
            leave_request_form()
        elif st.session_state.current_page == "view_my_leave":
            view_my_leave_requests()
        elif st.session_state.current_page == "opex_capex_form":
            opex_capex_form()
        elif st.session_state.current_page == "view_my_opex_capex":
            view_my_opex_capex_requests()
        elif st.session_state.current_page == "performance_goal_setting":
            performance_goal_setting()
        elif st.session_state.current_page == "view_my_goals":
            view_my_goals()
        elif st.session_state.current_page == "self_appraisal":
            self_appraisal_form()
        elif st.session_state.current_page == "view_my_appraisals":
            view_my_appraisals()
        elif st.session_state.current_page == "my_payslips":
            my_payslips()
        elif st.session_state.current_page == "hr_policies":
            hr_policies()
        # Admin functions - check role before rendering
        elif st.session_state.current_page == "manage_users":
            if st.session_state.current_user and st.session_state.current_user['role'] == 'admin':
                admin_manage_users()
            else:
                st.error("Access Denied: You do not have permission to view this page.")
                st.session_state.current_page = "dashboard"
                st.rerun()
        elif st.session_state.current_page == "upload_payroll":
            if st.session_state.current_user and st.session_state.current_user['role'] == 'admin':
                admin_upload_payroll()
            else:
                st.error("Access Denied: You do not have permission to view this page.")
                st.session_state.current_page = "dashboard"
                st.rerun()
        elif st.session_state.current_page == "manage_opex_capex_approvals":
            # Any approver in the chain (including admin) can access this
            current_user_profile = st.session_state.current_user.get('profile', {})
            current_user_department = current_user_profile.get('department')
            current_user_grade = current_user_profile.get('grade_level')
            
            is_eligible_approver = False
            if st.session_state.current_user['role'] == 'admin':
                is_eligible_approver = True
            else:
                for approver_role_info in APPROVAL_CHAIN:
                    if (current_user_department == approver_role_info['department'] and
                            current_user_grade == approver_role_info['grade_level']):
                        is_eligible_approver = True
                        break
            
            if is_eligible_approver:
                manage_opex_capex_approvals()
            else:
                st.error("Access Denied: You do not have permission to view this page.")
                st.session_state.current_page = "dashboard"
                st.rerun()
        elif st.session_state.current_page == "manage_leave_approvals": # NEWLY ADDED
            if st.session_state.current_user and st.session_state.current_user['role'] == 'admin':
                admin_manage_leave_approvals()
            else:
                st.error("Access Denied: You do not have permission to view this page.")
                st.session_state.current_page = "dashboard"
                st.rerun()
        elif st.session_state.current_page == "manage_beneficiaries":
            if st.session_state.current_user and st.session_state.current_user['role'] == 'admin':
                admin_manage_beneficiaries()
            else:
                st.error("Access Denied: You do not have permission to view this page.")
                st.session_state.current_page = "dashboard"
                st.rerun()
        elif st.session_state.current_page == "manage_hr_policies":
            if st.session_state.current_user and st.session_state.current_user['role'] == 'admin':
                admin_manage_hr_policies()
            else:
                st.error("Access Denied: You do not have permission to view this page.")
                st.session_state.current_page = "dashboard"
                st.rerun()

if __name__ == "__main__":
    main()
