"""Shared rules for the learner's active curriculum pathway."""

from __future__ import annotations

from ..content import (
    ALL_SKILLS,
    GCSE_TIERS,
    PATHWAY_SUBJECT_ORDER,
    SUBJECT_ORDER,
    gcse_skills_for,
)
from ..models import Settings


def is_gcse(settings: Settings) -> bool:
    return settings.gcse_tier in GCSE_TIERS


def gcse_subject(settings: Settings) -> str:
    """Return the selected GCSE subject, with old databases defaulting to Maths."""
    subject = getattr(settings, "gcse_subject", "gcse_maths")
    return subject if subject in PATHWAY_SUBJECT_ORDER else "gcse_maths"


def subject_ids(settings: Settings) -> list[str]:
    """Return only subjects available on the learner's active pathway."""
    if is_gcse(settings):
        return [gcse_subject(settings)]
    return [
        subject
        for subject in (settings.subjects_enabled or SUBJECT_ORDER)
        if subject in SUBJECT_ORDER
    ] or [SUBJECT_ORDER[0]]


def year_ids(settings: Settings) -> list[int]:
    """Return enabled Primary years, constrained to the six-year contract."""
    years = []
    for value in settings.years_enabled or range(1, 7):
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= year <= 6:
            years.append(year)
    return sorted(set(years)) or [3]


def active_skills(settings: Settings, subject: str | None = None) -> list:
    """Return skills that belong to the learner's active pathway."""
    if is_gcse(settings):
        selected = gcse_subject(settings)
        if subject not in (None, selected):
            return []
        return list(gcse_skills_for(selected, settings.gcse_tier))

    if subject in PATHWAY_SUBJECT_ORDER:
        return []
    subjects = {subject} if subject else set(subject_ids(settings))
    years = set(year_ids(settings))
    return [
        skill
        for skill in ALL_SKILLS
        if skill.subject in subjects and skill.year in years
    ]


def active_skill_ids(settings: Settings) -> set[str]:
    """Return stable ids for the learner's currently playable curriculum."""
    return {skill.id for skill in active_skills(settings)}


def quest_matches_path(
    settings: Settings, subject: str, skill_ids: list[str]
) -> bool:
    """Check a stored quest against the complete active pathway.

    This deliberately checks enabled subjects/years and GCSE tier, not only the
    broad Primary-versus-GCSE distinction. Old quests remain stored, but they
    cannot reappear in the current learner's app after settings change.
    """
    if not skill_ids:
        return False
    if any(skill_id not in active_skill_ids(settings) for skill_id in skill_ids):
        return False
    if is_gcse(settings):
        return subject == gcse_subject(settings)
    return subject == "mixed" or subject in subject_ids(settings)
