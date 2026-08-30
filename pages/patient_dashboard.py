import streamlit as st

import db
from styles import badge, page_header
from utils import file_to_bytes, image_bytes_to_thumbnail, initials, pretty_datetime

if st.session_state.get("user_type") != "patient":
    st.warning("Please log in as a patient to view this page.")
    if st.button("Go to Patient Log In"):
        st.switch_page("pages/patient_auth.py")
    st.stop()

patient = db.get_patient(st.session_state.user_id)
if not patient:
    st.error("Your profile could not be found. It may have been deleted.")
    st.stop()

# --------------------------------------------------------------------------
# Sidebar profile summary
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    thumb = image_bytes_to_thumbnail(patient.get("profile_photo"), size=(120, 120))
    if thumb:
        st.image(thumb, width=100)
    else:
        st.markdown(f'<div class="mk-avatar-initials" style="width:72px;height:72px;font-size:1.6rem;">{initials(patient["name"])}</div>', unsafe_allow_html=True)
    st.markdown(f"**{patient['name']}**")
    st.caption(f"{patient['age']} yrs · {patient['gender']}")

    with st.expander("✏️ Change photo"):
        new_photo = st.file_uploader(
            "Upload a new profile photo", type=["png", "jpg", "jpeg"], key="pat_photo_uploader"
        )
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Save photo", use_container_width=True, disabled=new_photo is None):
                db.update_patient_fields(patient["id"], profile_photo=file_to_bytes(new_photo))
                st.success("Profile photo updated.")
                st.rerun()
        with pc2:
            if st.button("Remove photo", use_container_width=True, disabled=not patient.get("profile_photo")):
                db.update_patient_fields(patient["id"], profile_photo=None)
                st.success("Profile photo removed.")
                st.rerun()

    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    with st.expander("⚠️ Delete profile"):
        confirm_delete = st.checkbox("I understand this cannot be undone.", key="pat_del_confirm")
        if st.button("Delete Profile", type="primary", use_container_width=True, disabled=not confirm_delete):
            db.delete_patient(patient["id"])
            st.session_state.user_type = None
            st.session_state.user_id = None
            st.session_state.user_name = None
            st.success("Profile deleted.")
            st.rerun()

page_header("PATIENT DASHBOARD", f"Hello, {patient['name']}", "Manage your care below. Head to Home for AI Chat.")

tab_records, tab_uploads, tab_upcoming, tab_booking = st.tabs(
    ["🗂 Medical Records", "📤 Document Uploads", "📅 Upcoming Appointments", "🔎 Book a Doctor"]
)

# ==========================================================================
# TAB: Medical Records
# ==========================================================================
with tab_records:
    st.markdown("#### Chat Summaries")
    sessions = [s for s in db.list_chat_sessions(patient["id"]) if s["status"] == "closed"]
    if not sessions:
        st.info("No completed AI assessments yet.")
    for s in sessions:
        sev_badge = badge((s.get("severity") or "n/a").title(), "coral" if s.get("severity") == "severe" else "primary")
        with st.container():
            st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
            st.markdown(f"{pretty_datetime(s['created_at'])} &nbsp; {sev_badge}", unsafe_allow_html=True)
            st.write(s.get("summary") or "")
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### Prescriptions")
    rx_list = db.list_prescriptions(patient["id"])
    if not rx_list:
        st.info("No prescriptions on file yet.")
    for rx in rx_list:
        with st.container():
            st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
            source_badge = badge("AI Generated", "primary") if rx["source"] == "ai" else badge(f"By {rx.get('doctor_name') or 'Doctor'}", "neutral")
            st.markdown(f"{pretty_datetime(rx['created_at'])} &nbsp; {source_badge}", unsafe_allow_html=True)
            content = rx["content"]
            if rx["source"] == "ai":
                for med in content.get("medicines", []):
                    st.markdown(f"- **{med.get('name')}** — {med.get('dosage', '')}")
                for tip in content.get("advice", []):
                    st.markdown(f"- {tip}")
            else:
                st.write(content.get("notes", ""))
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================================
# TAB: Document Uploads
# ==========================================================================
with tab_uploads:
    st.markdown("#### Upload a prescription or medical document")
    st.caption("Keep scanned prescriptions, lab reports, or referral letters here for your own records.")
    with st.form("upload_doc_form"):
        doc_file = st.file_uploader("Choose a file", type=["png", "jpg", "jpeg", "pdf"])
        note = st.text_input("Label (optional)", placeholder="e.g. Blood test report, 12 Aug")
        submitted = st.form_submit_button("Upload", type="primary")
    if submitted:
        if not doc_file:
            st.error("Please choose a file first.")
        else:
            db.create_prescription(
                patient_id=patient["id"],
                content={"notes": note or doc_file.name, "uploaded": True},
                source="upload",
                uploaded_file=file_to_bytes(doc_file),
                uploaded_file_name=doc_file.name,
            )
            st.success("Document uploaded and saved to your records.")
            st.rerun()

    uploaded_docs = [r for r in db.list_prescriptions(patient["id"]) if r["source"] == "upload"]
    if uploaded_docs:
        st.markdown("##### Your uploaded documents")
        for rx in uploaded_docs:
            with st.container():
                st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
                st.markdown(f"📄 **{rx['content'].get('notes')}** &nbsp;·&nbsp; {pretty_datetime(rx['created_at'])}", unsafe_allow_html=True)
                if rx.get("uploaded_file"):
                    st.download_button(
                        "Download", data=rx["uploaded_file"],
                        file_name=rx.get("uploaded_file_name") or "document",
                        key=f"dl_{rx['id']}",
                    )
                st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================================
# TAB: Upcoming Appointments
# ==========================================================================
with tab_upcoming:
    upcoming = db.list_appointments_for_patient(patient["id"], status="upcoming")
    if not upcoming:
        st.info("No upcoming appointments. Book one from the **Book a Doctor** tab.")
    for appt in upcoming:
        with st.container():
            st.markdown('<div class="mk-card">', unsafe_allow_html=True)
            st.markdown(f"**{appt['doctor_name']}** &nbsp;·&nbsp; {badge(appt['specialization'], 'primary')}", unsafe_allow_html=True)
            st.caption(f"📅 {appt['scheduled_date']} at {appt['scheduled_time']} &nbsp; · &nbsp; 📍 {appt['chamber_address']}")
            st.caption(f"Fee: ₹{appt['fee']:.0f}")
            if st.button("Cancel appointment", key=f"pat_cancel_{appt['id']}"):
                db.update_appointment_status(appt["id"], "cancelled")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### Past Appointments")
    past = db.list_appointments_for_patient(patient["id"], status="past")
    for appt in past:
        with st.container():
            st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
            st.markdown(f"**{appt['doctor_name']}** &nbsp;·&nbsp; {appt['scheduled_date']}", unsafe_allow_html=True)
            existing_rating_key = f"rated_{appt['id']}"
            if st.session_state.get(existing_rating_key):
                st.caption("Thanks for your rating!")
            else:
                stars = st.slider("Rate this doctor", 1, 5, 5, key=f"stars_{appt['id']}")
                comment = st.text_input("Comment (optional)", key=f"comment_{appt['id']}")
                if st.button("Submit rating", key=f"submit_rating_{appt['id']}"):
                    db.add_doctor_rating(appt["doctor_id"], patient["id"], stars, comment, appt["id"])
                    st.session_state[existing_rating_key] = True
                    st.success("Thanks for your feedback!")
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================================
# TAB: Manual Doctor Booking
# ==========================================================================
with tab_booking:
    st.info("Use the full directory to search, filter, and book by specialization.")
    if st.button("Open Doctor Directory →", type="primary"):
        st.switch_page("pages/doctor_directory.py")
