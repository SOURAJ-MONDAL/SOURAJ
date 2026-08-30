"""
utils.py
Shared validation, formatting, and small helper utilities for MediKiosk.
Keeping these in one place avoids re-implementing regex/hash logic per page.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import os
import re
import secrets
from datetime import datetime
from typing import Optional

from PIL import Image

# --------------------------------------------------------------------------
# Validation patterns
# --------------------------------------------------------------------------

PHONE_RE = re.compile(r"^\d{10}$")
DOCTOR_AGE_RE = re.compile(r"^\d{1,2}$")
PATIENT_AGE_RE = re.compile(r"^\d{1,3}$")
# min 8 chars, 1 uppercase, 1 digit, 1 special char
PASSWORD_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")

GENDERS = ["Male", "Female", "Others"]


def is_valid_phone(value: str) -> bool:
    return bool(PHONE_RE.match((value or "").strip()))


def is_valid_doctor_age(value: str) -> bool:
    v = (value or "").strip()
    return bool(DOCTOR_AGE_RE.match(v)) and 18 <= int(v) <= 99


def is_valid_patient_age(value: str) -> bool:
    v = (value or "").strip()
    return bool(PATIENT_AGE_RE.match(v)) and 0 <= int(v) <= 130


def is_valid_password(value: str) -> bool:
    return bool(PASSWORD_RE.match(value or ""))


def password_hint() -> str:
    return "At least 8 characters, with 1 uppercase letter, 1 number, and 1 special character."


# --------------------------------------------------------------------------
# Password hashing (stdlib only — PBKDF2-HMAC-SHA256, no external dependency)
# --------------------------------------------------------------------------

_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest_hex = stored_hash.split("$")
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
        return hmac.compare_digest(expected.hex(), digest_hex)
    except Exception:
        return False


# --------------------------------------------------------------------------
# Image helpers
# --------------------------------------------------------------------------

def image_bytes_to_thumbnail(data: Optional[bytes], size=(96, 96)) -> Optional[bytes]:
    """Return a resized PNG thumbnail (bytes) for avatar-style display, or None."""
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail(size)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def file_to_bytes(uploaded_file) -> Optional[bytes]:
    if uploaded_file is None:
        return None
    return uploaded_file.getvalue()


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def pretty_datetime(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso_str or ""


def initials(name: str) -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]


def time_options(interval_minutes: int = 30) -> list[str]:
    """Return a list of 12-hour time strings (e.g. '09:00 AM') at the given
    interval, covering a full day. Used to populate schedule dropdowns."""
    options = []
    for minutes in range(0, 24 * 60, interval_minutes):
        hour24, minute = divmod(minutes, 60)
        suffix = "AM" if hour24 < 12 else "PM"
        hour12 = hour24 % 12 or 12
        options.append(f"{hour12:02d}:{minute:02d} {suffix}")
    return options


TIME_OPTIONS = time_options()


def time_to_minutes(time_str: str) -> Optional[int]:
    """Convert a '09:00 AM' style string to minutes-since-midnight, or None."""
    try:
        dt = datetime.strptime(time_str.strip(), "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except Exception:
        return None


def format_schedule_slots(slots: Optional[list]) -> str:
    """Render a list of {'day','start','end','chamber','hospital'} slot
    dicts as a short human-readable multi-line summary, e.g.:
        Tuesday, Thursday, Saturday · 05:00 PM – 08:00 PM (Chamber 1) @ City Care Hospital
    Consecutive days sharing the same time range, chamber, and hospital are
    grouped together.
    """
    if not slots:
        return ""

    order = {d: i for i, d in enumerate(DAYS_OF_WEEK)}
    groups: dict[tuple, list[str]] = {}
    for s in slots:
        key = (s.get("start", ""), s.get("end", ""), s.get("chamber", 1), s.get("hospital", ""))
        groups.setdefault(key, []).append(s.get("day", ""))

    lines = []
    for (start, end, chamber, hospital), days in groups.items():
        days_sorted = sorted(set(days), key=lambda d: order.get(d, 99))
        chamber_txt = f" (Chamber {chamber})" if chamber else ""
        hospital_txt = f" @ {hospital}" if hospital else ""
        lines.append(f"{', '.join(days_sorted)} · {start} – {end}{chamber_txt}{hospital_txt}")
    return "\n".join(lines)


def schedule_slot_editor(
    key_prefix: str,
    chamber_count: int,
    initial_slots: Optional[list] = None,
    hospital_options: Optional[list] = None,
) -> list[dict]:
    """
    Render a repeatable Day / From / To / Chamber / Hospital picker for
    building a doctor's schedule, backed by st.session_state so rows can be
    added or removed. Returns the current list of
    {'day', 'start', 'end', 'chamber', 'hospital'} dicts, one per rendered row.

    Must be called as a plain (non-st.form) widget block, since add/remove
    needs an immediate rerun to redraw the rows — the same reason chamber
    address fields aren't inside a form either.
    """
    import streamlit as st

    count_key = f"{key_prefix}_slot_count"
    if count_key not in st.session_state:
        st.session_state[count_key] = max(1, len(initial_slots or []) or 1)

    default_start_idx = TIME_OPTIONS.index("09:00 AM") if "09:00 AM" in TIME_OPTIONS else 0
    default_end_idx = TIME_OPTIONS.index("01:00 PM") if "01:00 PM" in TIME_OPTIONS else 0
    chamber_count = int(chamber_count)
    chamber_choices = list(range(1, chamber_count + 1))
    hospital_choices = list(hospital_options) if hospital_options else ["Not specified"]
    if not hospital_choices:
        hospital_choices = ["Not specified"]

    slots = []
    slot_total = st.session_state[count_key]
    for i in range(slot_total):
        seed = initial_slots[i] if initial_slots and i < len(initial_slots) else {}
        show_labels = i == 0

        row1 = st.columns([2, 2, 2])
        with row1[0]:
            day = st.selectbox(
                "Day", DAYS_OF_WEEK,
                index=DAYS_OF_WEEK.index(seed["day"]) if seed.get("day") in DAYS_OF_WEEK else 0,
                key=f"{key_prefix}_day_{i}",
                label_visibility="visible" if show_labels else "collapsed",
            )
        with row1[1]:
            start = st.selectbox(
                "From", TIME_OPTIONS,
                index=TIME_OPTIONS.index(seed["start"]) if seed.get("start") in TIME_OPTIONS else default_start_idx,
                key=f"{key_prefix}_start_{i}",
                label_visibility="visible" if show_labels else "collapsed",
            )
        with row1[2]:
            end = st.selectbox(
                "To", TIME_OPTIONS,
                index=TIME_OPTIONS.index(seed["end"]) if seed.get("end") in TIME_OPTIONS else default_end_idx,
                key=f"{key_prefix}_end_{i}",
                label_visibility="visible" if show_labels else "collapsed",
            )

        row2 = st.columns([1, 3])
        with row2[0]:
            seed_chamber = seed.get("chamber", 1)
            chamber = st.selectbox(
                "Chamber", chamber_choices,
                index=chamber_choices.index(seed_chamber) if seed_chamber in chamber_choices else 0,
                format_func=lambda c: f"Chamber {c}",
                key=f"{key_prefix}_chamber_{i}",
                label_visibility="visible" if show_labels else "collapsed",
            )
        with row2[1]:
            seed_hospital = seed.get("hospital")
            hosp_index = hospital_choices.index(seed_hospital) if seed_hospital in hospital_choices else 0
            hospital = st.selectbox(
                "Hospital", hospital_choices,
                index=hosp_index,
                key=f"{key_prefix}_hospital_{i}",
                label_visibility="visible" if show_labels else "collapsed",
            )

        slots.append({"day": day, "start": start, "end": end, "chamber": int(chamber), "hospital": hospital})

        if i < slot_total - 1:
            st.markdown("<div style='margin-bottom:0.6rem;'></div>", unsafe_allow_html=True)

    add_col, remove_col, _sp = st.columns([1.3, 1.6, 4])
    with add_col:
        if st.button("➕ Add slot", key=f"{key_prefix}_add"):
            st.session_state[count_key] += 1
            st.rerun()
    with remove_col:
        if st.session_state[count_key] > 1:
            if st.button("➖ Remove last", key=f"{key_prefix}_remove"):
                st.session_state[count_key] -= 1
                st.rerun()

    return slots


def hospital_affiliations_editor(
    key_prefix: str,
    initial_hospitals: Optional[list] = None,
) -> list[str]:
    """
    Render a repeatable text-input list for a doctor's hospital
    affiliations, backed by st.session_state so rows can be added or
    removed — mirrors the ➕/➖ pattern used by schedule_slot_editor().
    Returns the current list of hospital name strings, one per rendered
    row (not yet stripped/filtered — callers should drop blanks).

    Must be called as a plain (non-st.form) widget block, since add/remove
    needs an immediate rerun to redraw the rows.
    """
    import streamlit as st

    count_key = f"{key_prefix}_hosp_count"
    if count_key not in st.session_state:
        st.session_state[count_key] = max(1, len(initial_hospitals or []) or 1)

    hospitals = []
    row_total = st.session_state[count_key]
    for i in range(row_total):
        seed = initial_hospitals[i] if initial_hospitals and i < len(initial_hospitals) else ""
        label = "Hospital affiliation*" if i == 0 else f"Hospital affiliation {i + 1}"
        h = st.text_input(
            label,
            value=seed,
            key=f"{key_prefix}_hosp_{i}",
            placeholder="e.g. City Care General Hospital",
            label_visibility="visible" if i == 0 else "collapsed",
        )
        hospitals.append(h)

    add_col, remove_col, _sp = st.columns([1.3, 1.6, 4])
    with add_col:
        if st.button("➕ Add hospital", key=f"{key_prefix}_hosp_add"):
            st.session_state[count_key] += 1
            st.rerun()
    with remove_col:
        if st.session_state[count_key] > 1:
            if st.button("➖ Remove last", key=f"{key_prefix}_hosp_remove"):
                st.session_state[count_key] -= 1
                st.rerun()

    return hospitals


def get_api_key() -> Optional[str]:
    """Resolve the Gemini API key from Streamlit secrets or environment."""
    try:
        import streamlit as st
        if "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GOOGLE_API_KEY")


# --------------------------------------------------------------------------
# Client-side "digits only" enforcement
# --------------------------------------------------------------------------

def restrict_to_digits(field_label: str, max_length: Optional[int] = None) -> None:
    """
    Best-effort client-side enforcement that keeps a specific st.text_input
    (matched by its exact visible label text) digits-only, and — if
    max_length is given — truncated to that many characters.

    Sanitization runs on every native 'input' event rather than only on
    keydown/paste. This matters because keydown+paste alone can be bypassed
    by browser autofill or some paste/drag-drop paths that set the input's
    value directly without firing those specific events; the 'input' event
    fires for effectively every way a value can change, so it catches
    typing, paste, drag-and-drop, IME composition, and autofill alike.
    A keydown blocker is layered on top purely for snappier feedback while
    typing — it is not relied on for correctness.

    Call this immediately after rendering the target text_input, e.g.:
        phone = st.text_input("Phone number* (10 digits)", max_chars=10)
        restrict_to_digits("Phone number* (10 digits)", max_length=10)

    This is a UX enhancement only, not a security boundary — it runs in the
    user's browser and can be bypassed (disabling JS, browser devtools,
    programmatic form submission). is_valid_phone() / is_valid_doctor_age() /
    is_valid_patient_age() in this module remain the authoritative
    server-side checks and must still be called on submit.
    """
    import streamlit.components.v1 as components

    max_len_js = "null" if max_length is None else str(int(max_length))

    js = f"""
    <script>
    (function() {{
        const targetLabel = {field_label!r};
        const maxLen = {max_len_js};

        function sanitize(input) {{
            const oldVal = input.value;
            let newVal = oldVal.replace(/[^0-9]/g, '');
            if (maxLen !== null) newVal = newVal.slice(0, maxLen);
            if (newVal !== oldVal) {{
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(input, newVal);
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }}

        function attach() {{
            const doc = window.parent.document;
            const labels = doc.querySelectorAll('label');
            labels.forEach(function(label) {{
                if (label.textContent.trim() !== targetLabel) return;
                const container = label.closest('div[data-testid="stTextInput"]') || label.parentElement;
                if (!container) return;
                const input = container.querySelector('input');
                if (!input || input.dataset.digitsOnly === "true") return;
                input.dataset.digitsOnly = "true";

                input.addEventListener('input', function() {{ sanitize(input); }});

                input.addEventListener('keydown', function(e) {{
                    const allowed = [
                        'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight',
                        'Tab', 'Home', 'End', 'Enter'
                    ];
                    if (allowed.includes(e.key) || e.ctrlKey || e.metaKey) return;
                    if (e.key.length === 1 && !/^[0-9]$/.test(e.key)) {{
                        e.preventDefault();
                    }}
                }});

                sanitize(input); // clean up anything already present (e.g. autofilled on load)
            }});
        }}

        attach();
        [200, 500, 1000, 2000].forEach(function(t) {{ setTimeout(attach, t); }});
        try {{
            const observer = new MutationObserver(function() {{ attach(); }});
            observer.observe(window.parent.document.body, {{ childList: true, subtree: true }});
        }} catch (e) {{}}
    }})();
    </script>
    """
    components.html(js, height=0, width=0)
