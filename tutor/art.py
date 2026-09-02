"""Hand-drawn SVG artwork: characters, a guide mascot, icons and scenery.

Everything is generated as SVG ``<symbol>`` elements and emitted once per page
as a hidden sprite, so any template — and the quest player's JavaScript — can
draw a piece of art with ``<svg><use href="#char-fox"/></svg>``.

Why build it this way rather than use emoji:

* Emoji look like placeholders, render differently on every device, and cannot
  be recoloured, posed or animated.
* The characters here are all built from one shared construction (same head
  geometry, same eye treatment, same cheek blush), with only colour and ear
  shape changing. That is what makes a set of characters feel like a designed
  family rather than a pile of clip art.
* It is all vector, so it is crisp on any screen, costs a few kilobytes, and
  needs no image files or network access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

# ---------------------------------------------------------------------------
# Shared palette
# ---------------------------------------------------------------------------

INK = "#3b2c4f"          # outlines: a warm dark purple reads friendlier than black
WHITE = "#ffffff"
BLUSH = "#ff9db0"


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Character:
    """One character. Drawing order matters, hence three separate art slots.

    crest    behind everything, above the head (spikes, horns, a water spout)
    under    on the head but beneath the muzzle (fur patches, eye rings)
    overlay  on top of everything (beaks, stripes, whiskers)
    eyes     set False when the character supplies its own, like the frog
    """

    id: str
    name: str
    fur: str
    fur_dark: str
    muzzle: str
    ears: str = "round"       # round | pointy | tall | tiny | flop | none
    nose: str = "#3b2c4f"
    under: str = ""
    overlay: str = ""
    crest: str = ""
    eyes: bool = True
    muzzle_shape: str = "wide"  # wide | narrow | none
    mouth: str = "smile"        # smile | beak | none


CHARACTERS: list[Character] = [
    Character(
        "fox", "Fizz the Fox", "#ff8a4c", "#e56a2c", "#ffe9d6", "pointy", "#5b3a2e",
        overlay="""<path d="M38 92 q-13 -2 -18 -6" stroke="#5b3a2e" stroke-width="2.2"
                         fill="none" stroke-linecap="round" opacity=".7"/>
                   <path d="M82 92 q13 -2 18 -6" stroke="#5b3a2e" stroke-width="2.2"
                         fill="none" stroke-linecap="round" opacity=".7"/>""",
    ),
    Character(
        "panda", "Pod the Panda", "#f9f7fb", "#ded7e6", "#ffffff", "round", "#3b2c4f",
        under="""<ellipse cx="43" cy="61" rx="13" ry="14.5" fill="#3b2c4f"
                       transform="rotate(-12 43 61)"/>
                 <ellipse cx="77" cy="61" rx="13" ry="14.5" fill="#3b2c4f"
                       transform="rotate(12 77 61)"/>""",
    ),
    Character(
        "cat", "Mitts the Cat", "#b39ddb", "#9a80c9", "#f3ecff", "pointy", "#6b4f8a",
        overlay="""<path d="M34 84 h-16 M35 90 h-15" stroke="#6b4f8a" stroke-width="2.4"
                         fill="none" stroke-linecap="round" opacity=".75"/>
                   <path d="M86 84 h16 M85 90 h15" stroke="#6b4f8a" stroke-width="2.4"
                         fill="none" stroke-linecap="round" opacity=".75"/>""",
    ),
    Character("bear", "Bramble the Bear", "#c98b5e", "#a96f45", "#f6e0cc", "round", "#5b3a2e"),
    Character(
        "frog", "Hop the Frog", "#7ed957", "#5cb63c", "#e8ffd9", "none", "#3f6b2a",
        eyes=False,
        muzzle_shape="none",
        crest="""<circle cx="38" cy="32" r="15" fill="#7ed957" stroke="#3b2c4f" stroke-width="3.5"/>
                 <circle cx="82" cy="32" r="15" fill="#7ed957" stroke="#3b2c4f" stroke-width="3.5"/>
                 <circle cx="38" cy="31" r="6.5" fill="#3b2c4f"/>
                 <circle cx="82" cy="31" r="6.5" fill="#3b2c4f"/>
                 <circle cx="40.4" cy="28" r="2.4" fill="#ffffff"/>
                 <circle cx="84.4" cy="28" r="2.4" fill="#ffffff"/>""",
        overlay="""<path d="M40 76 q20 16 40 0" fill="none" stroke="#3b2c4f" stroke-width="3.4"
                         stroke-linecap="round"/>
                   <ellipse cx="52" cy="66" rx="3" ry="2.4" fill="#3f6b2a" opacity=".5"/>
                   <ellipse cx="68" cy="66" rx="3" ry="2.4" fill="#3f6b2a" opacity=".5"/>""",
    ),
    Character(
        "owl", "Hoot the Owl", "#8ecae6", "#5fa8cc", "#fff3d6", "tiny", "#f4a259",
        muzzle_shape="none",
        mouth="none",
        under="""<circle cx="45" cy="62" r="17" fill="#fff3d6"/>
                 <circle cx="75" cy="62" r="17" fill="#fff3d6"/>""",
        overlay="""<path d="M60 70 l-7 9 h14 z" fill="#f4a259" stroke="#3b2c4f"
                         stroke-width="2.6" stroke-linejoin="round"/>
                   <path d="M34 94 q10 8 12 -2 M86 94 q-10 8 -12 -2" fill="#5fa8cc"
                         stroke="#3b2c4f" stroke-width="2.6" stroke-linejoin="round"/>""",
    ),
    Character(
        "penguin", "Puff the Penguin", "#4f5d75", "#3a465a", "#ffffff", "none", "#f4a259",
        mouth="none",
        under="""<ellipse cx="60" cy="74" rx="30" ry="32" fill="#ffffff"/>""",
        overlay="""<path d="M60 68 l-8 8 8 7 8 -7 z" fill="#f4a259" stroke="#3b2c4f"
                         stroke-width="2.6" stroke-linejoin="round"/>""",
    ),
    Character("bunny", "Nibble the Bunny", "#ffd6e0", "#f0b3c4", "#ffffff", "tall", "#c77b93"),
    Character(
        "dragon", "Ember the Dragon", "#69d2b0", "#45b592", "#eafff8", "none", "#2f7f68",
        crest="""<path d="M60 8 q9 10 4 22 q-9 -2 -14 -8 q4 -8 10 -14z" fill="#f4a259"
                       stroke="#3b2c4f" stroke-width="3" stroke-linejoin="round"/>
                 <path d="M28 40 q-6 -16 4 -22 q6 8 6 20z" fill="#f4a259" stroke="#3b2c4f"
                       stroke-width="3" stroke-linejoin="round"/>
                 <path d="M92 40 q6 -16 -4 -22 q-6 8 -6 20z" fill="#f4a259" stroke="#3b2c4f"
                       stroke-width="3" stroke-linejoin="round"/>""",
        overlay="""<ellipse cx="52" cy="78" rx="2.6" ry="2" fill="#2f7f68"/>
                   <ellipse cx="68" cy="78" rx="2.6" ry="2" fill="#2f7f68"/>""",
    ),
    Character(
        "whale", "Splash the Whale", "#7cb8f5", "#559ae0", "#e3f1ff", "none", "#2f6ba8",
        muzzle_shape="narrow",
        crest="""<path d="M60 22 q-3 -12 -12 -18 q10 0 14 8 q4 -8 14 -8 q-9 6 -12 18z"
                       fill="#bfe0ff" stroke="#3b2c4f" stroke-width="3"
                       stroke-linejoin="round"/>""",
        overlay="""<path d="M22 60 q-12 -8 -16 -2 q8 4 12 10z" fill="#559ae0" stroke="#3b2c4f"
                         stroke-width="3" stroke-linejoin="round"/>
                   <path d="M98 60 q12 -8 16 -2 q-8 4 -12 10z" fill="#559ae0" stroke="#3b2c4f"
                         stroke-width="3" stroke-linejoin="round"/>""",
    ),
    Character(
        "tiger", "Tiggy the Tiger", "#ffc046", "#e8a21f", "#fff6e0", "round", "#7a5410",
        overlay="""<path d="M52 30 q2 8 0 12 M60 27 q2 9 0 13 M68 30 q-2 8 0 12"
                         stroke="#8a5f12" stroke-width="3.4" fill="none" stroke-linecap="round"
                         opacity=".85"/>
                   <path d="M24 64 q7 3 11 1 M96 64 q-7 3 -11 1" stroke="#8a5f12"
                         stroke-width="3.4" fill="none" stroke-linecap="round" opacity=".85"/>""",
    ),
    Character(
        "unicorn", "Twinkle the Unicorn", "#fdf6ff", "#e6d8f5", "#ffeef8", "pointy", "#c77b93",
        crest="""<path d="M60 6 L67 30 H53 Z" fill="#ffd166" stroke="#3b2c4f"
                       stroke-width="3" stroke-linejoin="round"/>
                 <path d="M56 24 h8 M57 17 h6" stroke="#e0a92b" stroke-width="2.4"
                       stroke-linecap="round"/>
                 <path d="M36 30 q10 -14 24 -8 q-8 10 -24 8z" fill="#ff9ec7"
                       stroke="#3b2c4f" stroke-width="3" stroke-linejoin="round"/>
                 <path d="M84 30 q-10 -14 -24 -8 q8 10 24 8z" fill="#a78bfa"
                       stroke="#3b2c4f" stroke-width="3" stroke-linejoin="round"/>""",
        overlay="""<path d="M22 58 q-8 10 -2 18 q6 -8 6 -18z" fill="#ff9ec7"
                         stroke="#3b2c4f" stroke-width="2.6" stroke-linejoin="round"/>
                   <path d="M98 58 q8 10 2 18 q-6 -8 -6 -18z" fill="#a78bfa"
                         stroke="#3b2c4f" stroke-width="2.6" stroke-linejoin="round"/>""",
    ),
    Character(
        "hedgehog", "Prickle the Hedgehog", "#e8cba8", "#c8a882", "#fff3e4", "tiny", "#6b533a",
        crest="""<path d="M16 54 L22 22 L32 44 L40 14 L50 40 L60 10 L70 40 L80 14 L88 44
                        L98 22 L104 54 Z" fill="#a9825a" stroke="#3b2c4f" stroke-width="3.2"
                       stroke-linejoin="round"/>""",
    ),
]

CHARACTERS_BY_ID = {c.id: c for c in CHARACTERS}

# Older profiles stored an emoji in avatar_emoji. Map them onto the new
# characters so nobody's saved choice is lost.
EMOJI_TO_CHARACTER = {
    "🦊": "fox", "🐼": "panda", "🐨": "bear", "🦁": "tiger", "🐯": "tiger",
    "🐸": "frog", "🐙": "whale", "🦄": "unicorn", "🐧": "penguin", "🦉": "owl",
    "🐝": "tiger", "🦋": "bunny", "🐳": "whale", "🦕": "dragon", "🐰": "bunny",
    "🐷": "bunny", "🐱": "cat", "🐶": "bear", "🐢": "frog",
}


def character_id(value: str | None) -> str:
    """Resolve a stored avatar value (character id or legacy emoji) to an id."""
    if not value:
        return CHARACTERS[0].id
    if value in CHARACTERS_BY_ID:
        return value
    return EMOJI_TO_CHARACTER.get(value, CHARACTERS[0].id)


def character(value: str | None) -> Character:
    return CHARACTERS_BY_ID[character_id(value)]


def _ears(kind: str, fur: str, fur_dark: str, muzzle: str) -> str:
    stroke = f'stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"'
    if kind == "pointy":
        # Ears must overlap the head outline, or they read as floating horns.
        return (
            f'<path d="M20 52 L26 14 L54 34 Z" fill="{fur}" {stroke}/>'
            f'<path d="M100 52 L94 14 L66 34 Z" fill="{fur}" {stroke}/>'
            f'<path d="M27 44 L30 25 L44 35 Z" fill="{muzzle}"/>'
            f'<path d="M93 44 L90 25 L76 35 Z" fill="{muzzle}"/>'
        )
    if kind == "tall":
        return (
            f'<ellipse cx="42" cy="18" rx="10" ry="24" fill="{fur}" {stroke}/>'
            f'<ellipse cx="78" cy="18" rx="10" ry="24" fill="{fur}" {stroke}/>'
            f'<ellipse cx="42" cy="20" rx="4.5" ry="15" fill="{muzzle}"/>'
            f'<ellipse cx="78" cy="20" rx="4.5" ry="15" fill="{muzzle}"/>'
        )
    if kind == "tiny":
        return (
            f'<circle cx="32" cy="36" r="11" fill="{fur_dark}" {stroke}/>'
            f'<circle cx="88" cy="36" r="11" fill="{fur_dark}" {stroke}/>'
        )
    if kind == "flop":
        return (
            f'<path d="M24 40 q-10 22 8 26 q10 -14 6 -28z" fill="{fur_dark}" {stroke}/>'
            f'<path d="M96 40 q10 22 -8 26 q-10 -14 -6 -28z" fill="{fur_dark}" {stroke}/>'
        )
    if kind == "none":
        return ""
    # round
    return (
        f'<circle cx="30" cy="34" r="15" fill="{fur}" {stroke}/>'
        f'<circle cx="90" cy="34" r="15" fill="{fur}" {stroke}/>'
        f'<circle cx="30" cy="34" r="8" fill="{muzzle}"/>'
        f'<circle cx="90" cy="34" r="8" fill="{muzzle}"/>'
    )


def character_symbol(c: Character) -> str:
    """One character's face as an SVG symbol.

    Every character shares this construction so the set looks like a family:
    same head, same eye highlights, same cheek blush, same outline weight.
    """
    muzzle = ""
    if c.muzzle_shape == "wide":
        muzzle = f'<ellipse cx="60" cy="86" rx="21" ry="15" fill="{c.muzzle}"/>'
    elif c.muzzle_shape == "narrow":
        muzzle = f'<ellipse cx="60" cy="88" rx="15" ry="10" fill="{c.muzzle}"/>'

    eyes = ""
    if c.eyes:
        eyes = f"""<g class="art-eyes">
      <ellipse cx="45" cy="63" rx="6.5" ry="7.5" fill="{INK}"/>
      <ellipse cx="75" cy="63" rx="6.5" ry="7.5" fill="{INK}"/>
      <circle cx="47.4" cy="60" r="2.4" fill="{WHITE}"/>
      <circle cx="77.4" cy="60" r="2.4" fill="{WHITE}"/>
    </g>"""

    mouth = ""
    if c.mouth == "smile":
        mouth = (
            f'<ellipse cx="60" cy="79" rx="5" ry="3.6" fill="{c.nose}"/>'
            f'<path d="M52 87 q8 7 16 0" fill="none" stroke="{INK}" stroke-width="3"'
            f' stroke-linecap="round"/>'
        )

    return f"""<symbol id="char-{c.id}" viewBox="0 0 120 120">
  <g class="art-char">
    {c.crest}
    {_ears(c.ears, c.fur, c.fur_dark, c.muzzle)}
    <ellipse cx="60" cy="67" rx="45" ry="42" fill="{c.fur}"
             stroke="{INK}" stroke-width="3.5"/>
    <ellipse cx="60" cy="52" rx="38" ry="26" fill="{WHITE}" opacity=".14"/>
    {c.under}
    {muzzle}
    {eyes}
    <ellipse cx="27" cy="78" rx="8" ry="5" fill="{BLUSH}" opacity=".5"/>
    <ellipse cx="93" cy="78" rx="8" ry="5" fill="{BLUSH}" opacity=".5"/>
    {mouth}
    {c.overlay}
  </g>
</symbol>"""


# ---------------------------------------------------------------------------
# Pip, the guide mascot
# ---------------------------------------------------------------------------

PIP_BODY = "#8b7cf0"
PIP_BODY_DARK = "#6f5fd6"
PIP_BELLY = "#efeaff"


def _pip(name: str, face: str, arms: str = "", extra: str = "") -> str:
    return f"""<symbol id="pip-{name}" viewBox="0 0 120 120">
  <g class="art-pip">
    <path d="M60 12 q3 -9 10 -10 q-2 8 -8 11z" fill="#7ed957" stroke="{INK}"
          stroke-width="3" stroke-linejoin="round"/>
    <path d="M60 16 C88 16 100 42 100 66 C100 94 82 108 60 108
             C38 108 20 94 20 66 C20 42 32 16 60 16 Z"
          fill="{PIP_BODY}" stroke="{INK}" stroke-width="3.5"/>
    <ellipse cx="60" cy="44" rx="30" ry="20" fill="{WHITE}" opacity=".16"/>
    <path d="M60 70 C74 70 84 78 84 88 C84 98 74 104 60 104
             C46 104 36 98 36 88 C36 78 46 70 60 70 Z" fill="{PIP_BELLY}"/>
    {arms}
    {face}
    {extra}
  </g>
</symbol>"""


def pip_symbols() -> str:
    eyes_open = (
        f'<ellipse cx="47" cy="54" rx="7" ry="8" fill="{INK}"/>'
        f'<ellipse cx="73" cy="54" rx="7" ry="8" fill="{INK}"/>'
        f'<circle cx="49.6" cy="50.6" r="2.6" fill="{WHITE}"/>'
        f'<circle cx="75.6" cy="50.6" r="2.6" fill="{WHITE}"/>'
    )
    blush = (
        f'<ellipse cx="32" cy="66" rx="7" ry="4.5" fill="{BLUSH}" opacity=".5"/>'
        f'<ellipse cx="88" cy="66" rx="7" ry="4.5" fill="{BLUSH}" opacity=".5"/>'
    )
    arms_down = (
        f'<path d="M22 74 q-9 6 -6 15" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        f'<path d="M98 74 q9 6 6 15" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
    )
    arms_up = (
        f'<path d="M22 70 q-12 -8 -12 -20" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        f'<path d="M98 70 q12 -8 12 -20" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
    )

    idle = _pip(
        "idle",
        eyes_open + blush + f'<path d="M52 66 q8 7 16 0" fill="none" stroke="{INK}"'
        f' stroke-width="3" stroke-linecap="round"/>',
        arms_down,
    )
    happy = _pip(
        "happy",
        f'<path d="M40 52 q7 -8 14 0" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        f'<path d="M66 52 q7 -8 14 0" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        + blush
        + f'<path d="M48 62 q12 14 24 0 z" fill="{INK}"/>'
        f'<path d="M53 70 q7 5 14 0" fill="{BLUSH}"/>',
        arms_up,
    )
    think = _pip(
        "think",
        f'<ellipse cx="47" cy="54" rx="7" ry="8" fill="{INK}"/>'
        f'<ellipse cx="73" cy="52" rx="7" ry="4" fill="{INK}"/>'
        f'<circle cx="49.6" cy="50.6" r="2.6" fill="{WHITE}"/>'
        + blush
        + f'<path d="M52 68 q10 -4 16 2" fill="none" stroke="{INK}" stroke-width="3"'
        f' stroke-linecap="round"/>',
        arms_down,
        extra=f'<circle cx="98" cy="28" r="5" fill="{WHITE}" stroke="{INK}" stroke-width="2.5"/>'
        f'<circle cx="108" cy="16" r="3" fill="{WHITE}" stroke="{INK}" stroke-width="2"/>',
    )
    oops = _pip(
        "oops",
        eyes_open
        + blush
        + f'<ellipse cx="60" cy="70" rx="7" ry="5.5" fill="{INK}"/>',
        arms_down,
    )
    cheer = _pip(
        "cheer",
        f'<path d="M40 52 q7 -8 14 0" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        f'<path d="M66 52 q7 -8 14 0" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        + blush
        + f'<path d="M46 60 q14 18 28 0 z" fill="{INK}"/>'
        f'<path d="M52 69 q8 6 16 0" fill="{BLUSH}"/>',
        arms_up,
        extra=f'<path d="M14 24 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" fill="#ffd166"'
        f' stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>'
        f'<path d="M104 34 l2.4 5.6 5.6 2.4 -5.6 2.4 -2.4 5.6 -2.4 -5.6 -5.6 -2.4'
        f' 5.6 -2.4z" fill="#ffd166" stroke="{INK}" stroke-width="1.4"'
        f' stroke-linejoin="round"/>',
    )
    sleep = _pip(
        "sleep",
        f'<path d="M40 54 q7 6 14 0" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        f'<path d="M66 54 q7 6 14 0" fill="none" stroke="{INK}" stroke-width="3.5"'
        f' stroke-linecap="round"/>'
        + blush
        + f'<ellipse cx="60" cy="70" rx="5" ry="4" fill="{INK}"/>',
        arms_down,
        extra=f'<text x="96" y="34" font-size="18" font-weight="800" fill="{PIP_BODY_DARK}"'
        f' font-family="inherit">z</text>'
        f'<text x="106" y="20" font-size="12" font-weight="800" fill="{PIP_BODY_DARK}"'
        f' font-family="inherit">z</text>',
    )
    return idle + happy + think + oops + cheer + sleep


# ---------------------------------------------------------------------------
# Subject icons
# ---------------------------------------------------------------------------


def subject_symbols() -> str:
    """Illustrated subject icons: number blocks, a book, and a sprouting flask."""
    maths = f"""<symbol id="icon-maths" viewBox="0 0 120 120">
  <rect x="16" y="62" width="40" height="40" rx="8" fill="#ff8fab" stroke="{INK}" stroke-width="3.5"/>
  <rect x="62" y="62" width="40" height="40" rx="8" fill="#ffd166" stroke="{INK}" stroke-width="3.5"/>
  <rect x="39" y="20" width="40" height="40" rx="8" fill="#8ecae6" stroke="{INK}" stroke-width="3.5"/>
  <path d="M30 82 h12 M36 76 v12" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
  <path d="M74 82 h14" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
  <path d="M50 40 h18 M50 34 h18" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
</symbol>"""
    english = f"""<symbol id="icon-english" viewBox="0 0 120 120">
  <path d="M60 30 C48 22 30 22 18 26 v62 c12 -4 30 -4 42 4z" fill="#ffffff"
        stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M60 30 C72 22 90 22 102 26 v62 c-12 -4 -30 -4 -42 4z" fill="#eaf4ff"
        stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M60 30 v66" stroke="{INK}" stroke-width="3.5"/>
  <path d="M28 40 h22 M28 52 h22 M28 64 h16" stroke="#8ecae6" stroke-width="3.5"
        stroke-linecap="round"/>
  <path d="M70 40 h22 M70 52 h22 M70 64 h16" stroke="#8ecae6" stroke-width="3.5"
        stroke-linecap="round"/>
  <path d="M84 20 v34 l8 -7 8 7 V20z" fill="#ff8fab" stroke="{INK}" stroke-width="3"
        stroke-linejoin="round"/>
</symbol>"""
    science = f"""<symbol id="icon-science" viewBox="0 0 120 120">
  <path d="M50 20 h20 v22 l18 40 a10 10 0 0 1 -9 14 H41 a10 10 0 0 1 -9 -14 l18 -40z"
        fill="#eafff8" stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M37 72 h46 l5 12 a10 10 0 0 1 -9 14 H41 a10 10 0 0 1 -9 -14z" fill="#69d2b0"/>
  <path d="M46 18 h28" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
  <circle cx="52" cy="84" r="4" fill="#ffffff" opacity=".85"/>
  <circle cx="68" cy="90" r="3" fill="#ffffff" opacity=".85"/>
  <path d="M60 62 q-14 -6 -12 -22 q12 2 12 22z" fill="#7ed957" stroke="{INK}"
        stroke-width="2.5" stroke-linejoin="round"/>
  <path d="M60 62 q14 -10 14 -26 q-14 6 -14 26z" fill="#a5e887" stroke="{INK}"
        stroke-width="2.5" stroke-linejoin="round"/>
</symbol>"""
    gcse_maths = f"""<symbol id="icon-gcse_maths" viewBox="0 0 120 120">
  <path d="M20 88 A40 40 0 0 1 100 88" fill="#efe5ff" stroke="{INK}" stroke-width="3.5"/>
  <path d="M28 88 h64" stroke="{INK}" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M60 88 V42 M42 88 L48 51 M78 88 L72 51" stroke="#8b5cf6" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="60" cy="88" r="6" fill="#ffd166" stroke="{INK}" stroke-width="3"/>
  <path d="M32 101 h56" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
</symbol>"""
    gcse_physics = f"""<symbol id="icon-gcse_physics" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="12" fill="#ffd166" stroke="{INK}" stroke-width="3.5"/>
  <ellipse cx="60" cy="60" rx="43" ry="18" fill="none" stroke="#2481cc" stroke-width="3.5" transform="rotate(25 60 60)"/>
  <ellipse cx="60" cy="60" rx="43" ry="18" fill="none" stroke="#69d2b0" stroke-width="3.5" transform="rotate(-25 60 60)"/>
  <circle cx="22" cy="78" r="5" fill="#8ecae6" stroke="{INK}" stroke-width="2.5"/>
  <circle cx="98" cy="42" r="5" fill="#ff8fab" stroke="{INK}" stroke-width="2.5"/>
  <path d="M60 20 v-8 M60 108 v-8 M20 60 h-8 M108 60 h-8" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>
</symbol>"""
    return maths + english + science + gcse_maths + gcse_physics


# ---------------------------------------------------------------------------
# Hats, badges and scenery
# ---------------------------------------------------------------------------

HAT_SHAPES: dict[str, str] = {
    "hat-party": f"""<path d="M60 8 L84 62 H36 Z" fill="#ff6b9d" stroke="{INK}" stroke-width="3.5"
        stroke-linejoin="round"/>
      <circle cx="60" cy="8" r="7" fill="#ffd166" stroke="{INK}" stroke-width="3"/>
      <path d="M44 46 q10 -6 20 0 M48 32 q8 -5 16 0" stroke="#ffffff" stroke-width="4"
        stroke-linecap="round" fill="none"/>""",
    "hat-crown": f"""<path d="M28 58 L26 20 L44 36 L60 12 L76 36 L94 20 L92 58 Z" fill="#ffd166"
        stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>
      <rect x="28" y="56" width="64" height="12" rx="5" fill="#f0b429" stroke="{INK}"
        stroke-width="3.5"/>
      <circle cx="60" cy="42" r="5" fill="#ff6b9d" stroke="{INK}" stroke-width="2.5"/>""",
    "hat-wizard": f"""<path d="M60 4 C70 26 82 50 92 62 H28 C38 50 50 26 60 4 Z" fill="#6a5acd"
        stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>
      <path d="M22 60 h76 v12 H22 z" rx="4" fill="#4b3fa8" stroke="{INK}" stroke-width="3.5"/>
      <path d="M56 30 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" fill="#ffd166"/>""",
    "hat-cap": f"""<path d="M26 58 a34 30 0 0 1 68 0 z" fill="#3aa8db" stroke="{INK}"
        stroke-width="3.5" stroke-linejoin="round"/>
      <path d="M90 56 q22 2 22 12 H86 z" fill="#2b8ab8" stroke="{INK}" stroke-width="3.5"
        stroke-linejoin="round"/>
      <circle cx="60" cy="26" r="5" fill="#ffd166" stroke="{INK}" stroke-width="2.5"/>""",
    "hat-graduate": f"""<path d="M60 18 L104 38 L60 58 L16 38 Z" fill="#3b2c4f" stroke="{INK}"
        stroke-width="3.5" stroke-linejoin="round"/>
      <path d="M40 46 v18 q20 10 40 0 V46" fill="#2a1f3a" stroke="{INK}" stroke-width="3.5"
        stroke-linejoin="round"/>
      <path d="M100 40 v22" stroke="#ffd166" stroke-width="4" stroke-linecap="round"/>
      <circle cx="100" cy="66" r="6" fill="#ffd166" stroke="{INK}" stroke-width="2.5"/>""",
    "hat-flower": f"""<path d="M22 60 q38 -16 76 0" fill="none" stroke="#7ed957" stroke-width="7"
        stroke-linecap="round"/>
      <g>
        <circle cx="36" cy="52" r="9" fill="#ff8fab" stroke="{INK}" stroke-width="2.5"/>
        <circle cx="60" cy="44" r="10" fill="#ffd166" stroke="{INK}" stroke-width="2.5"/>
        <circle cx="84" cy="52" r="9" fill="#a78bfa" stroke="{INK}" stroke-width="2.5"/>
        <circle cx="60" cy="44" r="3.5" fill="#ffffff"/>
      </g>""",
}


# Each hat is drawn where it was convenient to draw it, so each one's brim — the
# line that should rest on a head — sits at a different height. These nudges move
# every brim onto y=68 of a shared, tightened viewBox, so one CSS rule can place
# any hat on any character. Without this a hat either floats above the head or
# sinks into it, depending which hat it is.
HAT_BRIM_NUDGE: dict[str, float] = {
    "hat-party": 4.25,     # cone base
    "hat-crown": -1.75,    # band underside
    "hat-wizard": -5.75,   # brim underside
    "hat-cap": -1.75,      # crown underside, ignoring the peak
    "hat-graduate": -1.0,  # board underside; the tassel is meant to hang below
    "hat-flower": 4.5,     # stem
}
HAT_VIEWBOX = "0 0 120 72"


def hat_symbols() -> str:
    out = []
    for hat_id, body in HAT_SHAPES.items():
        nudge = HAT_BRIM_NUDGE[hat_id]
        out.append(
            f'<symbol id="{hat_id}" viewBox="{HAT_VIEWBOX}">'
            f'<g transform="translate(0 {nudge})">{body}</g>'
            f"</symbol>"
        )
    return "".join(out)


BADGE_TIERS = {
    "start": ("#8ecae6", "#5fa8cc"),
    "streak": ("#ff8a4c", "#e56a2c"),
    "skill": ("#a78bfa", "#8b6cf0"),
    "mastery": ("#ffd166", "#f0b429"),
    "subject": ("#7ed957", "#5cb63c"),
    "ahead": ("#69d2b0", "#45b592"),
    "fun": ("#ff8fab", "#f06a90"),
}


def badge_symbols() -> str:
    """A rosette per badge group, so badges look like awards rather than emoji."""
    out = []
    for group, (light, dark) in BADGE_TIERS.items():
        out.append(f"""<symbol id="rosette-{group}" viewBox="0 0 120 120">
  <path d="M42 78 L28 112 L46 104 L52 116 L64 84 Z" fill="{dark}" stroke="{INK}"
        stroke-width="3" stroke-linejoin="round"/>
  <path d="M78 78 L92 112 L74 104 L68 116 L56 84 Z" fill="{dark}" stroke="{INK}"
        stroke-width="3" stroke-linejoin="round"/>
  <circle cx="60" cy="52" r="40" fill="{dark}" stroke="{INK}" stroke-width="3.5"/>
  <circle cx="60" cy="52" r="31" fill="{light}" stroke="{INK}" stroke-width="3"/>
  <circle cx="60" cy="52" r="31" fill="none" stroke="#ffffff" stroke-width="2"
          stroke-dasharray="4 6" opacity=".7"/>
  <ellipse cx="50" cy="38" rx="10" ry="6" fill="#ffffff" opacity=".45"
           transform="rotate(-25 50 38)"/>
</symbol>""")
    return "".join(out)


def scenery_symbols() -> str:
    """Decorative pieces for page headers."""
    return f"""<symbol id="scene-hills" viewBox="0 0 400 120" preserveAspectRatio="none">
  <path d="M0 78 Q60 44 120 74 T240 70 Q310 44 400 76 V120 H0 Z" fill="#7ed957" opacity=".55"/>
  <path d="M0 92 Q80 64 160 90 T320 86 Q368 70 400 90 V120 H0 Z" fill="#5cb63c" opacity=".65"/>
</symbol>
<symbol id="scene-cloud" viewBox="0 0 120 60">
  <path d="M20 44 a16 16 0 0 1 4 -31 a20 20 0 0 1 37 -4 a15 15 0 0 1 22 8
           a14 14 0 0 1 1 27 Z" fill="#ffffff" opacity=".92"/>
</symbol>
<symbol id="scene-sparkle" viewBox="0 0 24 24">
  <path d="M12 1 l3 7.5 7.5 3.5 -7.5 3.5 -3 7.5 -3 -7.5 -7.5 -3.5 7.5 -3.5z"
        fill="#ffd166" stroke="{INK}" stroke-width="1.4" stroke-linejoin="round"/>
</symbol>
<symbol id="scene-star" viewBox="0 0 48 48">
  <path d="M24 3 L30.4 17.6 L46 19.4 L34.4 30 L37.6 45.4 L24 37.8 L10.4 45.4
           L13.6 30 L2 19.4 L17.6 17.6 Z"
        fill="#ffd166" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>
  <path d="M24 10 L28 20 L20 20 Z" fill="#ffffff" opacity=".45"/>
</symbol>
<symbol id="scene-star-empty" viewBox="0 0 48 48">
  <path d="M24 3 L30.4 17.6 L46 19.4 L34.4 30 L37.6 45.4 L24 37.8 L10.4 45.4
           L13.6 30 L2 19.4 L17.6 17.6 Z"
        fill="#efe9f5" stroke="#c9c0d8" stroke-width="3" stroke-linejoin="round"/>
</symbol>
<symbol id="scene-tick" viewBox="0 0 48 48">
  <circle cx="24" cy="24" r="20" fill="#4ec97b" stroke="{INK}" stroke-width="3.2"/>
  <path d="M14 25 l7 7 13 -15" fill="none" stroke="#ffffff" stroke-width="5"
        stroke-linecap="round" stroke-linejoin="round"/>
</symbol>
<symbol id="scene-speaker" viewBox="0 0 48 48">
  <path d="M8 19 h7 l10 -9 v28 l-10 -9 H8 z" fill="#8ecae6" stroke="{INK}"
        stroke-width="3.2" stroke-linejoin="round"/>
  <path d="M31 18 q6 6 0 12" fill="none" stroke="{INK}" stroke-width="3.2"
        stroke-linecap="round"/>
  <path d="M37 13 q11 11 0 22" fill="none" stroke="{INK}" stroke-width="3.2"
        stroke-linecap="round"/>
</symbol>
<symbol id="scene-bulb" viewBox="0 0 48 48">
  <path d="M24 5 a14 14 0 0 1 8 25 v4 H16 v-4 a14 14 0 0 1 8 -25z" fill="#ffd166"
        stroke="{INK}" stroke-width="3.2" stroke-linejoin="round"/>
  <path d="M17 38 h14 M19 43 h10" stroke="{INK}" stroke-width="3.4" stroke-linecap="round"/>
  <path d="M24 14 v10" stroke="#a9791a" stroke-width="2.6" stroke-linecap="round"/>
</symbol>
<symbol id="scene-tree" viewBox="0 0 60 80">
  <rect x="25" y="46" width="10" height="30" rx="4" fill="#a9763f" stroke="{INK}"
        stroke-width="3"/>
  <circle cx="30" cy="34" r="20" fill="#7ed957" stroke="{INK}" stroke-width="3"/>
  <circle cx="18" cy="42" r="12" fill="#8fe36a" stroke="{INK}" stroke-width="3"/>
  <circle cx="42" cy="42" r="12" fill="#68c94a" stroke="{INK}" stroke-width="3"/>
</symbol>
<symbol id="scene-coin" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="17" fill="#ffd166" stroke="{INK}" stroke-width="3"/>
  <circle cx="20" cy="20" r="11" fill="none" stroke="#e0a92b" stroke-width="2.5"/>
  <path d="M20 12 v16 M16 16 h8 M16 24 h8" stroke="#a9791a" stroke-width="2.6"
        stroke-linecap="round"/>
</symbol>
<symbol id="scene-flame" viewBox="0 0 40 44">
  <!-- A single smooth teardrop reads as a water droplet. The second tongue on
       the left and the notch between them are what make this read as fire. -->
  <path d="M21 3 C26 13 33 17 33 27 a13 13 0 0 1 -26 0 C7 20 11 17 13 11
           c1 4 3 5 4 7 C19 14 20 9 21 3 Z"
        fill="#ff8a4c" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>
  <path d="M20 18 C23 23 26 25 26 30 a6.5 6.5 0 0 1 -13 0 c0 -5 4 -7 7 -12z"
        fill="#ffd166"/>
</symbol>
<symbol id="scene-lock" viewBox="0 0 40 44">
  <rect x="8" y="19" width="24" height="20" rx="5" fill="#c3bcd0" stroke="{INK}"
        stroke-width="3"/>
  <path d="M14 19 v-5 a6 6 0 0 1 12 0 v5" fill="none" stroke="{INK}" stroke-width="3"
        stroke-linecap="round"/>
  <circle cx="20" cy="29" r="3.4" fill="{INK}"/>
</symbol>"""


# ---------------------------------------------------------------------------
# The sprite
# ---------------------------------------------------------------------------


def _sprite_markup() -> str:
    parts = [character_symbol(c) for c in CHARACTERS]
    parts.append(pip_symbols())
    parts.append(subject_symbols())
    parts.append(hat_symbols())
    parts.append(badge_symbols())
    parts.append(scenery_symbols())
    return "".join(parts)


@lru_cache(maxsize=1)
def viewboxes() -> dict[str, str]:
    """{symbol id: its viewBox}.

    The wrapping ``<svg>`` around a ``<use>`` must carry the same viewBox as the
    symbol it references. Without it the artwork is laid out at its intrinsic
    size and spills outside its container — which is exactly what happened to
    the avatar until this was added.
    """
    found = {}
    for match in re.finditer(
        r'<symbol id="([^"]+)" viewBox="([^"]+)"', _sprite_markup()
    ):
        found[match.group(1)] = match.group(2)
    return found


def viewbox(symbol_id: str) -> str:
    return viewboxes().get(symbol_id, "0 0 120 120")


@lru_cache(maxsize=1)
def sprite() -> str:
    """The whole artwork sheet, emitted once per page."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"'
        ' style="position:absolute;width:0;height:0;overflow:hidden">'
        + _sprite_markup()
        + "</svg>"
    )


# Avatar background washes, referenced by name from the settings a parent picks.
COLOUR_THEMES: dict[str, tuple[str, str]] = {
    "sunshine": ("#fff0c9", "#ffd77a"),
    "berry": ("#ffdcea", "#ffa8c8"),
    "ocean": ("#d5ecff", "#8ecdf7"),
    "leaf": ("#dcf7dc", "#96e39a"),
    "grape": ("#e8ddff", "#bda6f7"),
    "peach": ("#ffe2dc", "#ffb3a3"),
}


@dataclass(frozen=True)
class Scene:
    id: str
    name: str
    sky: tuple[str, str]
    props: str = ""
    fields: dict = field(default_factory=dict)


SCENES: dict[str, Scene] = {
    "scene-space": Scene("scene-space", "Outer Space", ("#2b2456", "#5b4b9e")),
    "scene-beach": Scene("scene-beach", "Sunny Beach", ("#ffe9c2", "#8ed7f0")),
    "scene-forest": Scene("scene-forest", "Magic Forest", ("#d8f5d8", "#7ec97e")),
    "scene-castle": Scene("scene-castle", "Castle", ("#e6e0ff", "#a99bdf")),
    "scene-rainbow": Scene("scene-rainbow", "Rainbow", ("#fff0f6", "#ffd0e4")),
}


def scene_gradient(scene_id: str | None) -> tuple[str, str]:
    scene = SCENES.get(scene_id or "")
    return scene.sky if scene else ("#eaf6ff", "#d7ecff")
