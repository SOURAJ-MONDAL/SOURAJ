import datetime
import json

import streamlit as st

import db
from styles import badge, page_header
from utils import (
    file_to_bytes,
    hospital_affiliations_editor,
    image_bytes_to_thumbnail,
    initials,
    pretty_datetime,
    schedule_slot_editor,
    time_to_minutes,
)

if st.session_state.get("user_type") != "doctor":
    st.warning("Please log in as a doctor to view this page.")
    if st.button("Go to Doctor Log In"):
        st.switch_page("pages/doctor_auth.py")
    st.stop()

doctor = db.get_doctor(st.session_state.user_id)
if not doctor:
    st.error("Your profile could not be found. It may have been deleted.")
    st.stop()

# --------------------------------------------------------------------------
# Sidebar: profile photo, rating, fee editor, delete profile
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    thumb = image_bytes_to_thumbnail(doctor.get("profile_photo"), size=(120, 120))
    if thumb:
        st.image(thumb, width=100)
    else:
        st.markdown(f'<div class="mk-avatar-initials" style="width:72px;height:72px;font-size:1.6rem;">{initials(doctor["name"])}</div>', unsafe_allow_html=True)

    st.markdown(f"**Dr. {doctor['name']}**")
    st.caption(doctor["specialization"])
    rating_txt = f"⭐ {doctor['avg_rating']:.1f} / 5 ({doctor['rating_count']} ratings)" if doctor["rating_count"] else "⭐ No ratings yet"
    st.markdown(rating_txt)

    with st.expander("✏️ Change photo"):
        new_photo = st.file_uploader(
            "Upload a new profile photo", type=["png", "jpg", "jpeg"], key="doc_photo_uploader"
        )
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Save photo", use_container_width=True, disabled=new_photo is None):
                db.update_doctor_fields(doctor["id"], profile_photo=file_to_bytes(new_photo))
                st.success("Profile photo updated.")
                st.rerun()
        with pc2:
            if st.button("Remove photo", use_container_width=True, disabled=not doctor.get("profile_photo")):
                db.update_doctor_fields(doctor["id"], profile_photo=None)
                st.success("Profile photo removed.")
                st.rerun()

    new_fee = st.number_input("Consultation fee (₹)", min_value=0, step=50, value=int(doctor["fee"]))
    if new_fee != doctor["fee"]:
        if st.button("Save fee", use_container_width=True):
            db.update_doctor_fields(doctor["id"], fee=float(new_fee))
            st.success("Fee updated.")
            st.rerun()

    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    with st.expander("⚠️ Delete profile"):
        st.caption("This permanently removes your profile from MediKiosk.")
        confirm_delete = st.checkbox("I understand this cannot be undone.")
        if st.button("Delete Profile", type="primary", use_container_width=True, disabled=not confirm_delete):
            db.delete_doctor(doctor["id"])
            st.session_state.user_type = None
            st.session_state.user_id = None
            st.session_state.user_name = None
            st.success("Profile deleted.")
            st.rerun()

# --------------------------------------------------------------------------
# Main content
# --------------------------------------------------------------------------
page_header("DOCTOR DASHBOARD", f"Welcome, Dr. {doctor['name']}", "Manage your appointments, patients, and prescriptions.")

status_badge = badge("Verified", "primary") if doctor["verification_status"] == "accepted" else badge(doctor["verification_status"].title(), "amber")
st.markdown(status_badge, unsafe_allow_html=True)
st.write("")

tab_upcoming, tab_past, tab_prescriptions, tab_profile = st.tabs(
    ["📅 Upcoming Appointments", "🗂 Past Appointments", "💊 Prescriptions", "⚙️ Profile"]
)

# ---- Upcoming ----
with tab_upcoming:
    upcoming = db.list_appointments_for_doctor(doctor["id"], status="upcoming")
    if not upcoming:
        st.info("No upcoming appointments.")
    for appt in upcoming:
        with st.container():
            st.markdown('<div class="mk-card">', unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{appt['patient_name']}** &nbsp;·&nbsp; {appt['patient_age']} yrs, {appt['patient_gender']}", unsafe_allow_html=True)
                st.caption(f"📅 {appt['scheduled_date']} at {appt['scheduled_time']}")
                if appt.get("reason"):
                    st.caption(f"Reason: {appt['reason']}")

                sessions = [s for s in db.list_chat_sessions(appt["patient_id"]) if s["status"] == "closed"]
                if sessions:
                    with st.expander("View latest AI triage summary"):
                        latest = sessions[0]
                        st.write(latest.get("summary") or "No summary available.")
                        sev_kind = "coral" if latest.get("severity") == "severe" else "primary"
                        st.markdown(badge((latest.get("severity") or "n/a").title(), sev_kind), unsafe_allow_html=True)
            with c2:
                if st.button("Mark completed", key=f"complete_{appt['id']}", use_container_width=True):
                    db.update_appointment_status(appt["id"], "past")
                    st.rerun()
                if st.button("Cancel", key=f"cancel_{appt['id']}", use_container_width=True):
                    db.update_appointment_status(appt["id"], "cancelled")
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ---- Past ----
with tab_past:
    past = db.list_appointments_for_doctor(doctor["id"], status="past")
    if not past:
        st.info("No past appointments yet.")
    for appt in past:
        with st.container():
            st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
            st.markdown(f"**{appt['patient_name']}** &nbsp;·&nbsp; {appt['scheduled_date']} at {appt['scheduled_time']}", unsafe_allow_html=True)
            st.caption(f"Fee: ₹{appt['fee']:.0f}")

            with st.expander("Add prescription for this visit"):
                notes = st.text_area("Notes / medicines", key=f"rx_notes_{appt['id']}",
                                      placeholder="e.g. Paracetamol 500mg, twice daily for 3 days")
                if st.button("Save prescription", key=f"rx_save_{appt['id']}"):
                    db.create_prescription(
                        patient_id=appt["patient_id"],
                        content={"notes": notes, "written_by": f"Dr. {doctor['name']}"},
                        source="doctor",
                        doctor_id=doctor["id"],
                        doctor_name=f"Dr. {doctor['name']}",
                    )
                    st.success("Prescription saved to patient's record.")
            st.markdown("</div>", unsafe_allow_html=True)

# ---- Prescriptions ----
with tab_prescriptions:
    rx_list = db.list_prescriptions_for_doctor(doctor["id"])
    if not rx_list:
        st.info("You haven't written any prescriptions yet — add one from the Past Appointments tab.")
    for rx in rx_list:
        with st.container():
            st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
            st.markdown(f"**{rx['patient_name']}** &nbsp;·&nbsp; {pretty_datetime(rx['created_at'])}", unsafe_allow_html=True)
            st.write(rx["content"].get("notes", ""))
            st.markdown("</div>", unsafe_allow_html=True)

# ---- Profile ----
with tab_profile:
    st.markdown("#### Profile Details")
    addresses = json.loads(doctor.get("chamber_addresses") or "[]")
    affiliations = json.loads(doctor.get("hospital_affiliations") or "[]")
    schedule = json.loads(doctor.get("schedule") or "{}")
    existing_slots = schedule.get("slots") or []
    chamber_count = doctor.get("chamber_count") or 1

    # No st.form here: the schedule slot editor needs an immediate rerun
    # when rows are added/removed, and widgets inside st.form don't trigger
    # a rerun until the whole form is submitted.
    phone = st.text_input("Phone", value=doctor["phone"])

    st.markdown("**Hospital affiliation(s)**")
    st.caption("Add every hospital you practice at. Use ➕ Add hospital for more.")
    existing_hospital_names = [a.get("name", "") for a in affiliations]
    hospital_names = hospital_affiliations_editor("doctor_edit", initial_hospitals=existing_hospital_names)

    st.markdown(f"**Chamber address{'es' if chamber_count > 1 else ''}**")
    chamber_addresses = []
    for i in range(int(chamber_count)):
        existing = addresses[i] if i < len(addresses) else ""
        addr = st.text_area(
            f"Address (Chamber {i + 1})",
            value=existing,
            key=f"doctor_edit_chamber_addr_{i}",
        )
        chamber_addresses.append(addr)

    st.markdown("**Available schedule**")
    st.caption("Add a row for each day/time you're available. Use ➕ Add slot for more.")
    hospital_options = [h.strip() for h in hospital_names if h and h.strip()]
    if not hospital_options:
        hospital_options = ["Not specified"]
    schedule_slots = schedule_slot_editor(
        "doctor_edit", chamber_count, initial_slots=existing_slots, hospital_options=hospital_options
    )

    save = st.button("Save changes", type="primary")

    if save:
        from utils import is_valid_phone
        errors = []
        if not is_valid_phone(phone):
            errors.append("Phone number must be exactly 10 digits.")
        for slot in schedule_slots:
            start_min = time_to_minutes(slot["start"])
            end_min = time_to_minutes(slot["end"])
            if start_min is None or end_min is None or end_min <= start_min:
                errors.append(
                    f"On {slot['day']}, the 'To' time must be later than the 'From' time."
                )

        if errors:
            for e in errors:
                st.error(e)
        else:
            db.update_doctor_fields(
                doctor["id"],
                phone=phone.strip(),
                chamber_addresses=[a.strip() for a in chamber_addresses],
                schedule={"slots": schedule_slots},
            )
            clean_hospitals = [h.strip() for h in hospital_names if h and h.strip()]
            mapped = [db.auto_map_hospital_affiliation(h) for h in clean_hospitals]
            mapped = [m for m in mapped if m]
            if mapped:
                db.update_doctor_fields(
                    doctor["id"],
                    hospital_affiliations=[{"id": m["id"], "name": m["name"]} for m in mapped],
                )
            st.success("Profile updated.")
            st.rerun()
