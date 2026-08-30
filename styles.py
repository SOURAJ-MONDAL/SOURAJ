"""
styles.py
MediKiosk design system.

Token summary
-------------
Color:
  --mk-primary:      #0F5C5C   deep clinical teal   (headers, primary actions)
  --mk-primary-dark: #0A4444   pressed / hover state
  --mk-mint:         #E8F5F1   soft mint tint        (page background wash)
  --mk-paper:        #FBFAF7   warm off-white         (card surfaces)
  --mk-ink:          #1C2B2B   charcoal ink            (body text)
  --mk-ink-soft:     #5B6F6F   muted secondary text
  --mk-amber:        #E8A33D   caution / pending badges
  --mk-coral:        #D64545   emergency / destructive actions
  --mk-line:         #DCE8E4   hairline borders

Type:
  Display  — "Fraunces"     (institutional, slightly editorial — headings)
  Body     — "Inter"        (clean clinical readability)
  Data     — "JetBrains Mono" (IDs, badges, vitals-style numerics)

Signature element: the "vitals strip" — a thin heartbeat-pulse divider used
under page headers and as a loading motif, tying every screen back to the
idea of a kiosk reading your vitals before connecting you to care.
"""

import streamlit as st

FONT_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&"
    "family=Inter:wght@400;500;600;700&"
    "family=JetBrains+Mono:wght@400;500;600&display=swap"
)

BASE_CSS = f"""
<style>
@import url('{FONT_IMPORT_URL}');

:root {{
    --mk-primary: #0F5C5C;
    --mk-primary-dark: #0A4444;
    --mk-primary-light: #17807F;
    --mk-mint: #E8F5F1;
    --mk-paper: #FBFAF7;
    --mk-ink: #1C2B2B;
    --mk-ink-soft: #5B6F6F;
    --mk-amber: #E8A33D;
    --mk-amber-bg: #FBF1DF;
    --mk-coral: #D64545;
    --mk-coral-bg: #FBE9E9;
    --mk-line: #DCE8E4;
}}

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, sans-serif;
    color: var(--mk-ink);
}}

.stApp {{
    background: var(--mk-mint);
}}

h1, h2, h3, .mk-display {{
    font-family: 'Fraunces', Georgia, serif;
    color: var(--mk-ink);
    letter-spacing: -0.01em;
}}

/* ---------- Vitals strip (signature element) ---------- */
.mk-vitals-strip {{
    width: 100%;
    height: 3px;
    margin: 0.15rem 0 1.1rem 0;
    background: linear-gradient(90deg,
        var(--mk-line) 0%, var(--mk-line) 38%,
        var(--mk-primary) 42%, var(--mk-primary) 44%,
        var(--mk-mint) 46%,
        var(--mk-primary) 50%, var(--mk-primary) 53%,
        var(--mk-line) 57%, var(--mk-line) 100%);
    border-radius: 2px;
    opacity: 0.9;
}}

/* ---------- Header block ---------- */
.mk-kicker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--mk-primary);
    font-weight: 600;
}}

.mk-page-title {{
    font-family: 'Fraunces', Georgia, serif;
    font-size: 2.1rem;
    font-weight: 600;
    margin: 0.1rem 0 0.2rem 0;
    color: var(--mk-ink);
}}

.mk-subtitle {{
    color: var(--mk-ink-soft);
    font-size: 1rem;
    margin-bottom: 0.6rem;
}}

/* ---------- Cards ---------- */
.mk-card {{
    background: var(--mk-paper);
    border: 1px solid var(--mk-line);
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 2px rgba(15, 92, 92, 0.04);
    transition: box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
}}

.mk-card:hover {{
    box-shadow: 0 6px 18px rgba(15, 92, 92, 0.10);
    border-color: var(--mk-primary-light);
    transform: translateY(-1px);
}}

.mk-card-flat {{
    background: var(--mk-paper);
    border: 1px solid var(--mk-line);
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
}}

/* ---------- Badges ---------- */
.mk-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
    border-left: 3px solid currentColor;
    text-transform: uppercase;
}}
.mk-badge-primary {{ background: var(--mk-mint); color: var(--mk-primary); }}
.mk-badge-amber   {{ background: var(--mk-amber-bg); color: #92660E; }}
.mk-badge-coral   {{ background: var(--mk-coral-bg); color: var(--mk-coral); }}
.mk-badge-neutral {{ background: #EFEFEA; color: var(--mk-ink-soft); }}

/* ---------- Alert banners ---------- */
.mk-alert-emergency {{
    background: var(--mk-coral-bg);
    border: 1px solid var(--mk-coral);
    border-left: 6px solid var(--mk-coral);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    color: #7A1F1F;
    font-weight: 500;
    margin: 0.6rem 0 1rem 0;
    animation: mk-pulse 1.8s ease-in-out infinite;
}}
@keyframes mk-pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(214, 69, 69, 0.25); }}
    50% {{ box-shadow: 0 0 0 8px rgba(214, 69, 69, 0); }}
}}

.mk-disclaimer {{
    background: #FFFDF6;
    border: 1px dashed var(--mk-amber);
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    font-size: 0.86rem;
    color: #6B4F14;
}}

/* ---------- Buttons ---------- */
.stButton > button {{
    border-radius: 10px !important;
    font-weight: 600 !important;
    border: 1px solid var(--mk-primary) !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(15, 92, 92, 0.18);
}}
div[data-testid="stFormSubmitButton"] button,
.stButton > button[kind="primary"] {{
    background: var(--mk-primary) !important;
    color: white !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: var(--mk-primary-dark) !important;
}}

/* ---------- Form field labels (Email, Password, etc.) ---------- */
/* Safety net alongside .streamlit/config.toml: forces widget labels to
   ink color even if a visitor's browser dark-mode setting still leaks
   through to native Streamlit widget styling. */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {{
    color: var(--mk-ink) !important;
}}

/* ---------- Password fields: suppress browser's native reveal icon ---------- */
/* Chromium/Edge inject their own eye/reveal button inside <input type=password>,
   which stacks on top of Streamlit's own custom eye toggle button, showing two
   icons. These pseudo-elements hide the browser-native one so only Streamlit's
   remains. */
input[type="password"]::-ms-reveal,
input[type="password"]::-ms-clear {{
    display: none !important;
}}
input[type="password"]::-webkit-credentials-auto-fill-button,
input[type="password"]::-webkit-strong-password-auto-fill-button,
input[type="password"]::-webkit-caps-lock-indicator {{
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    position: absolute !important;
    right: 0 !important;
}}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {{
    background: var(--mk-paper);
    border-right: 1px solid var(--mk-line);
}}

/* ---------- Sidebar navigation links (st.navigation / st.Page) ---------- */
/* Streamlit's default nav text is white, meant for a dark sidebar. Ours is
   light (--mk-paper), so unselected links were invisible — force ink color. */
section[data-testid="stSidebarNav"] a,
section[data-testid="stSidebarNav"] a span,
section[data-testid="stSidebarNav"] a p,
[data-testid="stSidebarNavLink"],
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] p {{
    color: var(--mk-ink) !important;
    font-weight: 500 !important;
}}

section[data-testid="stSidebarNav"] a:hover,
section[data-testid="stSidebarNav"] a:hover span,
[data-testid="stSidebarNavLink"]:hover,
[data-testid="stSidebarNavLink"]:hover span {{
    color: var(--mk-primary) !important;
}}

/* Selected / active page */
section[data-testid="stSidebarNav"] a[aria-current="page"],
section[data-testid="stSidebarNav"] a[aria-current="page"] span,
[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNavLink"][aria-current="page"] span {{
    color: var(--mk-primary-dark) !important;
    font-weight: 700 !important;
}}
section[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: var(--mk-mint) !important;
    border-radius: 10px !important;
}}

/* ---------- Chat bubbles ---------- */
.mk-chat-doc {{
    background: var(--mk-paper);
    border: 1px solid var(--mk-line);
    border-radius: 14px 14px 14px 3px;
    padding: 0.75rem 1rem;
    max-width: 85%;
    margin: 0.3rem 0;
}}
.mk-chat-patient {{
    background: var(--mk-primary);
    color: white;
    border-radius: 14px 14px 3px 14px;
    padding: 0.75rem 1rem;
    max-width: 85%;
    margin: 0.3rem 0 0.3rem auto;
}}

/* ---------- Misc ---------- */
.mk-divider {{
    border: none;
    border-top: 1px solid var(--mk-line);
    margin: 1rem 0;
}}
.mk-muted {{ color: var(--mk-ink-soft); font-size: 0.88rem; }}
.mk-avatar-initials {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: var(--mk-primary);
    color: white;
    font-family: 'Fraunces', serif;
    font-weight: 600;
}}
</style>
"""


def inject_base_css():
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def vitals_strip():
    st.markdown('<div class="mk-vitals-strip"></div>', unsafe_allow_html=True)


def page_header(kicker: str, title: str, subtitle: str = ""):
    st.markdown(f'<div class="mk-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mk-page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="mk-subtitle">{subtitle}</div>', unsafe_allow_html=True)
    vitals_strip()


def badge(text: str, kind: str = "primary") -> str:
    return f'<span class="mk-badge mk-badge-{kind}">{text}</span>'
