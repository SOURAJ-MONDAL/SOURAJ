import time

import streamlit as st

import db
from styles import page_header
from utils import (
    file_to_bytes,
    hospital_affiliations_editor,
    is_valid_doctor_age,
    is_valid_password,
    is_valid_phone,
    password_hint,
    restrict_to_digits,
    schedule_slot_editor,
    time_to_minutes,
)

SPECIALIZATIONS = [
    "General Physician", "Cardiologist", "Neurologist", "Dermatologist",
    "Pediatrician", "Gynecologist", "Orthopedist", "ENT Specialist",
    "Psychiatrist", "Pulmonologist", "Gastroenterologist", "Physiotherapist",
]

if st.session_state.get("user_type") == "doctor":
    st.switch_page("pages/home.py")

page_header("DOCTOR PORTAL", "Sign Up or Log In", "Get verified and start managing your practice on MediKiosk.")

tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

# --------------------------------------------------------------------------
# LOGIN
# --------------------------------------------------------------------------
with tab_login:
    with st.form("doctor_login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter both email and password.")
        elif not db.get_doctor_by_email(email.strip()):
            st.error("No account created yet. Please sign up from the **Sign Up** tab.")
        else:
            doc = db.authenticate_doctor(email.strip(), password)
            if not doc:
                st.error("Incorrect password. Please try again.")
            elif doc["verification_status"] != "accepted":
                st.warning(
                    f"Your account is currently **{doc['verification_status']}**. "
                    "You'll be able to access your dashboard once your documents are verified."
                )
            else:
                st.session_state.user_type = "doctor"
                st.session_state.user_id = doc["id"]
                st.session_state.user_name = doc["name"]
                st.success("Welcome back! Redirecting…")
                st.rerun()

# --------------------------------------------------------------------------
# SIGN UP
# --------------------------------------------------------------------------
with tab_signup:
    st.markdown(
        "<div class='mk-muted'>Upload your medical license and degree to complete your profile.</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    # No st.form here: "Number of chambers" needs to redraw the address
    # fields the instant it changes, and widgets inside st.form don't
    # trigger a rerun until the whole form is submitted — so every field
    # below is a plain widget, gathered up and validated on button click.
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Full name*")
        email = st.text_input("Email*")
        phone = st.text_input("Phone number* (10 digits)", max_chars=10)
        restrict_to_digits("Phone number* (10 digits)", max_length=10)
        age = st.text_input("Age* (2 digits)", max_chars=2)
        restrict_to_digits("Age* (2 digits)", max_length=2)
        gender = st.selectbox("Gender*", ["Male", "Female", "Others"])
    with c2:
        specialization = st.selectbox("Specialization*", SPECIALIZATIONS)
        fee = st.number_input("Consultation fee (₹)*", min_value=0, step=50)
        profile_photo = st.file_uploader("Profile photo", type=["png", "jpg", "jpeg"])

    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    st.markdown("**Hospital affiliation(s)***")
    st.caption(
        "Add every hospital you practice at. Use ➕ Add hospital for more — "
        "we'll match each one against our hospital directory."
    )
    hospital_names = hospital_affiliations_editor("doctor_signup")

    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    chamber_count = st.number_input(
        "Number of chambers*", min_value=1, max_value=10, step=1, key="doctor_signup_chamber_count"
    )
    st.markdown(f"**Chamber address{'es' if chamber_count > 1 else ''}***")
    chamber_addresses = []
    for i in range(int(chamber_count)):
        addr = st.text_area(
            f"Address (Chamber {i + 1})*",
            key=f"doctor_signup_chamber_addr_{i}",
            placeholder="e.g. Room 4, 2nd Floor, City Care Hospital",
        )
        chamber_addresses.append(addr)

    st.markdown("**Available schedule***")
    st.caption("Add a row for each day/time you're available. Use ➕ Add slot for more.")
    hospital_options = [h.strip() for h in hospital_names if h and h.strip()]
    if not hospital_options:
        hospital_options = ["Not specified"]
    schedule_slots = schedule_slot_editor("doctor_signup", chamber_count, hospital_options=hospital_options)

    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        license_doc = st.file_uploader("Medical license document*", type=["png", "jpg", "jpeg", "pdf"])
    with d2:
        degree_doc = st.file_uploader("Degree certificate*", type=["png", "jpg", "jpeg", "pdf"])

    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    p1, p2 = st.columns(2)
    with p1:
        password = st.text_input("Password*", type="password", help=password_hint())
    with p2:
        confirm_password = st.text_input("Confirm password*", type="password")

    submitted = st.button("Create Doctor Account", type="primary", use_container_width=True)

    if submitted:
        errors = []
        clean_hospitals = [h.strip() for h in hospital_names if h and h.strip()]
        if not name or not email or not clean_hospitals:
            errors.append("Please fill in all required fields, including at least one hospital affiliation.")
        if not all(a.strip() for a in chamber_addresses):
            errors.append("Please fill in an address for every chamber.")
        for slot in schedule_slots:
            start_min = time_to_minutes(slot["start"])
            end_min = time_to_minutes(slot["end"])
            if start_min is None or end_min is None or end_min <= start_min:
                errors.append(
                    f"On {slot['day']}, the 'To' time must be later than the 'From' time."
                )
        if not is_valid_phone(phone):
            errors.append("Phone number must be exactly 10 digits.")
        if not is_valid_doctor_age(age):
            errors.append("Age must be 1-2 digits and between 18 and 99.")
        if not is_valid_password(password):
            errors.append(f"Password does not meet requirements: {password_hint()}")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if db.get_doctor_by_email(email.strip()) if email else False:
            errors.append("An account with this email already exists.")
        if not license_doc or not degree_doc:
            errors.append("Please upload both your license and degree documents.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            license_bytes = file_to_bytes(license_doc)
            degree_bytes = file_to_bytes(degree_doc)

            doctor_id = db.create_doctor(
                name=name.strip(),
                email=email.strip(),
                phone=phone.strip(),
                age=int(age),
                gender=gender,
                specialization=specialization,
                license_doc=license_bytes,
                license_doc_name=license_doc.name,
                degree_doc=degree_bytes,
                degree_doc_name=degree_doc.name,
                chamber_count=int(chamber_count),
                chamber_addresses=[a.strip() for a in chamber_addresses],
                hospital_affiliations=clean_hospitals,
                schedule={"slots": schedule_slots},
                fee=float(fee),
                profile_photo=file_to_bytes(profile_photo),
                password=password,
                verification_status="accepted",
            )
            st.session_state.user_type = "doctor"
            st.session_state.user_id = doctor_id
            st.session_state.user_name = name.strip()
            st.success("🎉 Your profile is live. Redirecting…")
            time.sleep(1.2)
            st.rerun()
