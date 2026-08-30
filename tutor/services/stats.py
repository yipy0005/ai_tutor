"""Analytics for the parent dashboard.

Everything is computed from the same rows the child's app writes, so the numbers
a parent sees are the real thing rather than a separate tally that can drift.
Charts are plain SVG built from these figures — no chart library, no CDN, works
offline on the kitchen iPad.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select

from ..content import (
    GCSE_TIER_LABELS,
    SUBJECT_ORDER,
    SUBJECTS,
    YEAR_LABELS,
    get_skill,
    topic_tree,
)
from ..extensions import db
from ..models import Child, DailyActivity, Quest, SkillProgress
from . import assessments, great, pathways, rewards, scheduler
from . import quests as quest_service

MASTERY_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# Headline numbers
# ---------------------------------------------------------------------------


def _activity_rows(child_id: int, since: date) -> list[DailyActivity]:
    return list(
        db.session.execute(
            select(DailyActivity)
            .where(DailyActivity.child_id == child_id, DailyActivity.on_date >= since)
            .order_by(DailyActivity.on_date)
        ).scalars().all()
    )


def pending_great_interviews(child: Child) -> list[dict]:
    """Return submitted GREAT interviews still waiting for parent scores."""
    path_quests = db.session.execute(
        select(Quest).where(Quest.child_id == child.id)
    ).scalars().all()
    pending = []
    for quest in path_quests:
        if not quest_service.quest_matches_path(child, quest):
            continue
        for question in quest.questions:
            diagnostic = great.diagnostic_from_solution(question.solution)
            if diagnostic is not None and diagnostic.get("scores") is None:
                pending.append(
                    {
                        "quest_id": quest.id,
                        "question_id": question.id,
                        "position": question.position + 1,
                        "quest_title": quest.title,
                    }
                )
    return pending


def overview(child: Child) -> dict:
    today = date.today()
    week_start = today - timedelta(days=6)

    rows = _activity_rows(child.id, week_start)
    today_row = next((r for r in rows if r.on_date == today), None)

    week_seconds = sum(r.seconds for r in rows)
    week_questions = sum(r.questions for r in rows)
    week_correct = sum(r.correct for r in rows)
    week_quests = sum(r.quests for r in rows)

    settings = child.settings
    totals = quest_service.lifetime_totals(child.id)
    progress_rows = db.session.execute(
        select(SkillProgress).where(SkillProgress.child_id == child.id)
    ).scalars().all()

    active_skills = pathways.active_skills(settings)
    active_ids = {skill.id for skill in active_skills}
    active_rows = [row for row in progress_rows if row.skill_id in active_ids]
    touched = [p for p in active_rows if p.attempts > 0]
    mastered = [p for p in touched if p.mastery >= MASTERY_THRESHOLD and p.attempts >= 4]
    struggling = [p for p in touched if p.attempts >= 3 and p.mastery < 0.4]
    active_gcse = pathways.is_gcse(settings)

    weekly_goal = settings.weekly_quest_goal or 0

    path_quests = db.session.execute(
        select(Quest).where(Quest.child_id == child.id)
    ).scalars().all()
    great_rows = [
        (quest, question)
        for quest in path_quests
        if quest_service.quest_matches_path(child, quest)
        for question in quest.questions
    ]
    great_assessments = []
    great_diagnostics = []
    pending_great_interviews = []
    answered_for_great = 0
    for quest, question in great_rows:
        if question.is_correct is not None:
            answered_for_great += 1
        assessment = great.assessment_from_solution(question.solution)
        if assessment is not None:
            great_assessments.append(assessment)
        diagnostic = great.diagnostic_from_solution(question.solution)
        if diagnostic is not None:
            great_diagnostics.append(diagnostic)
            if diagnostic.get("scores") is None:
                pending_great_interviews.append(
                    {
                        "quest_id": quest.id,
                        "question_id": question.id,
                        "position": question.position + 1,
                        "quest_title": quest.title,
                    }
                )
    great_report = great.aggregate(great_assessments)
    great_report.update(
        {
            "answered": answered_for_great,
            "unassessed": max(0, answered_for_great - great_report["assessed"]),
            "coverage_pct": (
                round(great_report["assessed"] / answered_for_great * 100)
                if answered_for_great
                else 0
            ),
        }
    )
    great_diagnostic_report = great.aggregate_diagnostics(great_diagnostics)
    great_diagnostic_report.update(
        {
            "enabled": bool(settings.great_diagnostic),
            "pending_interviews": pending_great_interviews,
            "answered": answered_for_great,
            "not_submitted": max(
                0, answered_for_great - great_diagnostic_report["submitted"]
            ),
            "coverage_pct": (
                round(great_diagnostic_report["reviewed"] / answered_for_great * 100)
                if answered_for_great
                else 0
            ),
            "submission_pct": (
                round(great_diagnostic_report["submitted"] / answered_for_great * 100)
                if answered_for_great
                else 0
            ),
        }
    )

    return {
        "today_minutes": round((today_row.seconds if today_row else 0) / 60),
        "today_questions": today_row.questions if today_row else 0,
        "today_quests": today_row.quests if today_row else 0,
        "today_accuracy": today_row.accuracy_pct if today_row else 0,
        "week_minutes": round(week_seconds / 60),
        "week_questions": week_questions,
        "week_quests": week_quests,
        "week_accuracy": round(week_correct / week_questions * 100) if week_questions else 0,
        "week_goal": weekly_goal,
        "week_goal_pct": min(100, round(week_quests / weekly_goal * 100)) if weekly_goal else 0,
        "streak": child.streak_days,
        "best_streak": child.best_streak,
        "level": child.level,
        "xp": child.xp,
        "coins": child.coins,
        "badges": len(rewards.visible_badge_awards(child)),
        "lifetime": totals,
        "pathway": "gcse_maths" if active_gcse else "primary",
        "pathway_label": (
            f"GCSE Maths · {GCSE_TIER_LABELS.get(settings.gcse_tier, settings.gcse_tier)}"
            if active_gcse
            else "Primary Years 1–6"
        ),
        "skills_total": len(active_skills),
        "skills_touched": len(touched),
        "skills_mastered": len(mastered),
        "skills_struggling": len(struggling),
        "coverage_pct": round(len(touched) / len(active_skills) * 100) if active_skills else 0,
        "mastered_pct": round(len(mastered) / len(active_skills) * 100) if active_skills else 0,
        "gcse": {
            "enabled": active_gcse,
            "tier": GCSE_TIER_LABELS.get(settings.gcse_tier, ""),
            "skills_total": len(active_skills) if active_gcse else 0,
            "skills_touched": len(touched) if active_gcse else 0,
            "skills_mastered": len(mastered) if active_gcse else 0,
            "coverage_pct": round(len(touched) / len(active_skills) * 100)
            if active_gcse and active_skills
            else 0,
            "mastered_pct": round(len(mastered) / len(active_skills) * 100)
            if active_gcse and active_skills
            else 0,
        },
        "due_now": scheduler.due_count(child.id),
        "great": great_report,
        "great_diagnostic": great_diagnostic_report,
    }


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------


def daily_series(child_id: int, days: int = 28) -> list[dict]:
    """One entry per day, oldest first, including days with no activity."""
    start = date.today() - timedelta(days=days - 1)
    rows = {r.on_date: r for r in _activity_rows(child_id, start)}
    out = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = rows.get(day)
        out.append(
            {
                "date": day,
                "label": day.strftime("%d %b"),
                "short": day.strftime("%a")[0],
                "minutes": round((row.seconds if row else 0) / 60),
                "seconds": row.seconds if row else 0,
                "questions": row.questions if row else 0,
                "correct": row.correct if row else 0,
                "quests": row.quests if row else 0,
                "accuracy": row.accuracy_pct if row else 0,
                "active": bool(row and row.questions),
            }
        )
    return out


def minutes_chart(child_id: int, days: int = 14) -> dict:
    """Bar chart geometry for minutes practised per day."""
    series = daily_series(child_id, days)
    peak = max([d["minutes"] for d in series] + [10])
    bars = []
    for index, day in enumerate(series):
        bars.append(
            {
                "label": day["label"],
                "short": day["short"],
                "value": day["minutes"],
                "pct": round(day["minutes"] / peak * 100) if peak else 0,
                "index": index,
                "active": day["active"],
            }
        )
    return {"bars": bars, "peak": peak, "days": days}


def accuracy_chart(child_id: int, days: int = 14, width: int = 640, height: int = 160) -> dict:
    """Line chart geometry (an SVG polyline) for daily accuracy."""
    series = daily_series(child_id, days)
    active = [d for d in series if d["questions"] > 0]
    if len(active) < 2:
        return {"points": "", "dots": [], "has_data": False, "width": width, "height": height}

    pad = 18
    span = max(1, len(series) - 1)
    dots = []
    for index, day in enumerate(series):
        if day["questions"] == 0:
            continue
        x = pad + (width - 2 * pad) * index / span
        y = height - pad - (height - 2 * pad) * (day["accuracy"] / 100)
        dots.append(
            {"x": round(x, 1), "y": round(y, 1), "value": day["accuracy"], "label": day["label"]}
        )
    points = " ".join(f"{d['x']},{d['y']}" for d in dots)
    return {
        "points": points,
        "dots": dots,
        "has_data": True,
        "width": width,
        "height": height,
        "pad": pad,
    }


def heatmap(child_id: int, weeks: int = 10) -> dict:
    """A GitHub-style grid: columns are weeks, rows are Monday..Sunday."""
    today = date.today()
    end = today + timedelta(days=(6 - today.weekday()))
    start = end - timedelta(days=weeks * 7 - 1)
    rows = {r.on_date: r for r in _activity_rows(child_id, start)}

    columns: list[list[dict]] = []
    for week in range(weeks):
        column = []
        for weekday in range(7):
            day = start + timedelta(days=week * 7 + weekday)
            row = rows.get(day)
            minutes = round((row.seconds if row else 0) / 60)
            if not row or row.questions == 0:
                level = 0
            elif minutes < 5:
                level = 1
            elif minutes < 12:
                level = 2
            elif minutes < 25:
                level = 3
            else:
                level = 4
            column.append(
                {
                    "date": day,
                    "label": day.strftime("%a %d %b"),
                    "minutes": minutes,
                    "questions": row.questions if row else 0,
                    "level": level,
                    "future": day > today,
                }
            )
        columns.append(column)
    return {"columns": columns, "weekdays": ["M", "T", "W", "T", "F", "S", "S"]}


# ---------------------------------------------------------------------------
# Curriculum breakdowns
# ---------------------------------------------------------------------------


def _progress_index(child_id: int) -> dict[str, SkillProgress]:
    return scheduler.progress_map(child_id)


def subject_breakdown(child_id: int) -> list[dict]:
    progress = _progress_index(child_id)
    child = db.session.get(Child, child_id)
    subject_ids = pathways.subject_ids(child.settings) if child else list(SUBJECT_ORDER)

    out = []
    for subject_id in subject_ids:
        subject = SUBJECTS[subject_id]
        skills = pathways.active_skills(child.settings, subject_id) if child else []
        rows = [
            progress[skill.id]
            for skill in skills
            if skill.id in progress and progress[skill.id].attempts
        ]
        attempts = sum(row.attempts for row in rows)
        correct = sum(row.correct for row in rows)
        mastered = [
            row
            for row in rows
            if row.mastery >= MASTERY_THRESHOLD and row.attempts >= 4
        ]
        out.append(
            {
                "id": subject_id,
                "name": subject.name,
                "emoji": subject.emoji,
                "colour": subject.colour,
                "skills": len(skills),
                "touched": len(rows),
                "mastered": len(mastered),
                "attempts": attempts,
                "correct": correct,
                "accuracy": round(correct / attempts * 100) if attempts else 0,
                "coverage_pct": round(len(rows) / len(skills) * 100) if skills else 0,
                "mastered_pct": round(len(mastered) / len(skills) * 100) if skills else 0,
                "minutes": round(sum(row.total_seconds for row in rows) / 60),
                "tier": (
                    GCSE_TIER_LABELS.get(child.settings.gcse_tier)
                    if subject_id == "gcse_maths" and child
                    else None
                ),
            }
        )
    return out


def year_breakdown(child_id: int) -> list[dict]:
    child = db.session.get(Child, child_id)
    if child is None or pathways.is_gcse(child.settings):
        return []
    progress = _progress_index(child_id)
    out = []
    for year in pathways.year_ids(child.settings):
        skills = [skill for skill in pathways.active_skills(child.settings) if skill.year == year]
        rows = [
            progress[skill.id]
            for skill in skills
            if skill.id in progress and progress[skill.id].attempts
        ]
        attempts = sum(row.attempts for row in rows)
        correct = sum(row.correct for row in rows)
        mastered = [
            row for row in rows
            if row.mastery >= MASTERY_THRESHOLD and row.attempts >= 4
        ]
        out.append(
            {
                "year": year,
                "label": YEAR_LABELS[year],
                "skills": len(skills),
                "touched": len(rows),
                "mastered": len(mastered),
                "attempts": attempts,
                "accuracy": round(correct / attempts * 100) if attempts else 0,
                "coverage_pct": round(len(rows) / len(skills) * 100) if skills else 0,
                "mastered_pct": round(len(mastered) / len(skills) * 100) if skills else 0,
            }
        )
    return out


def skill_matrix(
    child_id: int, subject: str, tier: str | None = None
) -> list[dict]:
    """Topic grid scoped to a primary subject or selected GCSE tier."""
    child = db.session.get(Child, child_id)
    if child is None or subject not in pathways.subject_ids(child.settings):
        return []
    progress = _progress_index(child_id)
    groups = []
    for year, topic, skills in topic_tree(subject, tier):
        if subject != "gcse_maths" and year not in pathways.year_ids(child.settings):
            continue
        entries = []
        for skill in skills:
            row = progress.get(skill.id)
            entries.append(
                {
                    "skill": skill,
                    "progress": row,
                    "attempts": row.attempts if row else 0,
                    "accuracy": row.accuracy_pct if row else 0,
                    "mastery": row.mastery_pct if row else 0,
                    "stage": row.stage if row else "not started",
                    "due_on": row.due_on if row else None,
                    "last_seen": row.last_seen_at if row else None,
                }
            )
        groups.append(
            {
                "year": year,
                "year_label": skills[0].year_label if skills else YEAR_LABELS.get(year, ""),
                "pathway_label": skills[0].pathway_label if skills else "",
                "topic": topic,
                "entries": entries,
                "mastered": sum(
                    1 for entry in entries if entry["mastery"] >= MASTERY_THRESHOLD * 100
                ),
                "touched": sum(1 for entry in entries if entry["attempts"] > 0),
                "count": len(entries),
            }
        )
    return groups


def attention_list(child_id: int, limit: int = 8) -> list[dict]:
    """Skills worth a parent's attention, most concerning first."""
    progress = _progress_index(child_id)
    child = db.session.get(Child, child_id)
    active_ids = {skill.id for skill in pathways.active_skills(child.settings)} if child else set()
    items = []
    for skill_id, row in progress.items():
        if skill_id not in active_ids:
            continue
        skill = get_skill(skill_id)
        if skill is None or row.attempts < 2:
            continue
        if row.mastery >= 0.6:
            continue
        items.append(
            {
                "skill": skill,
                "attempts": row.attempts,
                "accuracy": row.accuracy_pct,
                "mastery": row.mastery_pct,
                "stage": row.stage,
                "last_seen": row.last_seen_at,
                "nc_ref": skill.nc_ref,
            }
        )
    items.sort(key=lambda item: (item["mastery"], -item["attempts"]))
    return items[:limit]


def wins_list(child_id: int, limit: int = 8) -> list[dict]:
    progress = _progress_index(child_id)
    child = db.session.get(Child, child_id)
    active_ids = {skill.id for skill in pathways.active_skills(child.settings)} if child else set()
    items = []
    for skill_id, row in progress.items():
        if skill_id not in active_ids:
            continue
        skill = get_skill(skill_id)
        if skill is None or row.attempts < 3 or row.mastery < MASTERY_THRESHOLD:
            continue
        items.append(
            {
                "skill": skill,
                "attempts": row.attempts,
                "accuracy": row.accuracy_pct,
                "mastery": row.mastery_pct,
                "last_seen": row.last_seen_at,
            }
        )
    items.sort(key=lambda item: (-item["mastery"], -item["attempts"]))
    return items[:limit]


# ---------------------------------------------------------------------------
# Question-level detail
# ---------------------------------------------------------------------------


def quest_detail(child_id: int, quest_id: int) -> dict | None:
    child = db.session.get(Child, child_id)
    quest = db.session.get(Quest, quest_id)
    if (
        child is None
        or quest is None
        or quest.child_id != child_id
        or not quest_service.quest_matches_path(child, quest)
    ):
        return None
    rows = []
    for question in quest.questions:
        skill = get_skill(question.skill_id)
        rows.append(
            {
                "id": question.id,
                "position": question.position + 1,
                "skill": skill,
                "kind": question.kind,
                "difficulty_level": question.difficulty_level if question.difficulty_level in (0, 1, 2) else 1,
                "difficulty_label": {0: "Gentle", 1: "Normal", 2: "Challenge"}.get(question.difficulty_level, "Normal"),
                "prompt": (question.payload or {}).get("prompt", ""),
                "prompt_sub": (question.payload or {}).get("prompt_sub", ""),
                "choices": (question.payload or {}).get("choices", []),
                "given": question.given_answer,
                "answer": (question.solution or {}).get("answer", ""),
                "explain": (question.solution or {}).get("explain", ""),
                "correct": question.is_correct,
                "answered": question.is_answered,
                "pending": question.is_pending,
                "manual": assessments.is_manual(question.kind),
                "response": question.response_json,
                "score": question.score,
                "max_score": question.max_score,
                "assessment": question.assessment_json or {},
                "rubric": (question.solution or {}).get("assessment", {}),
                "response_spec": (question.payload or {}).get("response_spec", {}),
                "exam": (question.payload or {}).get("exam", {}),
                "tries": question.tries,
                "used_hint": question.used_hint,
                "seconds": question.seconds,
                "great": great.question_summary(question.solution),
                "great_diagnostic": great.diagnostic_summary(question.solution),
            }
        )
    return {"quest": quest, "rows": rows}


def recent_mistakes(child_id: int, limit: int = 12) -> list[dict]:
    child = db.session.get(Child, child_id)
    if child is None:
        return []
    quests_for_child = db.session.execute(
        select(Quest)
        .where(Quest.child_id == child_id)
        .order_by(Quest.finished_at.desc())
    ).scalars().all()
    rows = [
        question
        for quest in quests_for_child
        if quest_service.quest_matches_path(child, quest)
        for question in quest.questions
        if question.is_correct is False
    ]
    rows.sort(key=lambda question: question.answered_at or date.min, reverse=True)
    rows = rows[:limit]
    out = []
    for question in rows:
        skill = get_skill(question.skill_id)
        out.append(
            {
                "prompt": (question.payload or {}).get("prompt", ""),
                "given": question.given_answer,
                "answer": (question.solution or {}).get("answer", ""),
                "explain": (question.solution or {}).get("explain", ""),
                "skill": skill,
                "when": question.answered_at,
            }
        )
    return out


def subject_time_split(child_id: int) -> list[dict]:
    """Minutes spent per subject, for the little donut on the dashboard."""
    rows = db.session.execute(
        select(Quest.subject, func.coalesce(func.sum(Quest.seconds), 0))
        .where(Quest.child_id == child_id)
        .group_by(Quest.subject)
    ).all()
    child = db.session.get(Child, child_id)
    active_subjects = pathways.subject_ids(child.settings) if child else []
    allowed = set(active_subjects)
    if child and not pathways.is_gcse(child.settings):
        allowed.add("mixed")
    totals: dict[str, int] = defaultdict(int)
    for subject, seconds in rows:
        if subject in allowed:
            totals[subject] += int(seconds or 0)
    grand = sum(totals.values()) or 1
    subject_ids = list(active_subjects)
    out = []
    for subject_id in subject_ids + ["mixed"]:
        seconds = totals.get(subject_id, 0)
        if not seconds:
            continue
        subject = SUBJECTS.get(subject_id)
        out.append(
            {
                "id": subject_id,
                "name": subject.name if subject else "Mixed",
                "emoji": subject.emoji if subject else "🎲",
                "colour": subject.colour if subject else "grape",
                "minutes": round(seconds / 60),
                "pct": round(seconds / grand * 100),
            }
        )
    return out
