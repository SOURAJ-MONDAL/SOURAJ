import streamlit as st

import db
from styles import page_header
from utils import (
    file_to_bytes,
    is_valid_password,
    is_valid_patient_age,
    is_valid_phone,
    password_hint,
    restrict_to_digits,
)

if st.session_state.get("user_type") == "patient":
    st.switch_page("pages/home.py")

page_header("PATIENT PORTAL", "Sign Up or Log In", "Chat with our AI assistant and manage your care in one place.")

tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

with tab_login:
    with st.form("patient_login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter both email and password.")
        elif not db.get_patient_by_email(email.strip()):
            st.error("No account created yet. Please sign up from the **Sign Up** tab.")
        else:
            pat = db.authenticate_patient(email.strip(), password)
            if not pat:
                st.error("Incorrect password. Please try again.")
            else:
                st.session_state.user_type = "patient"
                st.session_state.user_id = pat["id"]
                st.session_state.user_name = pat["name"]
                st.success("Welcome back! Redirecting…")
                st.rerun()

with tab_signup:
    with st.form("patient_signup_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full name*")
            email = st.text_input("Email*")
            phone = st.text_input("Phone number* (10 digits)", max_chars=10)
            restrict_to_digits("Phone number* (10 digits)", max_length=10)
        with c2:
            age = st.text_input("Age* (up to 3 digits)", max_chars=3)
            restrict_to_digits("Age* (up to 3 digits)", max_length=3)
            gender = st.selectbox("Gender*", ["Male", "Female", "Others"])
            profile_photo = st.file_uploader("Profile photo", type=["png", "jpg", "jpeg"])

        st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        with p1:
            password = st.text_input("Password*", type="password", help=password_hint())
        with p2:
            confirm_password = st.text_input("Confirm password*", type="password")

        submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not name or not email:
            errors.append("Please fill in all required fields.")
        if not is_valid_phone(phone):
            errors.append("Phone number must be exactly 10 digits.")
        if not is_valid_patient_age(age):
            errors.append("Age must be numeric, up to 3 digits, and realistic.")
        if not is_valid_password(password):
            errors.append(f"Password does not meet requirements: {password_hint()}")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if email and db.get_patient_by_email(email.strip()):
            errors.append("An account with this email already exists.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            patient_id = db.create_patient(
                name=name.strip(),
                email=email.strip(),
                phone=phone.strip(),
                age=int(age),
                gender=gender,
                profile_photo=file_to_bytes(profile_photo),
                password=password,
            )
            st.session_state.user_type = "patient"
            st.session_state.user_id = patient_id
            st.session_state.user_name = name.strip()
            st.success("Account created! Redirecting…")
            st.rerun()
