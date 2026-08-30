"""Deciding what to practise next.

Three ideas combine here:

1. **Spaced repetition.** Every skill sits in a Leitner box with a due date.
   Skills that are due get pushed to the front, which is what turns a summer of
   short sessions into retained Primary knowledge.
2. **Mastery targeting.** Weak skills come up more often than strong ones, and
   a skill that has never been tried gets a fair chance of being introduced.
3. **Parent intent.** The year mix slider (revision versus getting ahead) and
   any focus skills a parent has ticked act as multipliers on top.

Nothing here is random-only: the same child on the same day gets a coherent
quest, but there is enough jitter that two quests in a row never feel identical.
"""

from __future__ import annotations

import random
from datetime import date

from sqlalchemy import select

from ..content import (
    ALL_SKILLS,
    Skill,
    bank_size,
    gcse_skills_for,
    get_skill,
)
from ..extensions import db
from ..models import Child, Settings, SkillProgress
from . import pathways

MODES = {
    "mixed": "A bit of everything",
    "revision": "Revision practice",
    "ahead": "New work",
    "focus": "Tricky bits",
    "skill": "One skill",
}


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def is_playable(skill: Skill) -> bool:
    """True if this skill can actually produce a question right now."""
    if skill.source == "generated":
        from ..content import generators

        return skill.generator in generators.GENERATORS
    return bank_size(skill.id) > 0


def available_skills(
    subject: str | None = None,
    years: list[int] | tuple[int, ...] | None = None,
    tier: str | None = None,
) -> list[Skill]:
    if subject == "gcse_maths":
        source = gcse_skills_for(tier)
    else:
        source = ALL_SKILLS
    wanted_years = {int(y) for y in years} if years else None
    out = []
    for skill in source:
        if subject and skill.subject != subject:
            continue
        if wanted_years and skill.year not in wanted_years:
            continue
        if not is_playable(skill):
            continue
        out.append(skill)
    return out


def skill_is_eligible(
    child: Child, skill: Skill, subject: str | None = None
) -> bool:
    """Authorize a skill against the learner's active pathway and settings."""
    settings = child.settings
    if pathways.is_gcse(settings):
        return (
            skill.is_gcse
            and skill.subject == "gcse_maths"
            and subject in (None, "gcse_maths")
            and skill.eligible_for_tier(settings.gcse_tier)
            and is_playable(skill)
        )
    if skill.is_gcse or subject == "gcse_maths":
        return False
    return (
        skill.id in pathways.active_skill_ids(settings)
        and (subject is None or skill.subject == subject)
        and is_playable(skill)
    )


def progress_map(child_id: int) -> dict[str, SkillProgress]:
    rows = db.session.execute(
        select(SkillProgress).where(SkillProgress.child_id == child_id)
    ).scalars().all()
    return {row.skill_id: row for row in rows}


def get_or_create_progress(child_id: int, skill_id: str) -> SkillProgress:
    row = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id, SkillProgress.skill_id == skill_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = SkillProgress(child_id=child_id, skill_id=skill_id, due_on=date.today())
        db.session.add(row)
        db.session.flush()
    return row


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_skill(
    skill: Skill,
    progress: SkillProgress | None,
    settings: Settings,
    year_weights: dict[int, int],
    today: date,
) -> float:
    """A positive weight. Bigger means more likely to be chosen."""
    weight = float(year_weights.get(skill.year, 1)) or 1.0

    if skill.id in (settings.focus_skills or []):
        weight *= 4.0

    if progress is None or progress.attempts == 0:
        # Brand new material: worth introducing, but not to the exclusion of
        # revision. Slightly favour new work in the child's own year group.
        weight *= 1.6
        return max(weight, 0.05)

    # Spaced repetition: overdue skills climb fast.
    days_overdue = (today - progress.due_on).days
    if days_overdue >= 0:
        weight *= 2.2 + min(days_overdue, 21) * 0.12
    else:
        # Not due yet. Still possible, just much less likely.
        weight *= 0.25

    # Weak skills come round more often.
    weight *= 0.6 + (1.0 - progress.mastery) * 1.8

    # Don't hammer something already practised today.
    if progress.last_seen_at and progress.last_seen_at.date() == today:
        weight *= 0.35

    # A skill answered correctly many times in a row can rest.
    if progress.mastery >= 0.85 and progress.current_streak >= 4:
        weight *= 0.4

    return max(weight, 0.05)


def level_for(progress: SkillProgress | None, settings: Settings) -> int:
    """Difficulty hint passed to the maths generators: 0 gentle, 1 normal, 2 hard."""
    mode = settings.difficulty_mode or "adaptive"
    if mode == "gentle":
        return 0
    if mode == "challenge":
        return 2
    if progress is None or progress.attempts < 3:
        return 1
    if progress.mastery < 0.4:
        return 0
    if progress.mastery >= 0.85:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Choosing the skills for a quest
# ---------------------------------------------------------------------------


def years_for_mode(mode: str, settings: Settings) -> list[int]:
    enabled = pathways.year_ids(settings)
    latest = max(enabled)
    if mode == "revision":
        picked = [year for year in enabled if year < latest]
    elif mode == "ahead":
        picked = [latest]
    else:
        picked = enabled
    return picked or enabled


def pick_skills(
    child: Child,
    subject: str | None,
    mode: str = "mixed",
    count: int = 8,
    skill_id: str | None = None,
    rng: random.Random | None = None,
) -> list[Skill]:
    """Choose skills without crossing the primary/GCSE pathway boundary."""
    rng = rng or random.Random()
    settings = child.settings
    today = date.today()

    if mode == "skill" and skill_id:
        skill = get_skill(skill_id)
        if skill and skill_is_eligible(child, skill, subject):
            return [skill] * count
        # A forged or stale direct skill request must not fall through into a
        # different curriculum or tier.
        return []

    learner_is_gcse = pathways.is_gcse(settings)
    if learner_is_gcse:
        if subject not in (None, "gcse_maths"):
            return []
        candidates = available_skills("gcse_maths", tier=settings.gcse_tier)
        year_weights = {0: 1}
    else:
        if subject == "gcse_maths":
            return []
        years = years_for_mode(mode, settings)
        enabled_subjects = set(pathways.subject_ids(settings))
        if subject and subject not in enabled_subjects:
            return []
        candidates = available_skills(subject, years)
        if subject is None:
            candidates = [skill for skill in candidates if skill.subject in enabled_subjects]
        # Never fall back to a different Primary year. A missing Year 4–6
        # content set must fail clearly rather than silently serving Year 1–3.
        if not candidates:
            return []
        year_weights = settings.year_weights()

    progress = progress_map(child.id)

    if mode == "focus":
        weak = [
            skill
            for skill in candidates
            if (row := progress.get(skill.id))
            and row.attempts >= 2
            and row.mastery < 0.6
        ]
        if len(weak) >= 3:
            candidates = weak

    chosen: list[Skill] = []

    # Focus skills get reserved slots rather than only a bigger weight. Only
    # ids already in the eligible candidate set can be reserved.
    focus_ids = list(settings.focus_skills or [])
    if focus_ids and mode != "skill":
        by_id = {skill.id: skill for skill in candidates}
        eligible = [by_id[sid] for sid in focus_ids if sid in by_id]
        rng.shuffle(eligible)
        reserved = min(len(eligible), max(1, count // 4))
        chosen.extend(eligible[:reserved])

    already = {skill.id for skill in chosen}
    remaining = [skill for skill in candidates if skill.id not in already]
    weights = [
        score_skill(skill, progress.get(skill.id), settings, year_weights, today)
        for skill in remaining
    ]
    pool = list(zip(remaining, weights, strict=True))

    while len(chosen) < count and pool:
        total = sum(weight for _, weight in pool)
        if total <= 0:
            break
        target = rng.random() * total
        running = 0.0
        for index, (skill, weight) in enumerate(pool):
            running += weight
            if running >= target:
                chosen.append(skill)
                pool.pop(index)
                break
        else:  # pragma: no cover - float rounding safety net
            skill, _ = pool.pop()
            chosen.append(skill)

    # Short on distinct skills? Cycle round again rather than a shorter quest.
    if len(chosen) < count and chosen:
        index = 0
        while len(chosen) < count:
            chosen.append(chosen[index % len(chosen)])
            index += 1

    chosen = chosen[:count]
    rng.shuffle(chosen)
    return chosen


# ---------------------------------------------------------------------------
# Suggestions shown on the child's home screen
# ---------------------------------------------------------------------------


def due_count(child_id: int, include_gcse: bool | None = None) -> int:
    child = db.session.get(Child, child_id)
    if child is None:
        return 0
    rows = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id,
            SkillProgress.due_on <= date.today(),
            SkillProgress.attempts > 0,
        )
    ).scalars().all()
    active_ids = pathways.active_skill_ids(child.settings)
    return sum(1 for row in rows if row.skill_id in active_ids)


def weak_skills(
    child_id: int, limit: int = 6, include_gcse: bool | None = None
) -> list[tuple[Skill, SkillProgress]]:
    """Skills the child is finding hardest, worst first."""
    child = db.session.get(Child, child_id)
    if child is None:
        return []
    rows = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id, SkillProgress.attempts >= 2
        )
    ).scalars().all()
    active_ids = pathways.active_skill_ids(child.settings)
    pairs = []
    for row in rows:
        skill = get_skill(row.skill_id)
        if skill and row.skill_id in active_ids and row.mastery < 0.7:
            pairs.append((skill, row))
    pairs.sort(key=lambda pair: (pair[1].mastery, -pair[1].attempts))
    return pairs[:limit]


def strong_skills(
    child_id: int, limit: int = 6, include_gcse: bool | None = None
) -> list[tuple[Skill, SkillProgress]]:
    child = db.session.get(Child, child_id)
    if child is None:
        return []
    rows = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id,
            SkillProgress.attempts >= 3,
            SkillProgress.mastery >= 0.85,
        )
    ).scalars().all()
    active_ids = pathways.active_skill_ids(child.settings)
    pairs = []
    for row in rows:
        skill = get_skill(row.skill_id)
        if skill and row.skill_id in active_ids:
            pairs.append((skill, row))
    pairs.sort(key=lambda pair: (-pair[1].mastery, -pair[1].attempts))
    return pairs[:limit]
