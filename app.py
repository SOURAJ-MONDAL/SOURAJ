"""
app.py
MediKiosk — main entry point and router.

Initializes all three SQLite databases, sets up shared session state, and
wires up the multi-page navigation via st.navigation. Pages appearing in
the nav change depending on whether a doctor / patient is logged in.
"""

import streamlit as st

from db import init_db
from styles import inject_base_css

st.set_page_config(
    page_title="MediKiosk",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
inject_base_css()

# --------------------------------------------------------------------------
# Session state defaults
# --------------------------------------------------------------------------

_DEFAULTS = {
    "user_type": None,        # "doctor" | "patient" | None
    "user_id": None,
    "user_name": None,
    "active_chat_session_id": None,
    "directory_specialization_filter": "All",
    "booking_doctor_id": None,
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


def logout():
    for key in ("user_type", "user_id", "user_name", "active_chat_session_id", "booking_doctor_id"):
        st.session_state[key] = _DEFAULTS[key]
    st.rerun()


# --------------------------------------------------------------------------
# Sidebar identity block
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        "<div style='font-family:Fraunces,serif;font-size:1.5rem;font-weight:700;"
        "color:#0F5C5C;'>🩺 MediKiosk</div>",
        unsafe_allow_html=True,
    )
    st.caption("Your walk-up healthcare companion")
    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)

    if st.session_state.user_type:
        role_label = "Doctor" if st.session_state.user_type == "doctor" else "Patient"
        st.markdown(f"**Signed in** · {role_label}")
        st.markdown(f"👤 {st.session_state.user_name}")
        if st.button("Log out", use_container_width=True):
            logout()
    else:
        st.caption("Not signed in")

# --------------------------------------------------------------------------
# Navigation — page list adapts to login state
# --------------------------------------------------------------------------

home_page = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
doctor_auth_page = st.Page("pages/doctor_auth.py", title="Doctor Sign Up / Login", icon="🩺")
patient_auth_page = st.Page("pages/patient_auth.py", title="Patient Sign Up / Login", icon="🧑‍🦰")
doctor_dashboard_page = st.Page("pages/doctor_dashboard.py", title="Doctor Dashboard", icon="📋")
patient_dashboard_page = st.Page("pages/patient_dashboard.py", title="Patient Dashboard", icon="💬")
doctor_directory_page = st.Page("pages/doctor_directory.py", title="Find a Doctor", icon="🔎")

if st.session_state.user_type == "doctor":
    pages = [home_page, doctor_dashboard_page]
elif st.session_state.user_type == "patient":
    pages = [home_page, patient_dashboard_page, doctor_directory_page]
else:
    pages = [home_page, patient_auth_page, doctor_auth_page, doctor_directory_page]

nav = st.navigation(pages, position="sidebar")
nav.run()
