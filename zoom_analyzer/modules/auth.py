"""
Module: auth.py
================
Natively manages user authentication, registration, password hashing,
and OTP code verification for the Zoom Attendance Analyzer in Streamlit.
"""

import streamlit as st
import hashlib
import random
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
    COLOR_BLUE, COLOR_DARK, COLOR_LIGHT
)
from modules.database import create_user, get_user_by_email, _get_conn


# ─── Security Helpers ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Securely hash a password with a static application salt."""
    salt = "zoom_attendance_analyzer_salt_123!"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()


def is_valid_email(email: str) -> bool:
    """Basic email regex validation."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def get_user_count() -> int:
    """Return the total number of registered users in the database."""
    try:
        with _get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except Exception:
        return 0


# ─── OTP Helpers ─────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """Generate a random 6-digit OTP code."""
    return str(random.randint(100000, 999999))


def send_otp_email(email: str, otp: str) -> tuple[bool, str]:
    """
    Send an OTP code to the user's email.
    If SMTP configurations are missing, it defaults to Demo Mock Mode.
    Returns (success_status, message_or_error).
    """
    if not SMTP_SERVER or not SMTP_USER:
        # Debug/Demo local fallback
        print(f"\n[DEMO MODE] OTP for {email} is: {otp}\n")
        return True, "demo"

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_FROM
        msg['To'] = email
        msg['Subject'] = "Your Registration OTP - Zoom Attendance Analyzer"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #2c3e50;">
            <div style="max-width: 500px; margin: auto; border: 1px solid #e2e8f0; border-radius: 12px; padding: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <h2 style="color: #3498db; margin-top: 0; text-align: center;">Verify Your Email Address</h2>
                <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                <p>Hello,</p>
                <p>Thank you for registering. Please use the following One-Time Password (OTP) to complete your account setup:</p>
                <div style="background-color: #f7fafc; border: 1px dashed #cbd5e0; border-radius: 8px; padding: 15px; text-align: center; margin: 25px 0;">
                    <span style="font-size: 30px; font-weight: bold; letter-spacing: 4px; color: #2b6cb0;">{otp}</span>
                </div>
                <p style="font-size: 13px; color: #718096; text-align: center;">This OTP is valid for <strong>5 minutes</strong>. Please do not share this code with anyone.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, email, msg.as_string())
        return True, "sent"
    except Exception as e:
        return False, str(e)


# ─── Auth Gate & Streamlit Pages ─────────────────────────────────────────────

def check_authentication() -> bool:
    """
    Verifies if the user is currently authenticated.
    If not, hides the sidebar navigation, displays the Login/Registration UI,
    and calls st.stop() to halt execution of the calling page.
    """
    # Initialize authentication session state variables if they don't exist
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user_name" not in st.session_state:
        st.session_state["user_name"] = ""
    if "user_email" not in st.session_state:
        st.session_state["user_email"] = ""

    # If already logged in, show normal content
    if st.session_state["authenticated"]:
        return True

    # Hide sidebar page links if not logged in
    st.markdown("""
    <style>
    [data-testid="sidebar-nav-container"], .stSidebarNav, [data-testid="stSidebarNav"] {
        display: none !important;
    }
    [data-testid="stSidebar"] {
        min-width: 0px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Initialize OTP state flags
    if "reg_otp" not in st.session_state:
        st.session_state["reg_otp"] = ""
    if "reg_otp_email" not in st.session_state:
        st.session_state["reg_otp_email"] = ""
    if "reg_otp_time" not in st.session_state:
        st.session_state["reg_otp_time"] = 0
    if "reg_otp_sent" not in st.session_state:
        st.session_state["reg_otp_sent"] = False
    if "reg_otp_verified" not in st.session_state:
        st.session_state["reg_otp_verified"] = False

    # Center the login card layout
    st.markdown("""
    <div style="text-align: center; padding-top: 1.5rem;">
        <span style="font-size: 3.5rem;">🎓</span>
        <h2 style="color: #2c3e50; font-weight: 800; margin-top: 10px;">Zoom Attendance Analyzer</h2>
        <p style="color: #7f8c8d; font-size: 0.95rem; margin-bottom: 2rem;">Secure Login & Registration Panel</p>
    </div>
    """, unsafe_allow_html=True)

    # Determine view state based on database contents
    has_users = get_user_count() > 0

    if not has_users:
        st.info("👋 Welcome! No accounts found in the database. Please create the administrator account first.")
        render_registration_page()
    else:
        # Standard login / registration tabs
        tab_login, tab_register = st.tabs(["🔒 Sign In", "📝 Create Account"])

        with tab_login:
            render_login_page()

        with tab_register:
            render_registration_page()

    # Halted page execution
    st.stop()
    return False


def render_login_page():
    """Renders the Sign-In Form."""
    with st.form("login_form", clear_on_submit=False):
        st.markdown("<h3 style='margin-top:0;'>Sign In to Your Account</h3>", unsafe_allow_html=True)
        email = st.text_input("Email Address", placeholder="admin@example.com").strip()
        password = st.text_input("Password", type="password", placeholder="••••••••")
        remember = st.checkbox("Remember me")
        
        submit_btn = st.form_submit_button("Sign In", type="primary", use_container_width=True)

        if submit_btn:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                user = get_user_by_email(email)
                if user and user['password'] == hash_password(password):
                    st.session_state["authenticated"] = True
                    st.session_state["user_name"] = user['name']
                    st.session_state["user_email"] = user['email']
                    st.success("Login successful! Redirecting...")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Incorrect email or password. Please check your credentials.")


def render_registration_page():
    """Renders the detailed Sign-Up / Register Form with OTP validation."""
    st.markdown("<h3 style='margin-top:0;'>Create An Account</h3>", unsafe_allow_html=True)
    
    # Text Inputs (outside of the form since sending OTP needs to update the session state dynamically)
    name = st.text_input("Your Name", key="reg_name", placeholder="Azim Krishna").strip()
    email = st.text_input("Email Address", key="reg_email", placeholder="name@company.com").strip()

    # Step 1: Send OTP Section
    col_otp1, col_otp2 = st.columns([3, 1])
    with col_otp1:
        st.caption("We will send a 6-digit verification code to this email address.")
    with col_otp2:
        send_otp_btn = st.button(
            "Send OTP" if not st.session_state["reg_otp_sent"] else "Resend OTP",
            key="send_otp_btn",
            use_container_width=True
        )

    if send_otp_btn:
        if not name:
            st.error("Please enter your name first.")
        elif not email or not is_valid_email(email):
            st.error("Please enter a valid email address.")
        else:
            # Check if user already exists
            existing_user = get_user_by_email(email)
            if existing_user:
                st.error("An account with this email address already exists. Please Sign In.")
            else:
                otp_code = generate_otp()
                st.session_state["reg_otp"] = otp_code
                st.session_state["reg_otp_email"] = email
                st.session_state["reg_otp_time"] = time.time()
                st.session_state["reg_otp_sent"] = True
                st.session_state["reg_otp_verified"] = False
                
                success, msg_type = send_otp_email(email, otp_code)
                if success:
                    st.session_state["otp_msg_type"] = msg_type
                else:
                    st.error(f"Failed to send email: {msg_type}")

    # Show OTP info box
    if st.session_state["reg_otp_sent"] and not st.session_state["reg_otp_verified"]:
        msg_type = st.session_state.get("otp_msg_type", "demo")
        if msg_type == "demo":
            st.warning(f"📩 **[Demo Mode]** OTP code sent. Use: `{st.session_state['reg_otp']}` to verify.")
        else:
            st.info("📩 Verification code has been sent to your email. (Valid for 5 minutes)")

    # Step 2: OTP Verification Inputs
    otp_code_input = ""
    if st.session_state["reg_otp_sent"] and not st.session_state["reg_otp_verified"]:
        col_ver1, col_ver2 = st.columns([3, 1])
        with col_ver1:
            otp_code_input = st.text_input("Enter 6-digit OTP", max_chars=6, placeholder="XXXXXX")
        with col_ver2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            verify_otp_btn = st.button("Verify OTP", key="verify_otp_btn", use_container_width=True)
            
            if verify_otp_btn:
                # Check expiration (5 mins)
                elapsed = time.time() - st.session_state["reg_otp_time"]
                if elapsed > 300:
                    st.error("OTP has expired. Please request a new code.")
                    # Reset OTP state
                    st.session_state["reg_otp_sent"] = False
                    st.session_state["reg_otp"] = ""
                elif otp_code_input == st.session_state["reg_otp"] and email == st.session_state["reg_otp_email"]:
                    st.session_state["reg_otp_verified"] = True
                    st.success("OTP Verified successfully!")
                    st.rerun()
                else:
                    st.error("Invalid OTP code. Please try again.")

    if st.session_state["reg_otp_verified"]:
        st.success("✅ Email Verified successfully!")

    # Step 3: Password setup
    is_fields_disabled = not st.session_state["reg_otp_verified"]
    password = st.text_input("Choose Password", type="password", disabled=is_fields_disabled, placeholder="••••••••")
    terms = st.checkbox("I accept the Terms and Conditions", disabled=is_fields_disabled, key="reg_terms")

    register_account_btn = st.button("Create Account", type="primary", disabled=is_fields_disabled, use_container_width=True)

    if register_account_btn:
        if not password or len(password) < 6:
            st.error("Password must be at least 6 characters long.")
        elif not terms:
            st.error("You must accept the Terms and Conditions to proceed.")
        else:
            # Save user
            hashed = hash_password(password)
            success = create_user(name, email, hashed)
            if success:
                st.success("🎉 Registration successful! You can now sign in.")
                # Reset registration states
                st.session_state["reg_otp"] = ""
                st.session_state["reg_otp_email"] = ""
                st.session_state["reg_otp_sent"] = False
                st.session_state["reg_otp_verified"] = False
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("Failed to register. Email might already be taken.")


def logout():
    """Clear session authentication states and redirect to login."""
    st.session_state["authenticated"] = False
    st.session_state["user_name"] = ""
    st.session_state["user_email"] = ""
    st.success("Logged out successfully.")
    time.sleep(0.5)
    st.rerun()
