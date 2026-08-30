"""
bot_companion.py
MediKiosk's animated AI companion — a small floating robot figurine that
keeps the patient company during the AI chat and visually reacts to what's
happening in the conversation (listening, thinking, replying, or reacting
to the final triage outcome).

Pure CSS/SVG, no extra dependencies — rendered via st.markdown into a
placeholder so its state can be updated as the conversation progresses.
Just the figure itself reacts — no speech bubble/text.
"""

STATE_GLOW = {
    "idle": "#0F5C5C",
    "listening": "#17807F",
    "thinking": "#E8A33D",
    "talking": "#0F5C5C",
    "happy": "#3FAE7A",
    "concerned": "#D64545",
    "surprised": "#5B8DEF",
    "sleepy": "#8AA6A0",
    "wink": "#17807F",
    "curious": "#0F5C5C",
}


def _mouth_path(state: str) -> str:
    return {
        "happy": "M40,88 Q60,108 80,88",
        "concerned": "M42,96 Q60,82 78,96",
        "thinking": "M52,90 a8,8 0 1,0 16,0 a8,8 0 1,0 -16,0",
        "talking": "M44,88 Q60,100 76,88",
        "listening": "M46,90 L74,90",
        "surprised": "M60,90 a11,11 0 1,0 0.01,0",
        "sleepy": "M48,90 Q60,94 72,90",
        "wink": "M42,88 Q62,104 82,86",
        "curious": "M46,92 Q64,100 78,86",
    }.get(state, "M46,90 Q60,98 74,90")  # idle — gentle smile


def _eyes(state: str) -> str:
    """Returns the SVG markup for both eyes, varying shape/animation by state."""
    if state == "sleepy":
        return (
            '<path d="M37,64 q7,-6 14,0" stroke="#8AA6A0" stroke-width="3.4" '
            'fill="none" stroke-linecap="round" />'
            '<path d="M69,64 q7,-6 14,0" stroke="#8AA6A0" stroke-width="3.4" '
            'fill="none" stroke-linecap="round" />'
        )
    if state == "wink":
        return (
            '<path d="M37,64 q7,6 14,0" stroke="#17807F" stroke-width="3.4" '
            'fill="none" stroke-linecap="round" />'
            '<circle class="mk-bot-eye" cx="76" cy="64" r="6.5" fill="#17807F" />'
        )
    if state == "surprised":
        return (
            '<circle class="mk-bot-eye" cx="44" cy="63" r="8" fill="#5B8DEF" />'
            '<circle class="mk-bot-eye" cx="76" cy="63" r="8" fill="#5B8DEF" />'
        )
    glow = STATE_GLOW.get(state, "#0F5C5C")
    return (
        f'<circle class="mk-bot-eye" cx="44" cy="64" r="6.5" fill="{glow}" />'
        f'<circle class="mk-bot-eye" cx="76" cy="64" r="6.5" fill="{glow}" />'
    )


def _extra_features(state: str) -> str:
    if state == "concerned":
        return (
            '<line x1="36" y1="56" x2="50" y2="62" class="mk-bot-brow" />'
            '<line x1="84" y1="56" x2="70" y2="62" class="mk-bot-brow" />'
        )
    if state == "happy":
        return (
            '<circle cx="32" cy="80" r="5" class="mk-bot-cheek" />'
            '<circle cx="88" cy="80" r="5" class="mk-bot-cheek" />'
        )
    if state == "thinking":
        return (
            '<circle class="mk-bot-dot mk-bot-dot-1" cx="96" cy="28" r="3.5" fill="#E8A33D" />'
            '<circle class="mk-bot-dot mk-bot-dot-2" cx="106" cy="18" r="3.5" fill="#E8A33D" />'
            '<circle class="mk-bot-dot mk-bot-dot-3" cx="116" cy="8" r="3.5" fill="#E8A33D" />'
        )
    if state == "surprised":
        return (
            '<line x1="34" y1="50" x2="46" y2="54" class="mk-bot-brow-up" />'
            '<line x1="86" y1="50" x2="74" y2="54" class="mk-bot-brow-up" />'
        )
    if state == "sleepy":
        return (
            '<text class="mk-bot-zzz mk-bot-zzz-1" x="90" y="34" font-size="14">z</text>'
            '<text class="mk-bot-zzz mk-bot-zzz-2" x="100" y="24" font-size="11">z</text>'
            '<text class="mk-bot-zzz mk-bot-zzz-3" x="108" y="16" font-size="8">z</text>'
        )
    if state == "wink":
        return '<path d="M18,50 l4,-4 M14,54 l6,0" class="mk-bot-sparkle" />'
    if state == "curious":
        return '<line x1="70" y1="52" x2="86" y2="48" class="mk-bot-brow-up" />'
    return ""


def companion_html(state: str = "idle") -> str:
    state = state if state in STATE_GLOW else "idle"
    glow = STATE_GLOW[state]
    mouth_d = _mouth_path(state)
    extras = _extra_features(state)
    eyes = _eyes(state)
    body_anim = {
        "thinking": "mk-bot-bob-fast",
        "concerned": "mk-bot-shake",
        "happy": "mk-bot-bounce",
        "sleepy": "mk-bot-bob-slow",
        "curious": "mk-bot-curious-tilt",
        "surprised": "mk-bot-pop",
    }.get(state, "mk-bot-bob")
    mouth_extra_anim = "animation: mk-bot-talk 0.5s ease-in-out infinite;" if state == "talking" else ""
    no_blink = state in ("sleepy", "surprised")
    blink_css = "animation: none;" if no_blink else ""

    return f"""
<style>
@keyframes mk-bot-bob {{
    0%, 100% {{ transform: translateY(0px); }}
    50% {{ transform: translateY(-7px); }}
}}
@keyframes mk-bot-bob-slow {{
    0%, 100% {{ transform: translateY(0px); }}
    50% {{ transform: translateY(-3px); }}
}}
@keyframes mk-bot-bob-fast {{
    0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
    50% {{ transform: translateY(-4px) rotate(2deg); }}
}}
@keyframes mk-bot-bounce {{
    0%, 100% {{ transform: translateY(0px) scale(1); }}
    30% {{ transform: translateY(-14px) scale(1.05); }}
    50% {{ transform: translateY(0px) scale(0.98); }}
    70% {{ transform: translateY(-6px) scale(1.02); }}
}}
@keyframes mk-bot-shake {{
    0%, 100% {{ transform: translateX(0px); }}
    25% {{ transform: translateX(-3px); }}
    75% {{ transform: translateX(3px); }}
}}
@keyframes mk-bot-pop {{
    0%, 100% {{ transform: scale(1); }}
    30% {{ transform: scale(1.12); }}
    50% {{ transform: scale(0.97); }}
}}
@keyframes mk-bot-curious-tilt {{
    0%, 100% {{ transform: rotate(-5deg) translateY(0px); }}
    50% {{ transform: rotate(5deg) translateY(-4px); }}
}}
@keyframes mk-bot-blink {{
    0%, 92%, 100% {{ transform: scaleY(1); }}
    96% {{ transform: scaleY(0.1); }}
}}
@keyframes mk-bot-glow {{
    0%, 100% {{ opacity: 0.55; }}
    50% {{ opacity: 1; }}
}}
@keyframes mk-bot-talk {{
    0%, 100% {{ transform: scaleY(1); }}
    50% {{ transform: scaleY(1.6); }}
}}
@keyframes mk-bot-dot-pulse {{
    0%, 100% {{ opacity: 0.15; transform: translateY(0px); }}
    50% {{ opacity: 1; transform: translateY(-3px); }}
}}
@keyframes mk-bot-zzz-float {{
    0% {{ opacity: 0; transform: translateY(0px); }}
    30% {{ opacity: 0.9; }}
    100% {{ opacity: 0; transform: translateY(-14px); }}
}}
@keyframes mk-bot-sparkle-fade {{
    0%, 100% {{ opacity: 0.3; }}
    50% {{ opacity: 1; }}
}}

.mk-bot-wrap {{
    position: fixed;
    right: 22px;
    bottom: 108px;
    z-index: 999999;
    pointer-events: none;
    font-family: 'Inter', sans-serif;
}}
.mk-bot-figure {{
    width: 78px;
    height: 90px;
    animation: {body_anim} 2.6s ease-in-out infinite;
    filter: drop-shadow(0 4px 8px rgba(15, 92, 92, 0.18));
}}
.mk-bot-eye {{
    transform-box: fill-box;
    transform-origin: center;
    animation: mk-bot-blink 4.5s ease-in-out infinite;
    {blink_css}
}}
.mk-bot-antenna-tip {{
    animation: mk-bot-glow 1.6s ease-in-out infinite;
}}
.mk-bot-mouth {{
    {mouth_extra_anim}
    transform-box: fill-box;
    transform-origin: center;
}}
.mk-bot-brow {{ stroke: var(--mk-coral, #D64545); stroke-width: 3; stroke-linecap: round; }}
.mk-bot-brow-up {{ stroke: {glow}; stroke-width: 3; stroke-linecap: round; }}
.mk-bot-cheek {{ fill: #F6B8C4; opacity: 0.75; }}
.mk-bot-dot {{ animation: mk-bot-dot-pulse 1.2s ease-in-out infinite; }}
.mk-bot-dot-2 {{ animation-delay: 0.2s; }}
.mk-bot-dot-3 {{ animation-delay: 0.4s; }}
.mk-bot-zzz {{ fill: #8AA6A0; font-family: 'Inter', sans-serif; font-weight: 700;
    animation: mk-bot-zzz-float 2.4s ease-in infinite; }}
.mk-bot-zzz-2 {{ animation-delay: 0.5s; }}
.mk-bot-zzz-3 {{ animation-delay: 1s; }}
.mk-bot-sparkle {{ stroke: #E8A33D; stroke-width: 2.4; stroke-linecap: round;
    animation: mk-bot-sparkle-fade 1.4s ease-in-out infinite; }}
</style>

<div class="mk-bot-wrap">
  <svg class="mk-bot-figure" viewBox="0 0 120 140" xmlns="http://www.w3.org/2000/svg">
    <line x1="60" y1="8" x2="60" y2="24" stroke="{glow}" stroke-width="3" />
    <circle class="mk-bot-antenna-tip" cx="60" cy="8" r="7" fill="{glow}" />
    <rect x="14" y="24" width="92" height="86" rx="26" fill="#FBFAF7" stroke="{glow}" stroke-width="3" />
    {eyes}
    <path class="mk-bot-mouth" d="{mouth_d}" stroke="{glow}" stroke-width="4" fill="none" stroke-linecap="round" />
    {extras}
    <rect x="10" y="112" width="100" height="8" rx="4" fill="{glow}" opacity="0.18" />
  </svg>
</div>
"""


def render_companion(placeholder, state: str = "idle") -> None:
    """Render (or update in place) the floating AI companion figurine.

    Args:
        placeholder: an st.empty() slot created once for the session, so
            repeated calls update the same widget instead of stacking copies.
        state: one of "idle", "listening", "thinking", "talking", "happy",
            "concerned", "surprised", "sleepy", "wink", "curious".
    """
    placeholder.markdown(companion_html(state), unsafe_allow_html=True)
