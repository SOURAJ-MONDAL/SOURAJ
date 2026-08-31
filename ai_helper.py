"""
ai_helper.py
All Google Gen AI (Gemini) integration for MediKiosk:
  - chat_reply():           conversational AI doctor-assistant turn
  - assess_severity():      severity + specialization triage after 5+ turns
  - generate_summary():     patient-facing + doctor-facing chat summary
  - generate_prescription() structured AI prescription (OTC / casual only)

Uses the current `google-genai` SDK (`from google import genai`). The
project previously used `google-generativeai` / `genai.GenerativeModel(...)`,
but Google deprecated that package on 31 Aug 2025 in favor of this unified
SDK — the old package doesn't reliably support current-generation models,
which is why every real AI call was silently failing and falling back to
the canned "I'm having trouble connecting" reply. See:
https://ai.google.dev/gemini-api/docs/migrate

Models:
  - gemini-3.7-flash        -> fast conversational turns (chat_reply, generate_summary)
  - gemini-3.1-pro-preview  -> higher-stakes structured reasoning (severity
                               triage, prescriptions). This is currently
                               Google's newest Pro-tier model — there is no
                               non-preview Gemini Pro release yet.

  Gemini 3.x models ignore `temperature`/`top_p`/`top_k` (Google deprecated
  those sampling params for the whole 3.x family), so determinism is
  controlled via `thinking_level` instead: "low" for quick conversational
  turns, "high" for the higher-stakes triage/prescription calls.

  (If Google ships a newer stable model down the line, just update the two
  model constants below.)

All model calls are defensive: on any SDK / parsing failure we return a
safe fallback dict rather than raising, so a flaky API call never crashes
a Streamlit page.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from utils import get_api_key

FLASH_MODEL = "gemini-3.7-flash"
PRO_MODEL = "gemini-3.1-pro-preview"

SEVERE_SPECIALIST_HINT = (
    "Map symptoms to ONE of these specializations when severe: Cardiologist, "
    "Neurologist, Pulmonologist, Gastroenterologist, Orthopedist, General Physician, "
    "ENT Specialist, Dermatologist, Gynecologist, Psychiatrist, Pediatrician."
)

_client = None  # lazily created, reused across calls in this process
_client_key = None  # the API key the current _client was built with (detects key changes)

# The single most common reason "the AI doesn't reply correctly" in practice
# is that a call is failing for a specific, diagnosable reason (missing key,
# bad key, wrong model name, quota) and the app was previously swallowing
# that reason completely, always showing the same generic fallback line no
# matter what actually went wrong. _last_error keeps the most recent
# diagnosis so the sidebar (see get_status()) and the dev running the app can
# actually see what's happening instead of guessing.
_last_error: Optional[str] = None


def _classify_error(exc: Exception) -> str:
    """Turn a raw SDK/network exception into a short, actionable diagnosis
    matching the failure modes called out in the build guide's
    'Common Errors and Fixes' section."""
    text = str(exc)
    lowered = text.lower()
    if "429" in text or "resource_exhausted" in lowered or "quota" in lowered:
        return "Gemini quota exceeded (429) — wait a bit, or switch FLASH_MODEL/PRO_MODEL to a lighter model."
    if "404" in text or "not_found" in lowered or "not found" in lowered:
        return f"Model not found (404) for one of {FLASH_MODEL!r}/{PRO_MODEL!r} — check the exact model name."
    if "api key not valid" in lowered or "api_key_invalid" in lowered or "400" in text:
        return "Gemini API key was rejected — get a fresh key from ai.google.dev and update secrets.toml."
    if "403" in text or "permission_denied" in lowered:
        return "Gemini API key doesn't have permission for this model/request."
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "The 'google-genai' package isn't installed — run: pip install google-genai"
    # Fall back to the raw message, trimmed so it stays readable in the UI.
    return text[:200] if text else exc.__class__.__name__


def _record_error(exc: Exception) -> str:
    global _last_error
    _last_error = _classify_error(exc)
    return _last_error


def get_status() -> dict:
    """Best-effort connection status for the sidebar / debugging.

    Returns: {"connected": bool, "detail": str}
    "connected" only reflects that a key is configured and the SDK package
    imports — it is NOT a guarantee the key is valid (we don't want to burn
    an API call just to render the sidebar). Any real call failure updates
    "detail" via _record_error() so the actual error shows up here on the
    next render.
    """
    if not get_api_key():
        return {"connected": False, "detail": "No Gemini API key found. Add GOOGLE_API_KEY to "
                                                ".streamlit/secrets.toml (or set it in the sidebar)."}
    try:
        import google.genai  # noqa: F401
    except Exception as exc:
        return {"connected": False, "detail": _classify_error(exc)}
    if _last_error:
        return {"connected": False, "detail": _last_error}
    return {"connected": True, "detail": "AI Connected"}


def clear_last_error() -> None:
    """Call after a successful generation so a one-off transient error
    doesn't keep showing as the status forever."""
    global _last_error
    _last_error = None


def _client_ready() -> bool:
    return bool(get_api_key())


def _get_client():
    """Lazy singleton google-genai client so the rest of the app still loads
    even if the package isn't installed yet (until `pip install google-genai`
    has been run). Rebuilds the client if the configured key changes (e.g.
    the user pastes a new one into the sidebar mid-session)."""
    global _client, _client_key
    key = get_api_key()
    if _client is None or _client_key != key:
        from google import genai
        _client = genai.Client(api_key=key)
        _client_key = key
    return _client


def _generate(model: str, prompt: str, *, json_mode: bool = False, thinking_level: str = "low") -> str:
    """Shared call wrapper around client.models.generate_content(). Returns
    the response text, or raises on any SDK failure (callers catch this and
    should route it through _record_error so the failure is diagnosable)."""
    from google.genai import types
    client = _get_client()
    config_kwargs = {"thinking_config": types.ThinkingConfig(thinking_level=thinking_level)}
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    clear_last_error()
    return response.text


def _extract_json(text: str) -> Optional[dict]:
    """Gemini sometimes wraps JSON in ```json fences despite instructions —
    strip those before parsing, and fall back to a regex grab of the first
    {...} block."""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------
# 1. Conversational Doctor Assistant
# --------------------------------------------------------------------------

def opening_message(patient_name: str) -> str:
    return f"Namaste {patient_name}, what brings you here today?"


def chat_reply(patient_name: str, history: list[dict]) -> dict:
    """One turn of the AI triage conversation.

    `history` is a list of {"role": "assistant"|"user", "content": str}.

    Returns: {"reply": str, "suggestions": [str, ...]}
    """
    def _fallback(detail: Optional[str] = None) -> dict:
        msg = "⚠️ I'm unable to reach the AI assistant right now"
        msg += f" ({detail})." if detail else "."
        msg += " Please tell the front desk, or try again in a moment."
        return {"reply": msg, "suggestions": ["Try again"]}

    if not _client_ready():
        return _fallback("no Gemini API key is configured")

    try:
        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        prompt = f"""You are MediKiosk AI, a clinical history-taking assistant on a hospital kiosk,
speaking with a patient named {patient_name}. Your job is triage, not diagnosis: take a complete
medical history by asking questions ONE AT A TIME, in a warm and empathetic manner.

Conversation so far:
{transcript}

RULES:
1. Ask ONE question at a time and wait for the reply. Keep each question to 2 sentences max.
2. If this is the start of the conversation, open with a warm greeting and ask about the chief
   complaint (what's bothering them today).
3. Once you know the chief complaint, follow the SOCRATES framework to understand it fully —
   ask about these one at a time, in whatever order fits the conversation naturally:
   - Site: where exactly is it?
   - Onset: when did it start, and how (sudden or gradual)?
   - Character: what does it feel like?
   - Radiation: does it spread anywhere else?
   - Associated symptoms: anything else alongside it?
   - Timing: constant or does it come and go?
   - Exacerbating/relieving factors: what makes it better or worse?
   - Severity: ask them to rate it 1-10.
4. After the chief complaint is well understood, briefly ask about relevant past medical history,
   current medications, allergies, and family history — pick whichever are most relevant rather
   than mechanically asking all of them.
5. Show empathy — acknowledge what the patient just told you before asking the next question.
6. Do not diagnose or prescribe — you are only gathering history.

RED FLAGS — if the patient mentions any of the following, treat it as urgent: chest pain with
breathlessness, sudden one-sided weakness, the worst headache of their life, difficulty breathing
at rest, coughing or vomiting blood, fainting or loss of consciousness, heavy bleeding, or
suicidal thoughts. If you spot one, acknowledge it with visible concern and gently steer the
conversation toward urgency, but you are still just gathering history — the app's own severity
check (after enough turns) is what actually triggers the emergency routing, so keep replying
normally within the required JSON format below.

Along with your reply, suggest up to 3 short quick-reply options the patient could tap instead of
typing (e.g. a plausible answer to the question you just asked, or "Not sure").

Respond with ONLY a JSON object, no markdown fences:
{{
  "reply": "your next message to the patient",
  "suggestions": ["short reply option 1", "short reply option 2", "short reply option 3"]
}}"""
        text = _generate(FLASH_MODEL, prompt, json_mode=True, thinking_level="low")
        parsed = _extract_json(text)
        if not parsed:
            return _fallback("the AI's response couldn't be parsed")
        return {
            "reply": parsed.get("reply") or _fallback()["reply"],
            "suggestions": parsed.get("suggestions", [])[:3],
        }
    except Exception as exc:
        return _fallback(_record_error(exc))


# --------------------------------------------------------------------------
# 2. Severity assessment
# --------------------------------------------------------------------------

def assess_severity(history: list[dict]) -> dict:
    """Run after 5+ conversational turns to decide severe vs casual, and
    which specialist to route to if severe.

    Returns: {"severity": "severe"|"casual", "specialization": str, "reasoning": str}
    """
    fallback = {"severity": "casual", "specialization": "General Physician", "reasoning": "Assessment unavailable."}
    if not _client_ready():
        return fallback

    try:
        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        prompt = f"""You are a clinical triage classifier. Review this patient conversation and
classify overall severity conservatively — err toward "severe" if there is ANY plausible red-flag
symptom (chest pain, breathing difficulty, severe/sudden headache, fainting, heavy bleeding,
stroke-like symptoms, high fever with confusion, severe abdominal pain, suicidal ideation, etc).

{SEVERE_SPECIALIST_HINT}

Conversation:
{transcript}

Respond with ONLY a JSON object, no markdown fences:
{{
  "severity": "severe" or "casual",
  "specialization": "the single best-fit specialization from the list (severe cases only, else General Physician)",
  "reasoning": "one short sentence"
}}"""
        text = _generate(PRO_MODEL, prompt, json_mode=True, thinking_level="high")
        parsed = _extract_json(text)
        if not parsed:
            return {**fallback, "reasoning": "AI response couldn't be parsed."}
        severity = parsed.get("severity", "casual")
        if severity not in ("severe", "casual"):
            severity = "casual"
        return {
            "severity": severity,
            "specialization": parsed.get("specialization", "General Physician"),
            "reasoning": parsed.get("reasoning", ""),
        }
    except Exception as exc:
        return {**fallback, "reasoning": _record_error(exc)}


# --------------------------------------------------------------------------
# 3. Chat summary
# --------------------------------------------------------------------------

def generate_summary(history: list[dict]) -> str:
    if not _client_ready():
        return "Summary unavailable — AI service not configured."
    try:
        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        prompt = f"""Summarize this patient triage conversation in 3-4 concise clinical sentences for a
doctor's dashboard: presenting complaint, duration, relevant details mentioned, and any red flags.
Plain text only, no markdown, no headers.

Conversation:
{transcript}"""
        text = _generate(FLASH_MODEL, prompt, thinking_level="low")
        return (text or "").strip() or "No summary generated."
    except Exception as exc:
        return f"Summary unavailable ({_record_error(exc)})."


# --------------------------------------------------------------------------
# 4. AI prescription (casual / OTC only)
# --------------------------------------------------------------------------

def generate_prescription(history: list[dict], summary: str) -> dict:
    """Generates a structured, casual/OTC-only recommendation. This is
    explicitly NOT a substitute for a licensed doctor and is labeled as such
    throughout the UI.

    Returns:
      {"medicines": [{"name": str, "dosage": str, "notes": str}, ...],
       "advice": [str, ...], "disclaimer": str}
    """
    fallback = {
        "medicines": [],
        "advice": ["Please consult a doctor for a proper prescription."],
        "disclaimer": "AI prescription generation is unavailable right now.",
    }
    if not _client_ready():
        return fallback

    try:
        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        prompt = f"""You are assisting with a CASUAL, NON-SEVERE patient case only (severity has already
been classified as casual — do not second-guess that). Based on the conversation and summary below,
suggest ONLY common over-the-counter (OTC) remedies and general self-care advice appropriate for mild,
everyday symptoms (e.g. mild cold, minor headache, mild indigestion). NEVER include prescription-only,
controlled, or high-risk medications. Keep dosages generic and conservative (e.g. "as per package
instructions" when unsure).

Summary: {summary}
Conversation:
{transcript}

Respond with ONLY a JSON object, no markdown fences:
{{
  "medicines": [{{"name": "...", "dosage": "...", "notes": "..."}}],
  "advice": ["self-care tip 1", "self-care tip 2"],
  "disclaimer": "a short sentence reminding the patient this is AI-generated general guidance, not a substitute for a licensed doctor"
}}"""
        text = _generate(PRO_MODEL, prompt, json_mode=True, thinking_level="high")
        parsed = _extract_json(text)
        if not parsed:
            return fallback
        return {
            "medicines": parsed.get("medicines", []),
            "advice": parsed.get("advice", []),
            "disclaimer": parsed.get(
                "disclaimer",
                "This is AI-generated general guidance, not a substitute for a licensed doctor.",
            ),
        }
    except Exception as exc:
        fallback["disclaimer"] = f"AI prescription generation failed ({_record_error(exc)})."
        return fallback
