import datetime
import json

import streamlit as st

import db
from styles import badge, page_header
from utils import format_schedule_slots, image_bytes_to_thumbnail, initials

page_header("FIND A DOCTOR", "Doctor Directory", "Browse verified doctors, compare fees, and book an appointment.")

specializations = ["All"] + db.list_specializations()
default_index = 0
if st.session_state.get("directory_specialization_filter") in specializations:
    default_index = specializations.index(st.session_state.directory_specialization_filter)

f1, f2 = st.columns([2, 1])
with f1:
    chosen_spec = st.selectbox("Filter by specialization", specializations, index=default_index)
with f2:
    sort_by = st.selectbox("Sort by", ["Highest rated", "Lowest fee", "Name"])

st.session_state.directory_specialization_filter = chosen_spec

doctors = db.list_doctors(specialization=chosen_spec, verified_only=True)

if sort_by == "Lowest fee":
    doctors.sort(key=lambda d: d["fee"])
elif sort_by == "Name":
    doctors.sort(key=lambda d: d["name"])
# "Highest rated" already the default DB order

if not doctors:
    st.info("No verified doctors found for this filter yet. Please check back soon.")
else:
    st.caption(f"{len(doctors)} doctor(s) found")

for doc in doctors:
    addresses = json.loads(doc.get("chamber_addresses") or "[]")
    affiliations = json.loads(doc.get("hospital_affiliations") or "[]")
    schedule = json.loads(doc.get("schedule") or "{}")

    with st.container():
        st.markdown('<div class="mk-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 4, 2])
        with c1:
            thumb = image_bytes_to_thumbnail(doc.get("profile_photo"))
            if thumb:
                st.image(thumb, width=72)
            else:
                st.markdown(
                    f'<div class="mk-avatar-initials">{initials(doc["name"])}</div>',
                    unsafe_allow_html=True,
                )
        with c2:
            rating_txt = f"⭐ {doc['avg_rating']:.1f} ({doc['rating_count']})" if doc["rating_count"] else "⭐ New"
            st.markdown(f"### Dr. {doc['name']}")
            st.markdown(
                badge(doc["specialization"], "primary") + " " + badge(rating_txt, "neutral"),
                unsafe_allow_html=True,
            )
            if affiliations:
                st.caption("🏥 " + ", ".join(a["name"] for a in affiliations))
            if addresses:
                if len(addresses) > 1:
                    st.caption(f"📍 {addresses[0]} · +{len(addresses) - 1} more chamber{'s' if len(addresses) > 2 else ''}")
                else:
                    st.caption("📍 " + addresses[0])
            schedule_summary = format_schedule_slots(schedule.get("slots"))
            if schedule_summary:
                for line in schedule_summary.split("\n"):
                    st.caption("🕐 " + line)
        with c3:
            st.markdown(f"<div style='font-size:1.4rem;font-weight:700;color:var(--mk-primary);'>₹{doc['fee']:.0f}</div>", unsafe_allow_html=True)
            st.caption("consultation fee")
            book_clicked = st.button("Book appointment", key=f"book_{doc['id']}", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if book_clicked:
        st.session_state.booking_doctor_id = doc["id"]

    if st.session_state.get("booking_doctor_id") == doc["id"]:
        with st.container():
            st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
            if st.session_state.get("user_type") == "doctor":
                st.warning("You're currently signed in as a doctor. Log out first to book an appointment as a patient.")
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("Log out", key=f"logout_prompt_{doc['id']}"):
                        for key in ("user_type", "user_id", "user_name", "active_chat_session_id", "booking_doctor_id"):
                            st.session_state[key] = None
                        st.rerun()
                with bc2:
                    if st.button("Cancel", key=f"cancel_prompt_{doc['id']}"):
                        st.session_state.booking_doctor_id = None
                        st.rerun()
            elif st.session_state.get("user_type") != "patient":
                st.warning("Please log in as a patient to book an appointment.")
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("Go to Patient Log In", key=f"login_prompt_{doc['id']}"):
                        st.switch_page("pages/patient_auth.py")
                with bc2:
                    if st.button("Cancel", key=f"cancel_prompt_{doc['id']}"):
                        st.session_state.booking_doctor_id = None
                        st.rerun()
            else:
                with st.form(f"booking_form_{doc['id']}"):
                    b1, b2 = st.columns(2)
                    with b1:
                        appt_date = st.date_input(
                            "Preferred date", min_value=datetime.date.today(),
                            value=datetime.date.today() + datetime.timedelta(days=1),
                        )
                    with b2:
                        appt_time = st.time_input("Preferred time", value=datetime.time(10, 0))
                    reason = st.text_area("Reason for visit (optional)")
                    if len(addresses) > 1:
                        address_choice = st.selectbox(
                            "Chamber",
                            addresses,
                            format_func=lambda a: f"📍 {a}",
                            key=f"chamber_choice_{doc['id']}",
                        )
                    else:
                        address_choice = addresses[0] if addresses else "Chamber address on file"
                        st.caption(f"📍 Chamber: {address_choice}")
                    confirm = st.form_submit_button("Confirm Booking", type="primary", use_container_width=True)

                if confirm:
                    db.create_appointment(
                        patient_id=st.session_state.user_id,
                        doctor_id=doc["id"],
                        doctor_name=f"Dr. {doc['name']}",
                        specialization=doc["specialization"],
                        chamber_address=address_choice,
                        scheduled_date=str(appt_date),
                        scheduled_time=appt_time.strftime("%I:%M %p"),
                        fee=doc["fee"],
                        reason=reason,
                    )
                    st.success(f"✅ Appointment booked with Dr. {doc['name']} on {appt_date} at {appt_time.strftime('%I:%M %p')}.")
                    st.session_state.booking_doctor_id = None
            st.markdown("</div>", unsafe_allow_html=True)
