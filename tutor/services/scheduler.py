"""Deciding what to practise next.

Three ideas combine here:

1. **Spaced repetition.** Every skill sits in a Leitner box with a due date.
   Skills that are due get pushed to the front, which is what turns a summer of
   short sessions into retained Year 1 and 2 knowledge.
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

from ..content import ALL_SKILLS, Skill, bank_size, get_skill
from ..extensions import db
from ..models import Child, Settings, SkillProgress

MODES = {
    "mixed": "A bit of everything",
    "revision": "Year 1 and 2 revision",
    "ahead": "New Year 3 work",
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
    subject: str | None = None, years: list[int] | tuple[int, ...] | None = None
) -> list[Skill]:
    wanted_years = {int(y) for y in years} if years else None
    out = []
    for skill in ALL_SKILLS:
        if subject and skill.subject != subject:
            continue
        if wanted_years and skill.year not in wanted_years:
            continue
        if not is_playable(skill):
            continue
        out.append(skill)
    return out


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
    enabled = [int(y) for y in (settings.years_enabled or [1, 2, 3])]
    if mode == "revision":
        picked = [y for y in enabled if y in (1, 2)]
    elif mode == "ahead":
        picked = [y for y in enabled if y == 3]
    else:
        picked = enabled
    return picked or enabled or [3]


def pick_skills(
    child: Child,
    subject: str | None,
    mode: str = "mixed",
    count: int = 8,
    skill_id: str | None = None,
    rng: random.Random | None = None,
) -> list[Skill]:
    """Choose the skills a quest will cover, in the order they will be asked."""
    rng = rng or random.Random()
    settings = child.settings
    today = date.today()

    if mode == "skill" and skill_id:
        skill = get_skill(skill_id)
        if skill and is_playable(skill):
            return [skill] * count

    years = years_for_mode(mode, settings)
    candidates = available_skills(subject, years)

    if not candidates:  # a parent has filtered everything out
        candidates = available_skills(subject) or available_skills()
    if not candidates:
        return []

    progress = progress_map(child.id)

    if mode == "focus":
        weak = [
            s
            for s in candidates
            if (p := progress.get(s.id)) and p.attempts >= 2 and p.mastery < 0.6
        ]
        if len(weak) >= 3:
            candidates = weak

    year_weights = settings.year_weights()
    chosen: list[Skill] = []

    # Focus skills get reserved slots rather than only a bigger weight. If a
    # parent has deliberately starred something, it should reliably turn up in
    # the next quest, not "probably turn up eventually". A quarter of the quest
    # at most, so the rest of the curriculum still gets a look in.
    focus_ids = list(settings.focus_skills or [])
    if focus_ids and mode != "skill":
        by_id = {s.id: s for s in candidates}
        eligible = [by_id[sid] for sid in focus_ids if sid in by_id]
        rng.shuffle(eligible)
        reserved = min(len(eligible), max(1, count // 4))
        chosen.extend(eligible[:reserved])

    already = {s.id for s in chosen}
    remaining = [s for s in candidates if s.id not in already]
    weights = [
        score_skill(s, progress.get(s.id), settings, year_weights, today)
        for s in remaining
    ]

    pool = list(zip(remaining, weights, strict=True))

    while len(chosen) < count and pool:
        total = sum(w for _, w in pool)
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
        i = 0
        while len(chosen) < count:
            chosen.append(chosen[i % len(chosen)])
            i += 1

    chosen = chosen[:count]
    # Shuffle so the reserved focus skills are not always the opening questions.
    rng.shuffle(chosen)
    return chosen


# ---------------------------------------------------------------------------
# Suggestions shown on the child's home screen
# ---------------------------------------------------------------------------


def due_count(child_id: int) -> int:
    rows = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id,
            SkillProgress.due_on <= date.today(),
            SkillProgress.attempts > 0,
        )
    ).scalars().all()
    return len(rows)


def weak_skills(child_id: int, limit: int = 6) -> list[tuple[Skill, SkillProgress]]:
    """Skills the child is finding hardest, worst first."""
    rows = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id, SkillProgress.attempts >= 2
        )
    ).scalars().all()
    pairs = []
    for row in rows:
        skill = get_skill(row.skill_id)
        if skill and row.mastery < 0.7:
            pairs.append((skill, row))
    pairs.sort(key=lambda pair: (pair[1].mastery, -pair[1].attempts))
    return pairs[:limit]


def strong_skills(child_id: int, limit: int = 6) -> list[tuple[Skill, SkillProgress]]:
    rows = db.session.execute(
        select(SkillProgress).where(
            SkillProgress.child_id == child_id,
            SkillProgress.attempts >= 3,
            SkillProgress.mastery >= 0.85,
        )
    ).scalars().all()
    pairs = []
    for row in rows:
        skill = get_skill(row.skill_id)
        if skill:
            pairs.append((skill, row))
    pairs.sort(key=lambda pair: (-pair[1].mastery, -pair[1].attempts))
    return pairs[:limit]
