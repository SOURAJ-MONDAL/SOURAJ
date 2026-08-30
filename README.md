# MediKiosk

A walk-up telehealth kiosk built with Streamlit, Google Gemini (`gemini-2.5-flash` /
`gemini-2.5-pro`), SQLite, and Pillow.

## Features

- **Home** — disclaimer, entry points for doctors and patients.
- **Doctor sign up** — uploads license + degree, AI document inspector auto-verifies or
  flags for manual review, auto-maps hospital affiliation against the hospital directory.
- **Patient sign up** — profile with validated phone/age/password.
- **AI Chat (patient)** — empathetic conversational triage, one question at a time, dynamic
  quick-reply buttons, severity assessment after 5+ patient turns:
  - **Severe** → red emergency banner + one-click routing to the Doctor Directory filtered
    by the recommended specialization.
  - **Casual** → chat summary + optional AI-generated OTC/self-care guidance, saved to the
    patient's record.
- **Doctor Directory** — filter by specialization, see fees/ratings/schedule, book instantly.
- **Doctor Dashboard** — upcoming/past appointment tabs, patient AI-summary viewer,
  prescription writer, editable fee, average rating, delete-profile.
- **Patient Dashboard** — AI chat, medical records, document uploads, upcoming appointments,
  ratings, and a shortcut into the directory for manual booking.

## Setup

```bash
cd medikiosk
python -m venv .venv && source .venv/bin/activate      # optional but recommended
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and paste your Gemini API key
```

You can also set the key as an environment variable instead of using secrets.toml:

```bash
export GOOGLE_API_KEY="your-gemini-api-key-here"
```

## Run

```bash
streamlit run app.py
```

SQLite databases (`doctors.db`, `patients.db`, `hospitals.db`) are created automatically
under `data/` on first run, with a small seed set of hospitals.

## Project layout

```
medikiosk/
├── app.py                     # router / st.navigation entry point
├── db.py                      # SQLite layer (3 attached databases)
├── ai_helper.py                # Gemini integration
├── styles.py                  # design system + injected CSS
├── utils.py                   # validation, hashing, formatting helpers
├── requirements.txt
├── .streamlit/secrets.toml.example
├── data/                      # auto-created SQLite files (gitignored)
└── pages/
    ├── home.py
    ├── doctor_auth.py
    ├── doctor_dashboard.py
    ├── patient_auth.py
    ├── patient_dashboard.py
    └── doctor_directory.py
```

## Notes & limitations

- Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only, no external crypto dependency).
- The AI prescription feature only ever suggests common OTC remedies for cases already
  classified as **casual** — it is explicitly not a substitute for a licensed doctor, and the
  UI states this every time it is shown.
- If `GOOGLE_API_KEY` is not configured, every AI feature degrades gracefully to a safe
  fallback message instead of crashing the app.
- This is a demo/portfolio-grade app: for real clinical use you'd want proper session auth
  (not just `st.session_state`), encrypted document storage, audit logging, and a licensed
  human review step before any doctor profile goes live regardless of AI verification.
