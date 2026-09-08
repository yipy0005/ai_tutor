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

from sqlalchemy import select

from ..content import (
    GCSE_TIER_LABELS,
    SUBJECTS,
    check_answer,
    draw_question,
    get_skill,
    split_question,
)
from ..extensions import db
from ..models import Child, DailyActivity, Quest, QuestQuestion
from . import assessments, great, pathways, rewards, scheduler

MIN_QUEST = 4
MAX_QUEST = 15


def record_great(quest: Quest, question_id: int, scores: dict) -> dict:
    """Persist one explicit GREAT reflection without changing quiz scoring."""
    question = db.session.get(QuestQuestion, question_id)
    if question is None or question.quest_id != quest.id:
        return {"error": "That question is not part of this quest."}
    if question.is_correct is None:
        return {"error": "Answer the question before recording a GREAT check-in."}

    try:
        question.solution = great.store_assessment(question.solution, scores)
    except ValueError as exc:
        return {"error": str(exc)}

    db.session.commit()
    return {"ok": True, "great": great.question_summary(question.solution)}


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
    ("maths", "ahead"): "Maths Challenge",
    ("maths", "focus"): "Tricky Maths",
    ("english", "mixed"): "English Mix",
    ("english", "revision"): "English Recap",
    ("english", "ahead"): "English Challenge",
    ("english", "focus"): "Tricky English",
    ("science", "mixed"): "Science Mix",
    ("science", "revision"): "Science Recap",
    ("science", "ahead"): "Science Challenge",
    ("science", "focus"): "Tricky Science",
    ("gcse_maths", "mixed"): "GCSE Maths",
    ("gcse_maths", "revision"): "GCSE Maths Practice",
    ("gcse_maths", "ahead"): "GCSE Maths Challenge",
    ("gcse_maths", "focus"): "GCSE Maths Focus",
}


def quest_title(
    subject: str | None,
    mode: str,
    skill_id: str | None = None,
    practice_profile: str = "standard",
) -> str:
    if mode == "skill" and skill_id:
        skill = get_skill(skill_id)
        if skill:
            label = scheduler.PRACTICE_PROFILES.get(practice_profile, {}).get("label")
            return f"{skill.name} · {label}" if label and practice_profile != "standard" else skill.name
    if subject is None:
        return {"revision": "Big Recap", "ahead": "Challenge Quest",
                "focus": "Tricky Bits"}.get(mode, "Daily Mix")
    return TITLES.get((subject, mode), SUBJECTS[subject].name)


# ---------------------------------------------------------------------------
# Starting a quest
# ---------------------------------------------------------------------------


def subject_for_path(child: Child, subject: str | None) -> str | None:
    """Normalize a request to the learner's active curriculum path."""
    if pathways.is_gcse(child.settings):
        if subject not in (None, "gcse_maths"):
            raise ValueError("This learner can only practise GCSE Maths.")
        return "gcse_maths"
    if subject == "gcse_maths":
        raise ValueError("GCSE Maths is only available on a GCSE learner profile.")
    return subject


def quest_matches_path(child: Child, quest: Quest) -> bool:
    """Reject quests outside the learner's current subjects, years or tier."""
    return pathways.quest_matches_path(
        child.settings,
        quest.subject,
        [question.skill_id for question in quest.questions],
    )


# ---------------------------------------------------------------------------
# Starting a quest
# ---------------------------------------------------------------------------


def start_quest(
    child: Child,
    subject: str | None = None,
    mode: str = "mixed",
    count: int | None = None,
    skill_id: str | None = None,
    practice_profile: str = "standard",
    related_skill_ids: list[str] | tuple[str, ...] | None = None,
    rng: random.Random | None = None,
) -> Quest:
    rng = rng or random.Random()
    settings = child.settings
    subject = subject_for_path(child, subject)
    target = count or settings.quest_length or 8
    target = max(MIN_QUEST, min(MAX_QUEST, int(target)))
    if practice_profile not in scheduler.PRACTICE_PROFILES:
        raise ValueError("Unknown practice profile.")

    skills = scheduler.pick_skills(
        child,
        subject,
        mode=mode,
        count=target,
        skill_id=skill_id,
        practice_profile=practice_profile,
        related_skill_ids=related_skill_ids,
        rng=rng,
    )
    if not skills:
        raise ValueError("No skills are available with the current settings.")

    quest = Quest(
        child_id=child.id,
        subject=subject or "mixed",
        mode=mode,
        practice_profile=practice_profile,
        skill_id=skill_id,
        title=quest_title(subject, mode, skill_id, practice_profile),
        target_count=len(skills),
    )
    db.session.add(quest)
    db.session.flush()

    progress = scheduler.progress_map(child.id)
    used_keys: set[str] = set()
    profile_level = scheduler.PRACTICE_PROFILES[practice_profile]["level"]

    for position, skill in enumerate(skills):
        level = scheduler.level_for(progress.get(skill.id), settings)
        if profile_level is not None:
            level = profile_level
        question = draw_question(
            skill.id,
            rng,
            level=level,
            avoid=used_keys,
            tier=settings.gcse_tier if skill.is_gcse else None,
            board=settings.gcse_board if skill.is_gcse else None,
            practice_profile=practice_profile,
        )
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


def successful_practice_days(child_id: int) -> dict[str, int]:
    """Count distinct days with a correct answer for each learner skill."""
    rows = db.session.execute(
        select(QuestQuestion.skill_id, QuestQuestion.answered_at).join(
            Quest, Quest.id == QuestQuestion.quest_id
        ).where(
            Quest.child_id == child_id,
            QuestQuestion.is_correct.is_(True),
            QuestQuestion.answered_at.is_not(None),
        )
    ).all()
    days: dict[str, set[date]] = {}
    for skill_id, answered_at in rows:
        if answered_at is not None:
            days.setdefault(skill_id, set()).add(answered_at.date())
    return {skill_id: len(review_days) for skill_id, review_days in days.items()}


def get_quest(child: Child, quest_id: int) -> Quest | None:
    quest = db.session.get(Quest, quest_id)
    if quest is None or quest.child_id != child.id or not quest_matches_path(child, quest):
        return None
    return quest


def quest_payload(quest: Quest, child: Child) -> dict:
    """Everything the quest player needs, with no answers in it."""
    settings = child.settings
    questions = [q.public() for q in quest.questions]
    payload = {
        "id": quest.id,
        "title": quest.title,
        "subject": quest.subject,
        "mode": quest.mode,
        "practice_profile": quest.practice_profile or "standard",
        "practice_label": scheduler.PRACTICE_PROFILES.get(
            quest.practice_profile or "standard", scheduler.PRACTICE_PROFILES["standard"]
        )["label"],
        "total": len(questions),
        "answered": quest.answered_count,
        "correct": quest.correct_count,
        "finished": quest.is_finished,
        "questions": questions,
        "options": {
            "allow_hints": settings.allow_hints,
            "second_chance": settings.second_chance,
            "show_explanations": settings.show_explanations,
            "great_diagnostic": settings.great_diagnostic,
            "sound": settings.sound_enabled,
            "animations": settings.animations_enabled,
            "read_aloud": settings.read_aloud,
            "read_aloud_auto": settings.read_aloud_auto,
            "show_timer": settings.show_timer,
            "break_after_minutes": settings.break_after_minutes,
        },
    }
    if quest.subject == "gcse_maths":
        payload.update(
            {
                "pathway": "gcse_maths",
                "pathway_label": "GCSE Maths",
                "tier": GCSE_TIER_LABELS.get(settings.gcse_tier, settings.gcse_tier),
                "exam_board": settings.gcse_board,
            }
        )
    return payload


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------


def _bump_activity(child: Child, **deltas: int) -> None:
    row = today_activity(child, create=True)
    for field, amount in deltas.items():
        setattr(row, field, (getattr(row, field) or 0) + amount)


def _interactive_answer_label(response: dict) -> str:
    points = response.get("points", []) if isinstance(response, dict) else []
    label = ", ".join(
        f"({point[0]:g}, {point[1]:g})" for point in points if isinstance(point, list) and len(point) == 2
    )
    return label[:400] or "Interactive diagram response"


def submit_answer(
    child: Child,
    quest: Quest,
    question_id: int,
    given: str = "",
    response=None,
    seconds: int = 0,
    used_hint: bool = False,
    rng: random.Random | None = None,
) -> dict:
    """Submit a scalar answer or a bounded manual assessment response."""
    rng = rng or random.Random()
    question = db.session.get(QuestQuestion, question_id)
    if question is None or question.quest_id != quest.id:
        return {"error": "That question is not part of this quest."}
    if question.is_answered:
        return {"error": "That question has already been answered."}

    settings = child.settings
    elapsed = max(0, min(int(seconds or 0), 600))
    question.tries += 1
    question.seconds += elapsed
    previous_used_hint = question.used_hint
    if used_hint:
        question.used_hint = True

    interactive_saved = None
    marking_given = given
    if assessments.is_manual(question.kind):
        try:
            saved = assessments.validate_response(
                question.kind,
                response if response is not None else given,
                (question.payload or {}).get("response_spec", {}),
            )
        except ValueError as exc:
            question.tries = max(0, question.tries - 1)
            question.seconds = max(0, question.seconds - elapsed)
            question.used_hint = previous_used_hint
            return {"error": str(exc)}

        question.response_json = saved
        question.response_status = "submitted"
        question.given_answer = {
            "free_text": saved.get("text", ""),
            "handwriting": "Handwriting response",
            "audio": "Audio recording" if saved.get("audio") else "Typed speaking response",
            "evidence": "Investigation record",
        }[question.kind][:400]
        question.answered_at = datetime.now()
        quest.answered_count += 1
        quest.seconds += question.seconds
        first_today = rewards.touch_streak(child)
        _bump_activity(
            child,
            seconds=question.seconds,
            questions=1,
            correct=0,
            xp=0,
        )
        db.session.commit()
        return {
            "status": "submitted",
            "correct": None,
            "pending": True,
            "message": "Saved — a grown-up can review your thinking later.",
            "xp": 0,
            "coins": 0,
            "tries": question.tries,
            "answered": quest.answered_count,
            "total": len(quest.questions),
            "quest_correct": quest.correct_count,
            "child": {"xp": child.xp, "coins": child.coins, "level": child.level,
                      "level_pct": child.level_progress_pct, "streak": child.streak_days},
            "first_today": first_today,
        }

    if assessments.is_interactive(question.kind):
        try:
            interactive_saved = assessments.validate_response(
                question.kind,
                response if response is not None else given,
                (question.payload or {}).get("response_spec", {}),
                (question.payload or {}).get("visual"),
            )
        except ValueError as exc:
            question.tries = max(0, question.tries - 1)
            question.seconds = max(0, question.seconds - elapsed)
            question.used_hint = previous_used_hint
            return {"error": str(exc)}
        marking_given = interactive_saved

    correct = check_answer(marking_given, question.solution or {}, question.kind)

    # One gentle second chance, if a parent has left it on.
    if not correct and question.tries == 1 and settings.second_chance:
        db.session.commit()
        return {
            "status": "retry",
            "message": rng.choice(rewards.CHEERS_RETRY),
            "tries": question.tries,
            "hint": (question.payload or {}).get("hint", "") if settings.allow_hints else "",
        }

    # Finalise a legacy auto-marked question.
    if assessments.is_interactive(question.kind):
        question.response_json = interactive_saved
        question.given_answer = _interactive_answer_label(interactive_saved)
    else:
        question.given_answer = str(given)[:400]
    question.is_correct = correct
    question.response_status = "scored"
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


def record_assessment_review(
    child: Child,
    quest_id: int,
    question_id: int,
    scores: dict,
    feedback: str = "",
) -> dict:
    """Score one submitted manual response once, then update mastery."""
    quest = db.session.get(Quest, quest_id)
    question = db.session.get(QuestQuestion, question_id)
    if (
        quest is None
        or question is None
        or quest.child_id != child.id
        or question.quest_id != quest.id
        or not quest_matches_path(child, quest)
    ):
        return {"error": "That question is not part of this learner's quest."}
    if not assessments.is_manual(question.kind):
        return {"error": "Only open-ended responses need a parent review."}
    if not question.is_pending:
        return {"error": "That response is already reviewed or has not been submitted."}

    try:
        review = assessments.review_response(question.solution or {}, scores, feedback)
    except ValueError as exc:
        return {"error": str(exc)}

    question.score = review["score"]
    question.max_score = review["max_score"]
    question.assessment_json = review
    question.response_status = "reviewed"
    question.is_correct = bool(review["passed"])

    progress = scheduler.get_or_create_progress(child.id, question.skill_id)
    progress.register(question.is_correct, question.seconds)
    quest.correct_count += 1 if question.is_correct else 0
    if question.is_correct:
        response_day = (question.answered_at or datetime.now()).date()
        activity = db.session.execute(
            select(DailyActivity).where(
                DailyActivity.child_id == child.id,
                DailyActivity.on_date == response_day,
            )
        ).scalar_one_or_none()
        if activity is None:
            activity = DailyActivity(child_id=child.id, on_date=response_day)
            db.session.add(activity)
        activity.correct += 1
    if quest.finished_at is not None:
        old_xp = quest.xp_earned or 0
        old_coins = quest.coins_earned or 0
        quest.stars = rewards.stars_for(quest.correct_count, quest.answered_count)
        quest.xp_earned = rewards.XP_QUEST_BONUS + quest.stars * rewards.XP_PER_STAR
        quest.coins_earned = rewards.COINS_QUEST_BONUS + quest.stars * rewards.COINS_PER_STAR
        child.xp += quest.xp_earned - old_xp
        child.coins += quest.coins_earned - old_coins
        bonus_day = quest.finished_at.date()
        activity = db.session.execute(
            select(DailyActivity).where(
                DailyActivity.child_id == child.id,
                DailyActivity.on_date == bonus_day,
            )
        ).scalar_one_or_none()
        if activity is None:
            activity = DailyActivity(child_id=child.id, on_date=bonus_day)
            db.session.add(activity)
        activity.xp += quest.xp_earned - old_xp
    db.session.commit()
    return {"ok": True, "review": review, "correct": question.is_correct}


def record_great_diagnostic(quest: Quest, question_id: int, responses: dict) -> dict:
    """Store child evidence for later parent review, without assigning scores."""
    question = db.session.get(QuestQuestion, question_id)
    if question is None or question.quest_id != quest.id:
        return {"error": "That question is not part of this quest."}
    if question.is_correct is None:
        return {"error": "Answer the question before recording GREAT evidence."}
    existing = great.diagnostic_from_solution(question.solution)
    if existing and existing["scores"] is not None:
        return {"error": "This GREAT evidence has already been reviewed."}

    try:
        question.solution = great.store_diagnostic(question.solution, responses)
    except ValueError as exc:
        return {"error": str(exc)}

    db.session.commit()
    return {"ok": True, "great_diagnostic": great.diagnostic_summary(question.solution)}


def record_great_review(
    child: Child, quest_id: int, question_id: int, scores: dict
) -> dict:
    """Save a parent review of submitted GREAT evidence."""
    quest = db.session.get(Quest, quest_id)
    question = db.session.get(QuestQuestion, question_id)
    if (
        quest is None
        or question is None
        or quest.child_id != child.id
        or question.quest_id != quest.id
        or not quest_matches_path(child, quest)
    ):
        return {"error": "That question is not part of this learner's quest."}

    try:
        question.solution = great.review_diagnostic(question.solution, scores)
    except ValueError as exc:
        return {"error": str(exc)}

    db.session.commit()
    return {"ok": True}


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
        if not question.is_answered:
            continue
        skill = get_skill(question.skill_id)
        item = {
            "position": question.position + 1,
            "prompt": (question.payload or {}).get("prompt", ""),
            "given": question.given_answer,
            "answer": (question.solution or {}).get("answer", ""),
            "explain": (question.solution or {}).get("explain", ""),
            "correct": bool(question.is_correct) if question.is_scored else None,
            "pending": question.is_pending,
            "manual": assessments.is_manual(question.kind),
            "response": question.response_json,
            "score": question.score,
            "max_score": question.max_score,
            "feedback": (question.assessment_json or {}).get("feedback", ""),
            "skill": skill.name if skill else question.skill_id,
            "year": skill.year if skill else None,
        }
        if skill and skill.is_gcse:
            item.update(
                {
                    "year_label": skill.year_label,
                    "pathway_label": skill.pathway_label,
                    "tier": GCSE_TIER_LABELS.get(
                        (question.payload or {}).get("tier", "").lower(),
                        (question.payload or {}).get("tier", ""),
                    ),
                    "exam": (question.payload or {}).get("exam", {}),
                }
            )
        review.append(item)

    pending = sum(1 for question in quest.questions if question.is_pending)
    return {
        "quest_id": quest.id,
        "title": quest.title,
        "answered": answered,
        "pending": pending,
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
    """Return today's unfinished quest on the learner's active pathway."""
    quests_today = db.session.execute(
        select(Quest)
        .where(
            Quest.child_id == child.id,
            Quest.finished_at.is_(None),
            Quest.started_at >= datetime.combine(date.today(), datetime.min.time()),
        )
        .order_by(Quest.started_at.desc())
    ).scalars().all()
    return next((quest for quest in quests_today if quest_matches_path(child, quest)), None)


def recent_quests(child_id: int, limit: int = 10) -> list[Quest]:
    child = db.session.get(Child, child_id)
    if child is None:
        return []
    finished = db.session.execute(
        select(Quest)
        .where(Quest.child_id == child_id, Quest.finished_at.is_not(None))
        .order_by(Quest.finished_at.desc())
    ).scalars().all()
    return [quest for quest in finished if quest_matches_path(child, quest)][:limit]


def lifetime_totals(child_id: int) -> dict:
    child = db.session.get(Child, child_id)
    finished = []
    if child is not None:
        finished = db.session.execute(
            select(Quest)
            .where(Quest.child_id == child_id, Quest.finished_at.is_not(None))
        ).scalars().all()
        finished = [quest for quest in finished if quest_matches_path(child, quest)]
    quests_count = len(finished)
    answered = sum(quest.answered_count for quest in finished)
    correct = sum(quest.correct_count for quest in finished)
    seconds = sum(quest.seconds for quest in finished)
    stars = sum(quest.stars for quest in finished)
    return {
        "quests": int(quests_count),
        "questions": int(answered or 0),
        "correct": int(correct or 0),
        "accuracy": round((correct or 0) / answered * 100) if answered else 0,
        "minutes": round((seconds or 0) / 60),
        "stars": int(stars or 0),
    }
