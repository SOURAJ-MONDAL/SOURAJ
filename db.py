"""
db.py
All SQLite persistence for MediKiosk.

Three logical databases are kept as three separate .db files (per the spec),
but a single sqlite3 connection ATTACHes all of them so appointments /
prescriptions can join across doctor, patient and hospital data without
duplicating a query layer per file. Call `get_conn()` everywhere.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional

from utils import hash_password, now_iso, verify_password

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DOCTORS_DB = os.path.join(DATA_DIR, "doctors.db")
PATIENTS_DB = os.path.join(DATA_DIR, "patients.db")
HOSPITALS_DB = os.path.join(DATA_DIR, "hospitals.db")


# --------------------------------------------------------------------------
# Connection handling
# --------------------------------------------------------------------------

@contextmanager
def get_conn():
    """Yield a sqlite3 connection with all three databases attached as
    'main' (doctors), 'patients' and 'hospitals'. Using ATTACH lets us run
    cross-database JOINs (e.g. appointments joined to doctor + hospital)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DOCTORS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS patients", (PATIENTS_DB,))
    conn.execute("ATTACH DATABASE ? AS hospitals", (HOSPITALS_DB,))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Schema init
# --------------------------------------------------------------------------

def init_db():
    """Create all tables if they do not already exist. Safe to call on
    every app startup."""
    with get_conn() as conn:
        # ---- doctors.db (main) --------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                specialization TEXT NOT NULL,
                license_doc BLOB,
                license_doc_name TEXT,
                degree_doc BLOB,
                degree_doc_name TEXT,
                chamber_count INTEGER DEFAULT 1,
                chamber_addresses TEXT DEFAULT '[]',
                hospital_affiliations TEXT DEFAULT '[]',
                schedule TEXT DEFAULT '{}',
                fee REAL DEFAULT 0,
                profile_photo BLOB,
                password_hash TEXT NOT NULL,
                verification_status TEXT DEFAULT 'pending',
                avg_rating REAL DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doctor_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                appointment_id INTEGER,
                stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
                comment TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (doctor_id) REFERENCES doctors(id)
            )
        """)

        # ---- patients.db (attached as `patients`) ---------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients.patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                profile_photo BLOB,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients.chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                messages TEXT DEFAULT '[]',
                summary TEXT,
                severity TEXT,
                specialization_suggested TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients.prescriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER,
                doctor_name TEXT,
                source TEXT NOT NULL DEFAULT 'ai',
                chat_session_id INTEGER,
                content TEXT NOT NULL,
                uploaded_file BLOB,
                uploaded_file_name TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients.appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                doctor_name TEXT NOT NULL,
                specialization TEXT,
                chamber_address TEXT,
                scheduled_date TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                fee REAL DEFAULT 0,
                status TEXT DEFAULT 'upcoming',
                reason TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # ---- hospitals.db (attached as `hospitals`) --------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hospitals.hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                address TEXT,
                city TEXT,
                specialties_offered TEXT DEFAULT '[]'
            )
        """)
        _seed_hospitals(conn)


def _seed_hospitals(conn: sqlite3.Connection):
    count = conn.execute("SELECT COUNT(*) AS c FROM hospitals.hospitals").fetchone()["c"]
    if count:
        return
    seed = [
        ("City Care General Hospital", "12 MG Road", "Kolkata",
         ["Cardiologist", "General Physician", "Orthopedist"]),
        ("Sunrise Multispecialty Hospital", "45 Salt Lake Sector V", "Kolkata",
         ["Dermatologist", "Pediatrician", "ENT Specialist"]),
        ("Lotus Women & Children Hospital", "8 Park Street", "Kolkata",
         ["Gynecologist", "Pediatrician"]),
        ("Metro Neuro & Ortho Institute", "21 Rashbehari Ave", "Kolkata",
         ["Neurologist", "Orthopedist", "Physiotherapist"]),
        ("Green Valley Clinic", "3 Camac Street", "Kolkata",
         ["General Physician", "Dermatologist", "Psychiatrist"]),
    ]
    for name, addr, city, specs in seed:
        conn.execute(
            "INSERT INTO hospitals.hospitals (name, address, city, specialties_offered) VALUES (?,?,?,?)",
            (name, addr, city, json.dumps(specs)),
        )


# --------------------------------------------------------------------------
# Hospitals
# --------------------------------------------------------------------------

def list_hospitals() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM hospitals.hospitals ORDER BY name").fetchall()
        return _rows_to_dicts(rows)


def find_hospital_by_name(name: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hospitals.hospitals WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
        return _row_to_dict(row)


def auto_map_hospital_affiliation(hospital_name: str) -> Optional[dict]:
    """Called on doctor signup: looks up the hospital directory so the
    doctor's affiliation is normalized against a real hospital record."""
    hosp = find_hospital_by_name(hospital_name)
    if hosp:
        return hosp
    # Not found — register it so future lookups match, but leave specialties empty.
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO hospitals.hospitals (name, address, city, specialties_offered) VALUES (?,?,?,?)",
            (hospital_name, "", "", json.dumps([])),
        )
        row = conn.execute(
            "SELECT * FROM hospitals.hospitals WHERE lower(name) = lower(?)", (hospital_name,)
        ).fetchone()
        return _row_to_dict(row)


# --------------------------------------------------------------------------
# Doctors
# --------------------------------------------------------------------------

def create_doctor(**fields) -> int:
    password_hash = hash_password(fields.pop("password"))
    hospital_names = fields.pop("hospital_affiliations", [])
    mapped = [auto_map_hospital_affiliation(h) for h in hospital_names if h and h.strip()]
    affiliations_json = json.dumps([{"id": h["id"], "name": h["name"]} for h in mapped if h])

    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO doctors (
                name, email, phone, age, gender, specialization,
                license_doc, license_doc_name, degree_doc, degree_doc_name,
                chamber_count, chamber_addresses, hospital_affiliations, schedule,
                fee, profile_photo, password_hash, verification_status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            fields.get("name"), fields.get("email"), fields.get("phone"),
            fields.get("age"), fields.get("gender"), fields.get("specialization"),
            fields.get("license_doc"), fields.get("license_doc_name"),
            fields.get("degree_doc"), fields.get("degree_doc_name"),
            fields.get("chamber_count", 1),
            json.dumps(fields.get("chamber_addresses", [])),
            affiliations_json,
            json.dumps(fields.get("schedule", {})),
            fields.get("fee", 0),
            fields.get("profile_photo"),
            password_hash,
            fields.get("verification_status", "pending"),
            now_iso(),
        ))
        return cur.lastrowid


def get_doctor(doctor_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
        return _row_to_dict(row)


def get_doctor_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM doctors WHERE lower(email) = lower(?)", (email,)).fetchone()
        return _row_to_dict(row)


def authenticate_doctor(email: str, password: str) -> Optional[dict]:
    doc = get_doctor_by_email(email)
    if doc and verify_password(password, doc["password_hash"]):
        return doc
    return None


def list_doctors(specialization: Optional[str] = None, verified_only: bool = True) -> list[dict]:
    with get_conn() as conn:
        q = "SELECT * FROM doctors WHERE 1=1"
        params: list[Any] = []
        if verified_only:
            q += " AND verification_status = 'accepted'"
        if specialization and specialization != "All":
            q += " AND specialization = ?"
            params.append(specialization)
        q += " ORDER BY avg_rating DESC, name ASC"
        rows = conn.execute(q, params).fetchall()
        return _rows_to_dicts(rows)


def list_specializations() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT specialization FROM doctors WHERE verification_status='accepted' ORDER BY specialization"
        ).fetchall()
        return [r["specialization"] for r in rows]


def update_doctor_fields(doctor_id: int, **fields) -> None:
    if not fields:
        return
    for json_field in ("chamber_addresses", "hospital_affiliations", "schedule"):
        if json_field in fields and not isinstance(fields[json_field], str):
            fields[json_field] = json.dumps(fields[json_field])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE doctors SET {set_clause} WHERE id = ?", (*fields.values(), doctor_id))


def delete_doctor(doctor_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
        conn.execute("DELETE FROM doctor_ratings WHERE doctor_id = ?", (doctor_id,))


def add_doctor_rating(doctor_id: int, patient_id: int, stars: int, comment: str = "",
                       appointment_id: Optional[int] = None) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO doctor_ratings (doctor_id, patient_id, appointment_id, stars, comment, created_at)
            VALUES (?,?,?,?,?,?)
        """, (doctor_id, patient_id, appointment_id, stars, comment, now_iso()))
        agg = conn.execute(
            "SELECT AVG(stars) AS avg_r, COUNT(*) AS n FROM doctor_ratings WHERE doctor_id = ?",
            (doctor_id,),
        ).fetchone()
        conn.execute(
            "UPDATE doctors SET avg_rating = ?, rating_count = ? WHERE id = ?",
            (round(agg["avg_r"] or 0, 2), agg["n"], doctor_id),
        )


# --------------------------------------------------------------------------
# Patients
# --------------------------------------------------------------------------

def create_patient(**fields) -> int:
    password_hash = hash_password(fields.pop("password"))
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO patients.patients (name, email, phone, age, gender, profile_photo, password_hash, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            fields.get("name"), fields.get("email"), fields.get("phone"),
            fields.get("age"), fields.get("gender"), fields.get("profile_photo"),
            password_hash, now_iso(),
        ))
        return cur.lastrowid


def get_patient(patient_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM patients.patients WHERE id = ?", (patient_id,)).fetchone()
        return _row_to_dict(row)


def get_patient_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients.patients WHERE lower(email) = lower(?)", (email,)
        ).fetchone()
        return _row_to_dict(row)


def authenticate_patient(email: str, password: str) -> Optional[dict]:
    pat = get_patient_by_email(email)
    if pat and verify_password(password, pat["password_hash"]):
        return pat
    return None


def update_patient_fields(patient_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE patients.patients SET {set_clause} WHERE id = ?", (*fields.values(), patient_id))


def delete_patient(patient_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM patients.patients WHERE id = ?", (patient_id,))


# --------------------------------------------------------------------------
# Chat sessions
# --------------------------------------------------------------------------

def create_chat_session(patient_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO patients.chat_sessions (patient_id, messages, created_at, updated_at)
            VALUES (?, '[]', ?, ?)
        """, (patient_id, now_iso(), now_iso()))
        return cur.lastrowid


def get_chat_session(session_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM patients.chat_sessions WHERE id = ?", (session_id,)).fetchone()
        d = _row_to_dict(row)
        if d:
            d["messages"] = json.loads(d["messages"] or "[]")
        return d


def save_chat_messages(session_id: int, messages: list[dict]) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE patients.chat_sessions SET messages = ?, updated_at = ? WHERE id = ?",
            (json.dumps(messages), now_iso(), session_id),
        )


def finalize_chat_session(session_id: int, summary: str, severity: str, specialization: str = "") -> None:
    with get_conn() as conn:
        conn.execute("""
            UPDATE patients.chat_sessions
            SET summary = ?, severity = ?, specialization_suggested = ?, status = 'closed', updated_at = ?
            WHERE id = ?
        """, (summary, severity, specialization, now_iso(), session_id))


def list_chat_sessions(patient_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patients.chat_sessions WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()
        out = _rows_to_dicts(rows)
        for d in out:
            d["messages"] = json.loads(d["messages"] or "[]")
        return out


# --------------------------------------------------------------------------
# Prescriptions
# --------------------------------------------------------------------------

def create_prescription(patient_id: int, content: dict, source: str = "ai",
                         doctor_id: Optional[int] = None, doctor_name: Optional[str] = None,
                         chat_session_id: Optional[int] = None,
                         uploaded_file: Optional[bytes] = None,
                         uploaded_file_name: Optional[str] = None) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO patients.prescriptions
                (patient_id, doctor_id, doctor_name, source, chat_session_id, content,
                 uploaded_file, uploaded_file_name, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            patient_id, doctor_id, doctor_name, source, chat_session_id,
            json.dumps(content), uploaded_file, uploaded_file_name, now_iso(),
        ))
        return cur.lastrowid


def list_prescriptions(patient_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patients.prescriptions WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()
        out = _rows_to_dicts(rows)
        for d in out:
            d["content"] = json.loads(d["content"] or "{}")
        return out


def update_prescription_content(prescription_id: int, content: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE patients.prescriptions SET content = ? WHERE id = ?",
            (json.dumps(content), prescription_id),
        )


def list_prescriptions_for_doctor(doctor_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.*, pt.name AS patient_name
            FROM patients.prescriptions p
            JOIN patients.patients pt ON pt.id = p.patient_id
            WHERE p.doctor_id = ?
            ORDER BY p.created_at DESC
        """, (doctor_id,)).fetchall()
        out = _rows_to_dicts(rows)
        for d in out:
            d["content"] = json.loads(d["content"] or "{}")
        return out


# --------------------------------------------------------------------------
# Appointments
# --------------------------------------------------------------------------

def create_appointment(patient_id: int, doctor_id: int, doctor_name: str, specialization: str,
                        chamber_address: str, scheduled_date: str, scheduled_time: str,
                        fee: float = 0, reason: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO patients.appointments
                (patient_id, doctor_id, doctor_name, specialization, chamber_address,
                 scheduled_date, scheduled_time, fee, status, reason, created_at)
            VALUES (?,?,?,?,?,?,?,?, 'upcoming', ?, ?)
        """, (patient_id, doctor_id, doctor_name, specialization, chamber_address,
              scheduled_date, scheduled_time, fee, reason, now_iso()))
        return cur.lastrowid


def list_appointments_for_patient(patient_id: int, status: Optional[str] = None) -> list[dict]:
    with get_conn() as conn:
        q = "SELECT * FROM patients.appointments WHERE patient_id = ?"
        params: list[Any] = [patient_id]
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY scheduled_date DESC, scheduled_time DESC"
        rows = conn.execute(q, params).fetchall()
        return _rows_to_dicts(rows)


def list_appointments_for_doctor(doctor_id: int, status: Optional[str] = None) -> list[dict]:
    with get_conn() as conn:
        q = """
            SELECT a.*, pt.name AS patient_name, pt.age AS patient_age, pt.gender AS patient_gender
            FROM patients.appointments a
            JOIN patients.patients pt ON pt.id = a.patient_id
            WHERE a.doctor_id = ?
        """
        params: list[Any] = [doctor_id]
        if status:
            q += " AND a.status = ?"
            params.append(status)
        q += " ORDER BY a.scheduled_date DESC, a.scheduled_time DESC"
        rows = conn.execute(q, params).fetchall()
        return _rows_to_dicts(rows)


def update_appointment_status(appointment_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE patients.appointments SET status = ? WHERE id = ?", (status, appointment_id))
