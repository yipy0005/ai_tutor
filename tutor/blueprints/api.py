"""JSON endpoints used by the quest player.

The browser is never told an answer in advance, and every submission is marked
server side. The heartbeat endpoint is what makes the parent's daily time limit
reflect real time spent rather than questions answered.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..content import PATHWAY_SUBJECT_ORDER, SUBJECTS
from ..services import quests, scheduler

bp = Blueprint("api", __name__, url_prefix="/api")

VALID_MODES = set(scheduler.MODES)


def _need_child():
    if g.child is None:
        return jsonify({"error": "No learner is signed in.", "reload": True}), 401
    return None


def _body() -> dict:
    return request.get_json(silent=True) or {}


@bp.post("/quest/start")
def start():
    if (problem := _need_child()) is not None:
        return problem
    child = g.child

    if (reason := quests.blocked_reason(child)) is not None:
        return jsonify({"error": reason, "blocked": True}), 403

    data = _body()
    subject = data.get("subject")
    if subject in {"", "mixed", None}:
        subject = None
    elif subject not in SUBJECTS:
        return jsonify({"error": "Unknown subject."}), 400

    try:
        subject = quests.subject_for_path(child, subject)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 403

    if subject in PATHWAY_SUBJECT_ORDER:
        if child.settings.gcse_tier not in {"foundation", "higher"}:
            return jsonify(
                {"error": f"{SUBJECTS[subject].name} is switched off in settings."}
            ), 403
    elif subject:
        enabled = child.settings.subjects_enabled or ["maths", "english", "science"]
        if subject not in enabled:
            return jsonify({"error": "That subject is switched off in settings."}), 403

    mode = data.get("mode") or "mixed"
    if mode not in VALID_MODES:
        mode = "mixed"

    skill_id = data.get("skill_id") or None
    count = data.get("count")

    try:
        quest = quests.start_quest(
            child, subject=subject, mode=mode, count=count, skill_id=skill_id
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "quest_id": quest.id, "url": f"/play/{quest.id}"})


@bp.get("/quest/<int:quest_id>")
def read(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404
    return jsonify(quests.quest_payload(quest, g.child))


@bp.post("/quest/<int:quest_id>/answer")
def answer(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404

    data = _body()
    question_id = data.get("question_id")
    if not isinstance(question_id, int):
        return jsonify({"error": "Missing question id."}), 400

    result = quests.submit_answer(
        g.child,
        quest,
        question_id,
        given=str(data.get("answer", "")),
        response=data.get("response"),
        seconds=int(data.get("seconds") or 0),
        used_hint=bool(data.get("used_hint")),
    )
    status = 400 if result.get("error") else 200
    return jsonify(result), status


@bp.post("/quest/<int:quest_id>/great")
def great_reflection(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404

    data = _body()
    question_id = data.get("question_id")
    if not isinstance(question_id, int):
        return jsonify({"error": "Missing question id."}), 400

    result = quests.record_great(quest, question_id, data.get("scores"))
    status = 400 if result.get("error") else 200
    return jsonify(result), status


@bp.post("/quest/<int:quest_id>/great-diagnostic")
def great_diagnostic(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404
    if not g.child.settings.great_diagnostic:
        return jsonify({"error": "Evidence-based GREAT is not enabled."}), 403

    data = _body()
    question_id = data.get("question_id")
    if not isinstance(question_id, int):
        return jsonify({"error": "Missing question id."}), 400

    result = quests.record_great_diagnostic(quest, question_id, data.get("responses"))
    status = 400 if result.get("error") else 200
    return jsonify(result), status


@bp.post("/quest/<int:quest_id>/hint")
def hint(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404
    data = _body()
    question_id = data.get("question_id")
    if not isinstance(question_id, int):
        return jsonify({"error": "Missing question id."}), 400
    return jsonify(quests.use_hint(g.child, quest, question_id))


@bp.post("/quest/<int:quest_id>/finish")
def finish(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404
    return jsonify(quests.finish_quest(g.child, quest))


@bp.post("/quest/<int:quest_id>/abandon")
def abandon(quest_id: int):
    if (problem := _need_child()) is not None:
        return problem
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return jsonify({"error": "Quest not found."}), 404
    quests.abandon_quest(g.child, quest)
    return jsonify({"ok": True})


@bp.post("/heartbeat")
def heartbeat():
    """Called every 15 seconds while a quest is on screen.

    Records real time on task so the daily limit is about minutes spent, not
    questions answered, and tells the player when time has run out.
    """
    if (problem := _need_child()) is not None:
        return problem
    child = g.child
    seconds = int(_body().get("seconds") or 0)
    seconds = max(0, min(seconds, 120))
    if seconds:
        row = quests.today_activity(child, create=True)
        row.seconds = (row.seconds or 0) + seconds
        from ..extensions import db

        db.session.commit()

    state = quests.allowance(child)
    return jsonify(
        {
            "ok": True,
            "minutes_used": state["used_minutes"],
            "minutes_left": state["minutes_left"],
            "out_of_time": state["out_of_time"],
            "within_hours": state["within_hours"],
        }
    )


@bp.get("/state")
def state():
    if (problem := _need_child()) is not None:
        return problem
    child = g.child
    return jsonify(
        {
            "child": {
                "name": child.name,
                "xp": child.xp,
                "coins": child.coins,
                "level": child.level,
                "level_pct": child.level_progress_pct,
                "streak": child.streak_days,
            },
            "allowance": quests.allowance(child),
        }
    )
