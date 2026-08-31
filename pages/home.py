import json

import streamlit as st

import db
from ai_helper import assess_severity, chat_reply, generate_prescription, generate_summary, get_status, opening_message
from bot_companion import render_companion
from styles import badge, page_header, vitals_strip
from utils import format_schedule_slots, pretty_datetime

user_type = st.session_state.get("user_type")

# ==========================================================================
# LOGGED IN AS PATIENT — Home becomes the AI Chat experience
# ==========================================================================
if user_type == "patient":
    patient = db.get_patient(st.session_state.user_id)
    if not patient:
        st.error("Your profile could not be found. It may have been deleted.")
        st.stop()

    MIN_TURNS_BEFORE_ASSESSMENT = 5  # patient messages, per spec ("after 5+ turns")

    page_header("AI CHAT", f"Hello, {patient['name']}", "Chat with the AI assistant to get triaged.")

    ai_status = get_status()
    if not ai_status["connected"]:
        st.warning(
            f"⚠️ The AI assistant isn't connected right now ({ai_status['detail']}). "
            "You can still start a chat, but replies will show a connection notice instead "
            "of real triage — fix this in the sidebar under 'Set Gemini API key'.",
        )

    if st.session_state.active_chat_session_id is None:
        render_companion(st.empty(), "sleepy")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.caption("Start a new conversation with the AI assistant to get triaged.")
        with c2:
            if st.button("Start new chat", type="primary", use_container_width=True):
                session_id = db.create_chat_session(patient["id"])
                opener = opening_message(patient["name"])
                db.save_chat_messages(session_id, [{"role": "assistant", "content": opener}])
                st.session_state.active_chat_session_id = session_id
                st.rerun()

        past_sessions = db.list_chat_sessions(patient["id"])
        if past_sessions:
            st.markdown("##### Previous conversations")
            for s in past_sessions:
                sev = s.get("severity")
                sev_badge = badge(sev.title(), "coral" if sev == "severe" else "primary") if sev else badge("In progress", "neutral")
                with st.container():
                    st.markdown('<div class="mk-card-flat">', unsafe_allow_html=True)
                    st.markdown(f"{pretty_datetime(s['created_at'])} &nbsp; {sev_badge}", unsafe_allow_html=True)
                    if s.get("summary"):
                        st.caption(s["summary"])
                    if st.button("Resume / view", key=f"resume_{s['id']}"):
                        st.session_state.active_chat_session_id = s["id"]
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        session = db.get_chat_session(st.session_state.active_chat_session_id)
        messages = session["messages"]

        if st.button("← Back to conversations"):
            st.session_state.active_chat_session_id = None
            st.rerun()

        companion_slot = st.empty()  # the animated AI companion figurine lives here

        chat_box = st.container(height=420)
        with chat_box:
            for m in messages:
                css_class = "mk-chat-patient" if m["role"] == "user" else "mk-chat-doc"
                label = "You" if m["role"] == "user" else "MediKiosk Assistant"
                chat_box.markdown(
                    f'<div class="{css_class}"><b>{label}:</b><br/>{m["content"]}</div>',
                    unsafe_allow_html=True,
                )

        patient_turns = sum(1 for m in messages if m["role"] == "user")
        is_closed = session["status"] == "closed"

        if is_closed:
            sev = session.get("severity")
            if sev == "severe":
                render_companion(companion_slot, "concerned")
                st.markdown(
                    f"""<div class="mk-alert-emergency">
                    🚨 <strong>This looks like it may need urgent attention.</strong><br/>
                    Based on your symptoms, we recommend seeing a
                    <strong>{session.get('specialization_suggested', 'specialist')}</strong> as soon as possible.
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button("Find a " + session.get("specialization_suggested", "Specialist") + " now →",
                              type="primary"):
                    st.session_state.directory_specialization_filter = session.get("specialization_suggested", "All")
                    st.switch_page("pages/doctor_directory.py")
            else:
                st.success("Assessment complete: this looks like a casual, non-severe case.")
                st.markdown("**Summary:** " + (session.get("summary") or ""))

                rx_existing = [r for r in db.list_prescriptions(patient["id"]) if r.get("chat_session_id") == session["id"]]
                # first reveal gets a celebratory bounce; once guidance already exists, a calmer wink
                render_companion(companion_slot, "happy" if not rx_existing else "wink")
                if not rx_existing:
                    if st.button("Generate AI prescription (OTC guidance)", type="primary"):
                        with st.spinner("Preparing general guidance…"):
                            rx = generate_prescription(messages, session.get("summary") or "")
                        db.create_prescription(
                            patient_id=patient["id"], content=rx, source="ai",
                            chat_session_id=session["id"],
                        )
                        st.rerun()
                else:
                    rx = rx_existing[0]["content"]
                    st.markdown("##### 💊 AI-Generated Guidance")
                    st.caption(rx.get("disclaimer", ""))
                    for med in rx.get("medicines", []):
                        st.markdown(f"- **{med.get('name')}** — {med.get('dosage', '')} · _{med.get('notes', '')}_")
                    for tip in rx.get("advice", []):
                        st.markdown(f"- {tip}")

                if st.button("Browse doctors anyway"):
                    st.switch_page("pages/doctor_directory.py")
        else:
            last_role = messages[-1]["role"] if messages else None
            if last_role == "assistant":
                waiting_state = "curious" if patient_turns == 0 else "talking"
            else:
                waiting_state = "idle"
            render_companion(companion_slot, waiting_state)

            if patient_turns >= MIN_TURNS_BEFORE_ASSESSMENT:
                st.info("We have enough information to assess this conversation.")
                b1, b2 = st.columns(2)
                with b1:
                    run_assessment = st.button("Get my assessment", type="primary", use_container_width=True)
                with b2:
                    keep_chatting = st.button("I have more to add", use_container_width=True)
                if run_assessment:
                    with st.spinner("Reviewing your symptoms…"):
                        result = assess_severity(messages)
                        summary = generate_summary(messages)
                    db.finalize_chat_session(
                        session["id"], summary=summary,
                        severity=result["severity"], specialization=result.get("specialization", ""),
                    )
                    st.rerun()
                if keep_chatting:
                    st.session_state[f"force_continue_{session['id']}"] = True

            show_input = patient_turns < MIN_TURNS_BEFORE_ASSESSMENT or st.session_state.get(f"force_continue_{session['id']}")
            if show_input:
                # Dynamic quick-reply suggestions from the last assistant turn
                last_assistant = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
                suggestions = last_assistant.get("suggestions", []) if last_assistant else []
                if suggestions:
                    st.caption("Quick replies")
                    scols = st.columns(len(suggestions))
                    for i, sug in enumerate(suggestions):
                        if scols[i].button(sug, key=f"sugg_{session['id']}_{len(messages)}_{i}"):
                            st.session_state[f"pending_input_{session['id']}"] = sug

                user_text = st.chat_input("Describe your symptoms…")
                pending = st.session_state.pop(f"pending_input_{session['id']}", None)
                final_text = user_text or pending

                if final_text:
                    messages.append({"role": "user", "content": final_text})
                    render_companion(companion_slot, "thinking")
                    with st.spinner("Thinking…"):
                        ai_turn = chat_reply(patient["name"], messages)
                    messages.append({
                        "role": "assistant", "content": ai_turn["reply"], "suggestions": ai_turn["suggestions"],
                    })
                    db.save_chat_messages(session["id"], messages)
                    st.rerun()

# ==========================================================================
# LOGGED IN AS DOCTOR — simple signed-in landing, no signup cards
# ==========================================================================
elif user_type == "doctor":
    doctor = db.get_doctor(st.session_state.user_id)
    doctor_name = doctor["name"] if doctor else st.session_state.get("user_name", "")

    page_header("MEDIKIOSK", f"Welcome back, Dr. {doctor_name}", "Manage your practice from the dashboard below.")

    st.markdown(
        """
<div class="mk-disclaimer">
⚠️ <strong>Medical disclaimer:</strong> MediKiosk's AI assistant provides general triage guidance
only and is <strong>not a substitute for professional medical advice, diagnosis, or treatment</strong>.
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")

    d1, d2 = st.columns([1, 1.3], gap="large")
    with d1:
        st.markdown(
            """
<div class="mk-card">
<div class="mk-avatar-initials">🩺</div>
<h3>Doctor Dashboard</h3>
<p class="mk-muted">Review appointments, view AI triage summaries, and manage prescriptions.</p>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("Go to Dashboard →", use_container_width=True, type="primary"):
            st.switch_page("pages/doctor_dashboard.py")

    with d2:
        if doctor:
            schedule = json.loads(doctor.get("schedule") or "{}")
            schedule_summary = format_schedule_slots(schedule.get("slots"))
            if schedule_summary:
                schedule_html = "".join(
                    f'<p style="margin:0.25rem 0;">🕐 {line}</p>' for line in schedule_summary.split("\n")
                )
            else:
                schedule_html = '<p class="mk-muted">No schedule slots set yet.</p>'

            addresses = json.loads(doctor.get("chamber_addresses") or "[]")
            addresses_html = ""
            if addresses:
                addresses_html = "<hr class='mk-divider'/>" + "".join(
                    f'<p class="mk-muted" style="margin:0.2rem 0;">📍 Chamber {i}: {addr}</p>'
                    for i, addr in enumerate(addresses, start=1)
                )
        else:
            schedule_html = '<p class="mk-muted">Schedule unavailable.</p>'
            addresses_html = ""

        st.markdown(
            f"""
<div class="mk-card">
<h3>🗓️ Your Schedule</h3>
{schedule_html}
{addresses_html}
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("Edit schedule →", use_container_width=True):
            st.switch_page("pages/doctor_dashboard.py")

# ==========================================================================
# LOGGED OUT — original marketing / sign-up entry point
# ==========================================================================
else:
    st.markdown(
        "<div class='mk-kicker'>WALK-UP TELEHEALTH KIOSK</div>"
        "<div class='mk-page-title' style='font-size:3rem;'>MEDIKIOSK</div>"
        "<div class='mk-subtitle' style='font-size:1.15rem;'>"
        "AI-guided triage, verified doctors, and same-day booking — all from one screen."
        "</div>",
        unsafe_allow_html=True,
    )
    vitals_strip()

    st.markdown(
        """
<div class="mk-disclaimer">
⚠️ <strong>Medical disclaimer:</strong> MediKiosk's AI assistant provides general triage guidance
only and is <strong>not a substitute for professional medical advice, diagnosis, or treatment</strong>.
Always consult a qualified doctor for medical concerns. In a medical emergency, contact your local
emergency services immediately.
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            f"""
<div class="mk-card">
<div class="mk-avatar-initials">🧑‍🦰</div>
<h3>I'm a Patient</h3>
<p class="mk-muted">Chat with the AI assistant, get triaged, book a doctor, and keep all your
records in one place.</p>
{badge("Free AI triage", "primary")} {badge("Book instantly", "neutral")}
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("Continue as Patient →", use_container_width=True, type="primary"):
            st.switch_page("pages/patient_auth.py")

    with col2:
        st.markdown(
            f"""
<div class="mk-card">
<div class="mk-avatar-initials">🩺</div>
<h3>I'm a Doctor</h3>
<p class="mk-muted">Get verified, manage your chamber, review AI-triaged patients, and track
appointments and prescriptions.</p>
{badge("Verified profiles", "primary")} {badge("Manage schedule", "neutral")}
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("Continue as Doctor →", use_container_width=True, type="primary"):
            st.switch_page("pages/doctor_auth.py")

    st.write("")
    st.markdown("<hr class='mk-divider'/>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="mk-card-flat"><div class="mk-kicker">STEP 01</div>'
            "<b>Describe your symptoms</b><p class='mk-muted'>Talk to the AI assistant like you would "
            "a friendly front-desk nurse.</p></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="mk-card-flat"><div class="mk-kicker">STEP 02</div>'
            "<b>Get triaged instantly</b><p class='mk-muted'>Severe cases are routed to the right "
            "specialist right away.</p></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="mk-card-flat"><div class="mk-kicker">STEP 03</div>'
            "<b>Book or get guidance</b><p class='mk-muted'>Casual cases get self-care advice; "
            "everyone can browse and book verified doctors.</p></div>",
            unsafe_allow_html=True,
        )
