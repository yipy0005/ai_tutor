"""Creating learner profiles, and reading/writing the parent settings form."""

from __future__ import annotations

from sqlalchemy import select

from ..config import Config
from ..content import SKILLS_BY_ID, SUBJECT_ORDER
from ..extensions import db
from ..models import Child, ParentAccount, Settings

DIFFICULTY_MODES = {
    "gentle": "Gentle — keep it easy and confident",
    "adaptive": "Adaptive — match the questions to her level (recommended)",
    "challenge": "Challenge — push a bit harder",
}


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------


def all_children() -> list[Child]:
    return list(
        db.session.execute(select(Child).order_by(Child.id)).scalars().all()
    )


def get_child(child_id: int) -> Child | None:
    return db.session.get(Child, child_id)


def create_child(
    name: str,
    year_group: int = 3,
    avatar_emoji: str = "fox",
    avatar_colour: str = "sunshine",
) -> Child:
    child = Child(
        name=name.strip()[:60] or "Learner",
        year_group=max(1, min(6, int(year_group))),
        avatar_emoji=avatar_emoji,
        avatar_colour=avatar_colour,
    )
    db.session.add(child)
    db.session.flush()

    settings = Settings(child_id=child.id)
    # A child about to start Year 3 gets a summer mix that leans towards new
    # Year 3 work while keeping Year 1 and 2 ticking over.
    if child.year_group >= 3:
        settings.year_mix = {"1": 15, "2": 35, "3": 50}
    else:
        settings.year_mix = {"1": 30, "2": 45, "3": 25}
    db.session.add(settings)
    db.session.flush()
    return child


def delete_child(child: Child) -> None:
    db.session.delete(child)
    db.session.commit()


# ---------------------------------------------------------------------------
# Parent account
# ---------------------------------------------------------------------------


def ensure_parent_account(pin: str | None = None) -> ParentAccount:
    """Fetch the parent account, creating it with ``pin`` if it does not exist.

    Note that an existing account is returned untouched — passing ``pin`` will
    not change an already-set PIN. Call ``set_pin`` for that.
    """
    account = ParentAccount.get()
    if account is None:
        account = ParentAccount(id=1, pin_hash="")
        account.set_pin(pin or Config.DEFAULT_PARENT_PIN)
        db.session.add(account)
        db.session.flush()
    return account


# ---------------------------------------------------------------------------
# Settings form
# ---------------------------------------------------------------------------

BOOLEAN_FIELDS = [
    "allow_hints",
    "second_chance",
    "show_explanations",
    "sound_enabled",
    "animations_enabled",
    "read_aloud",
    "read_aloud_auto",
    "dyslexia_font",
    "large_text",
    "high_contrast",
    "show_timer",
    "shop_enabled",
]

INT_FIELDS = {
    # field: (minimum, maximum)
    "quest_length": (4, 15),
    "daily_limit_minutes": (0, 240),
    "daily_quest_goal": (0, 12),
    "break_after_minutes": (0, 60),
    "weekly_quest_goal": (0, 100),
    "allowed_from_hour": (0, 23),
    "allowed_to_hour": (0, 23),
}


def _as_int(value, low: int, high: int, fallback: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def apply_settings(settings: Settings, form) -> list[str]:
    """Update a Settings row from a submitted form. Returns warning messages."""
    warnings: list[str] = []

    for field, (low, high) in INT_FIELDS.items():
        if field in form:
            setattr(settings, field, _as_int(form.get(field), low, high, getattr(settings, field)))

    for field in BOOLEAN_FIELDS:
        # An unchecked checkbox is simply absent from the POST body.
        setattr(settings, field, form.get(field) in {"on", "1", "true", "yes"})

    mode = (form.get("difficulty_mode") or "").strip()
    if mode in DIFFICULTY_MODES:
        settings.difficulty_mode = mode

    subjects = [s for s in form.getlist("subjects_enabled") if s in SUBJECT_ORDER]
    if subjects:
        settings.subjects_enabled = subjects
    else:
        warnings.append("At least one subject must stay switched on, so nothing was changed there.")

    years = []
    for value in form.getlist("years_enabled"):
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if year in (1, 2, 3):
            years.append(year)
    if years:
        settings.years_enabled = sorted(set(years))
    else:
        warnings.append("At least one year group must stay switched on, so nothing was changed there.")

    mix = {}
    for year in (1, 2, 3):
        mix[str(year)] = _as_int(
            form.get(f"year_mix_{year}"), 0, 100, (settings.year_mix or {}).get(str(year), 33)
        )
    if sum(mix.values()) == 0:
        warnings.append("The revision balance cannot be all zeros, so it was left as it was.")
    else:
        settings.year_mix = mix

    focus = [sid for sid in form.getlist("focus_skills") if sid in SKILLS_BY_ID]
    settings.focus_skills = focus[:20]
    if len(focus) > 20:
        warnings.append("Only the first 20 focus skills were kept.")

    settings.reward_note = (form.get("reward_note") or "").strip()[:300]
    settings.cheer_note = (form.get("cheer_note") or "").strip()[:300]

    if settings.allowed_from_hour == settings.allowed_to_hour:
        warnings.append(
            "The start and end hour are the same, so the app is available all day."
        )

    return warnings


def settings_summary(settings: Settings) -> list[tuple[str, str]]:
    """A short human-readable summary shown at the top of the settings page."""
    limit = (
        f"{settings.daily_limit_minutes} minutes a day"
        if settings.daily_limit_minutes
        else "No daily time limit"
    )
    mix = settings.year_weights()
    total = sum(mix.values()) or 1
    mix_text = ", ".join(
        f"Y{year} {round(weight / total * 100)}%" for year, weight in sorted(mix.items())
    )
    return [
        ("Questions per quest", str(settings.quest_length)),
        ("Daily limit", limit),
        ("Available", f"{settings.allowed_from_hour}:00 – {settings.allowed_to_hour}:00"),
        ("Difficulty", DIFFICULTY_MODES.get(settings.difficulty_mode, settings.difficulty_mode)),
        ("Subjects", ", ".join(s.title() for s in (settings.subjects_enabled or []))),
        ("Year balance", mix_text),
        ("Weekly goal", f"{settings.weekly_quest_goal} quests"),
    ]
