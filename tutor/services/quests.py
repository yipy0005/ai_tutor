"""Building and running a quest.

A quest is a short, finite burst of practice — 6 to 10 questions, three to five
minutes. Finite matters: the child can see the last dot from the first question,
which is what makes a short attention span work *with* the app rather than
against it.

All the questions are generated up front and stored in the database, so:

* the browser never sees an answer before the child has committed to one,
* a parent can read back the exact wording of anything their child was asked,
* refreshing the page mid-quest loses nothing.
"""

from __future__ import annotations

import random
from datetime import date, datetime

from sqlalchemy import func, select

from ..content import SUBJECTS, check_answer, draw_question, get_skill, split_question
from ..extensions import db
from ..models import Child, DailyActivity, Quest, QuestQuestion
from . import rewards, scheduler

MIN_QUEST = 4
MAX_QUEST = 15


# ---------------------------------------------------------------------------
# Daily allowance
# ---------------------------------------------------------------------------


def today_activity(child: Child, create: bool = False) -> DailyActivity | None:
    row = db.session.execute(
        select(DailyActivity).where(
            DailyActivity.child_id == child.id, DailyActivity.on_date == date.today()
        )
    ).scalar_one_or_none()
    if row is None and create:
        row = DailyActivity(child_id=child.id, on_date=date.today())
        db.session.add(row)
        db.session.flush()
    return row


def seconds_used_today(child: Child) -> int:
    row = today_activity(child)
    return row.seconds if row else 0


def allowance(child: Child) -> dict:
    """How much practice time is left today, and whether the app is open."""
    settings = child.settings
    limit_minutes = max(0, settings.daily_limit_minutes or 0)
    used = seconds_used_today(child)
    row = today_activity(child)

    left = None
    if limit_minutes:
        left = max(0, limit_minutes * 60 - used)

    within_hours = settings.within_allowed_hours()
    return {
        "limit_minutes": limit_minutes,
        "used_seconds": used,
        "used_minutes": round(used / 60),
        "seconds_left": left,
        "minutes_left": None if left is None else max(0, round(left / 60)),
        "out_of_time": bool(limit_minutes) and (left is not None and left <= 0),
        "within_hours": within_hours,
        "quests_today": row.quests if row else 0,
        "questions_today": row.questions if row else 0,
        "daily_quest_goal": settings.daily_quest_goal or 0,
        "allowed_from": settings.allowed_from_hour,
        "allowed_to": settings.allowed_to_hour,
    }


def blocked_reason(child: Child) -> str | None:
    state = allowance(child)
    if not state["within_hours"]:
        return (
            f"The app is open between {state['allowed_from']}:00 and "
            f"{state['allowed_to']}:00. See you then!"
        )
    if state["out_of_time"]:
        return (
            f"You've done your {state['limit_minutes']} minutes for today. "
            "Great work — come back tomorrow!"
        )
    return None


# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------

TITLES = {
    ("maths", "mixed"): "Maths Mix",
    ("maths", "revision"): "Maths Recap",
    ("maths", "ahead"): "Year 3 Maths",
    ("maths", "focus"): "Tricky Maths",
    ("english", "mixed"): "English Mix",
    ("english", "revision"): "English Recap",
    ("english", "ahead"): "Year 3 English",
    ("english", "focus"): "Tricky English",
    ("science", "mixed"): "Science Mix",
    ("science", "revision"): "Science Recap",
    ("science", "ahead"): "Year 3 Science",
    ("science", "focus"): "Tricky Science",
}


def quest_title(subject: str | None, mode: str, skill_id: str | None = None) -> str:
    if mode == "skill" and skill_id:
        skill = get_skill(skill_id)
        if skill:
            return skill.name
    if subject is None:
        return {"revision": "Big Recap", "ahead": "Year 3 Challenge",
                "focus": "Tricky Bits"}.get(mode, "Daily Mix")
    return TITLES.get((subject, mode), SUBJECTS[subject].name)


# ---------------------------------------------------------------------------
# Starting a quest
# ---------------------------------------------------------------------------


def start_quest(
    child: Child,
    subject: str | None = None,
    mode: str = "mixed",
    count: int | None = None,
    skill_id: str | None = None,
    rng: random.Random | None = None,
) -> Quest:
    rng = rng or random.Random()
    settings = child.settings
    target = count or settings.quest_length or 8
    target = max(MIN_QUEST, min(MAX_QUEST, int(target)))

    skills = scheduler.pick_skills(
        child, subject, mode=mode, count=target, skill_id=skill_id, rng=rng
    )
    if not skills:
        raise ValueError("No skills are available with the current settings.")

    quest = Quest(
        child_id=child.id,
        subject=subject or "mixed",
        mode=mode,
        skill_id=skill_id,
        title=quest_title(subject, mode, skill_id),
        target_count=len(skills),
    )
    db.session.add(quest)
    db.session.flush()

    progress = scheduler.progress_map(child.id)
    used_keys: set[str] = set()

    for position, skill in enumerate(skills):
        level = scheduler.level_for(progress.get(skill.id), settings)
        question = draw_question(skill.id, rng, level=level, avoid=used_keys)
        used_keys.add(question.get("item_key", ""))
        payload, solution = split_question(question)
        db.session.add(
            QuestQuestion(
                quest_id=quest.id,
                position=position,
                skill_id=skill.id,
                kind=question.get("kind", "choice"),
                difficulty_level=level,
                payload=payload,
                solution=solution,
            )
        )

    db.session.commit()
    return quest


def get_quest(child: Child, quest_id: int) -> Quest | None:
    quest = db.session.get(Quest, quest_id)
    if quest is None or quest.child_id != child.id:
        return None
    return quest


def quest_payload(quest: Quest, child: Child) -> dict:
    """Everything the quest player needs, with no answers in it."""
    settings = child.settings
    questions = [q.public() for q in quest.questions]
    return {
        "id": quest.id,
        "title": quest.title,
        "subject": quest.subject,
        "mode": quest.mode,
        "total": len(questions),
        "answered": quest.answered_count,
        "correct": quest.correct_count,
        "finished": quest.is_finished,
        "questions": questions,
        "options": {
            "allow_hints": settings.allow_hints,
            "second_chance": settings.second_chance,
            "show_explanations": settings.show_explanations,
            "sound": settings.sound_enabled,
            "animations": settings.animations_enabled,
            "read_aloud": settings.read_aloud,
            "read_aloud_auto": settings.read_aloud_auto,
            "show_timer": settings.show_timer,
            "break_after_minutes": settings.break_after_minutes,
        },
    }


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------


def _bump_activity(child: Child, **deltas: int) -> None:
    row = today_activity(child, create=True)
    for field, amount in deltas.items():
        setattr(row, field, (getattr(row, field) or 0) + amount)


def submit_answer(
    child: Child,
    quest: Quest,
    question_id: int,
    given: str,
    seconds: int = 0,
    used_hint: bool = False,
    rng: random.Random | None = None,
) -> dict:
    """Mark one answer and update every counter that depends on it."""
    rng = rng or random.Random()
    question = db.session.get(QuestQuestion, question_id)
    if question is None or question.quest_id != quest.id:
        return {"error": "That question is not part of this quest."}
    if question.is_correct is not None:
        return {"error": "That question has already been answered."}

    settings = child.settings
    question.tries += 1
    question.seconds += max(0, min(int(seconds or 0), 600))
    if used_hint:
        question.used_hint = True

    correct = check_answer(given, question.solution or {}, question.kind)

    # One gentle second chance, if a parent has left it on.
    if not correct and question.tries == 1 and settings.second_chance:
        db.session.commit()
        return {
            "status": "retry",
            "message": rng.choice(rewards.CHEERS_RETRY),
            "tries": question.tries,
            "hint": (question.payload or {}).get("hint", "") if settings.allow_hints else "",
        }

    # Finalise.
    question.given_answer = str(given)[:400]
    question.is_correct = correct
    question.answered_at = datetime.now()

    progress = scheduler.get_or_create_progress(child.id, question.skill_id)
    progress.register(correct, question.seconds)

    quest.answered_count += 1
    quest.correct_count += 1 if correct else 0
    quest.seconds += question.seconds

    xp = rewards.xp_for_answer(correct, question.tries)
    coins = rewards.COINS_PER_CORRECT if correct else 0
    child.xp += xp
    child.coins += coins

    first_today = rewards.touch_streak(child)
    _bump_activity(
        child,
        seconds=question.seconds,
        questions=1,
        correct=1 if correct else 0,
        xp=xp,
    )
    db.session.commit()

    solution = question.solution or {}
    return {
        "status": "correct" if correct else "wrong",
        "correct": correct,
        "answer": solution.get("answer", ""),
        "explain": solution.get("explain", "") if settings.show_explanations else "",
        "message": rng.choice(rewards.CHEERS_CORRECT if correct else rewards.CHEERS_WRONG),
        "xp": xp,
        "coins": coins,
        "tries": question.tries,
        "answered": quest.answered_count,
        "total": len(quest.questions),
        "quest_correct": quest.correct_count,
        "child": {"xp": child.xp, "coins": child.coins, "level": child.level,
                  "level_pct": child.level_progress_pct, "streak": child.streak_days},
        "first_today": first_today,
    }


def use_hint(child: Child, quest: Quest, question_id: int) -> dict:
    question = db.session.get(QuestQuestion, question_id)
    if question is None or question.quest_id != quest.id:
        return {"error": "Unknown question."}
    if not child.settings.allow_hints:
        return {"hint": ""}
    question.used_hint = True
    db.session.commit()
    return {"hint": (question.payload or {}).get("hint", "")}


# ---------------------------------------------------------------------------
# Finishing
# ---------------------------------------------------------------------------


def finish_quest(child: Child, quest: Quest, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    if quest.is_finished:
        return quest_summary(child, quest, [], rng)

    answered = quest.answered_count
    stars = rewards.stars_for(quest.correct_count, answered) if answered else 0
    bonus_xp = (rewards.XP_QUEST_BONUS + stars * rewards.XP_PER_STAR) if answered else 0
    bonus_coins = (rewards.COINS_QUEST_BONUS + stars * rewards.COINS_PER_STAR) if answered else 0

    quest.stars = stars
    quest.xp_earned = bonus_xp
    quest.coins_earned = bonus_coins
    quest.finished_at = datetime.now()

    child.xp += bonus_xp
    child.coins += bonus_coins

    rewards.touch_streak(child)
    _bump_activity(child, quests=1, xp=bonus_xp)
    db.session.flush()

    new_badges = rewards.evaluate_badges(child)
    db.session.commit()
    return quest_summary(child, quest, new_badges, rng)


def quest_summary(
    child: Child, quest: Quest, new_badges: list, rng: random.Random | None = None
) -> dict:
    rng = rng or random.Random()
    answered = quest.answered_count or 0
    review = []
    for question in quest.questions:
        if question.is_correct is None:
            continue
        skill = get_skill(question.skill_id)
        review.append(
            {
                "position": question.position + 1,
                "prompt": (question.payload or {}).get("prompt", ""),
                "given": question.given_answer,
                "answer": (question.solution or {}).get("answer", ""),
                "explain": (question.solution or {}).get("explain", ""),
                "correct": bool(question.is_correct),
                "skill": skill.name if skill else question.skill_id,
                "year": skill.year if skill else None,
            }
        )

    return {
        "quest_id": quest.id,
        "title": quest.title,
        "answered": answered,
        "correct": quest.correct_count,
        "accuracy": quest.accuracy_pct,
        "stars": quest.stars,
        "xp": quest.xp_earned,
        "coins": quest.coins_earned,
        "minutes": quest.minutes,
        "message": rng.choice(rewards.QUEST_END.get(quest.stars, ["Well done!"])),
        "badges": [
            {"id": b.id, "name": b.name, "emoji": b.emoji, "description": b.description}
            for b in new_badges
        ],
        "child": {
            "xp": child.xp,
            "coins": child.coins,
            "level": child.level,
            "level_pct": child.level_progress_pct,
            "streak": child.streak_days,
        },
        "review": review,
    }


def abandon_quest(child: Child, quest: Quest) -> None:
    """A child wandered off. Keep any answers, drop the empty shell."""
    if quest.is_finished:
        return
    if quest.answered_count == 0:
        db.session.delete(quest)
    else:
        quest.finished_at = datetime.now()
        quest.stars = rewards.stars_for(quest.correct_count, quest.answered_count)
        _bump_activity(child, quests=1)
    db.session.commit()


def open_quest(child: Child) -> Quest | None:
    """An unfinished quest worth offering to carry on with.

    Only today's counts. Being invited to resume something abandoned last
    Tuesday is confusing, and it would crowd out the main "start a quest"
    action on the home screen.
    """
    return db.session.execute(
        select(Quest)
        .where(
            Quest.child_id == child.id,
            Quest.finished_at.is_(None),
            Quest.started_at >= datetime.combine(date.today(), datetime.min.time()),
        )
        .order_by(Quest.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def recent_quests(child_id: int, limit: int = 10) -> list[Quest]:
    return list(
        db.session.execute(
            select(Quest)
            .where(Quest.child_id == child_id, Quest.finished_at.is_not(None))
            .order_by(Quest.finished_at.desc())
            .limit(limit)
        ).scalars().all()
    )


def lifetime_totals(child_id: int) -> dict:
    row = db.session.execute(
        select(
            func.count(Quest.id),
            func.coalesce(func.sum(Quest.answered_count), 0),
            func.coalesce(func.sum(Quest.correct_count), 0),
            func.coalesce(func.sum(Quest.seconds), 0),
            func.coalesce(func.sum(Quest.stars), 0),
        ).where(Quest.child_id == child_id, Quest.finished_at.is_not(None))
    ).one()
    quests, answered, correct, seconds, stars = row
    return {
        "quests": int(quests or 0),
        "questions": int(answered or 0),
        "correct": int(correct or 0),
        "accuracy": round((correct or 0) / answered * 100) if answered else 0,
        "minutes": round((seconds or 0) / 60),
        "stars": int(stars or 0),
    }
