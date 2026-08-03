"""End-to-end check that every page renders and the whole quest flow works.

    pixi run smoke

Runs against a temporary throwaway database so it never touches real progress.
Exercises: first-run setup, every child page, starting a quest, answering every
question (correctly and incorrectly), the second-chance path, hints, finishing,
the PIN gate, and every parent page.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ✓ {label}")
    else:
        print(f"  ✗ {label} {detail}")
        FAILURES.append(f"{label} {detail}".strip())


def get_csrf(client) -> str:
    with client.session_transaction() as session:
        return session.get("_csrf", "")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tutor-smoke-"))
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'smoke.sqlite3'}"
    os.environ["SECRET_KEY"] = "smoke-test-secret-key"

    from sqlalchemy import func

    from tutor import create_app, db
    from tutor.content import SKILLS_BY_ID
    from tutor.models import Child, Quest, QuestQuestion, SkillProgress
    from tutor.services import profiles

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.create_all()
        # Reproduce what `pixi run setup` does before a parent ever opens the
        # app: the parent account already exists with the default PIN. The PIN
        # chosen on the welcome screen has to override it.
        profiles.ensure_parent_account()
        db.session.commit()

    client = app.test_client()

    # ------------------------------------------------------------------
    print("\nFirst run")
    # ------------------------------------------------------------------
    response = client.get("/", follow_redirects=True)
    check("redirects to the welcome page", b"Learning Quest" in response.data, response.status_code)

    response = client.post(
        "/welcome",
        data={
            "_csrf": get_csrf(client),
            "name": "Smoke",
            "year_group": "3",
            "avatar_emoji": "🦊",
            "avatar_colour": "sunshine",
            "pin": "4321",
        },
        follow_redirects=True,
    )
    check("creates the first learner", b"Smoke" in response.data, response.status_code)

    with app.app_context():
        child = db.session.execute(db.select(Child)).scalars().first()
        check("learner is stored", child is not None and child.name == "Smoke")
        check("settings row created", child is not None and child.settings is not None)
        check(
            "year mix favours Year 3",
            child is not None and child.settings.year_mix.get("3", 0) >= 40,
            child.settings.year_mix if child else "",
        )
        check(
            "quiet hours are off by default",
            child.settings.allowed_from_hour == 0 and child.settings.allowed_to_hour == 0,
            f"{child.settings.allowed_from_hour}-{child.settings.allowed_to_hour}",
        )
        check("the app is available by default", child.settings.within_allowed_hours())

    # ------------------------------------------------------------------
    print("\nChild pages")
    # ------------------------------------------------------------------
    for label, url in [
        ("home", "/home"),
        ("maths", "/learn/maths"),
        ("english", "/learn/english"),
        ("science", "/learn/science"),
        ("badges", "/badges"),
        ("shop", "/shop"),
        ("profile", "/me"),
        ("blocked screen", "/blocked"),
        ("pick learner", "/pick"),
    ]:
        response = client.get(url)
        check(f"GET {url} ({label})", response.status_code == 200, response.status_code)

    response = client.get("/learn/nonsense", follow_redirects=True)
    check("unknown subject redirects home", response.status_code == 200)

    response = client.get("/definitely-not-a-page")
    check("404 page renders", response.status_code == 404)

    # ------------------------------------------------------------------
    print("\nCSRF protection")
    # ------------------------------------------------------------------
    bare = app.test_client()
    bare.get("/")
    response = bare.post("/api/quest/start", json={"mode": "mixed"})
    check("API rejects a missing CSRF token", response.status_code == 400, response.status_code)

    # ------------------------------------------------------------------
    print("\nQuest flow")
    # ------------------------------------------------------------------
    csrf = get_csrf(client)
    headers = {"X-CSRF-Token": csrf}

    response = client.post("/api/quest/start", json={"mode": "mixed"}, headers=headers)
    payload = response.get_json()
    check("quest starts", response.status_code == 200 and payload.get("quest_id"), payload)
    quest_id = payload["quest_id"]

    response = client.get(f"/api/quest/{quest_id}", headers=headers)
    quest = response.get_json()
    check("quest has questions", len(quest.get("questions", [])) >= 4, len(quest.get("questions", [])))
    check(
        "no answers leak to the browser",
        all("answer" not in q for q in quest["questions"]),
    )
    check(
        "every question names a real skill",
        all(q["skill_id"] in SKILLS_BY_ID for q in quest["questions"]),
    )

    response = client.get(f"/play/{quest_id}")
    check("player page renders", response.status_code == 200, response.status_code)

    with app.app_context():
        rows = (
            db.session.execute(
                db.select(QuestQuestion).where(QuestQuestion.quest_id == quest_id)
            )
            .scalars()
            .all()
        )
        solutions = {row.id: (row.solution or {}).get("answer", "") for row in rows}

    # Ask for a hint on the first question.
    first_id = quest["questions"][0]["id"]
    response = client.post(
        f"/api/quest/{quest_id}/hint", json={"question_id": first_id}, headers=headers
    )
    check("hint endpoint responds", response.status_code == 200, response.status_code)

    # Answer wrongly first (exercises the second-chance path), then correctly.
    wrong_then_right = quest["questions"][0]
    response = client.post(
        f"/api/quest/{quest_id}/answer",
        json={"question_id": wrong_then_right["id"], "answer": "!!definitely wrong!!", "seconds": 5},
        headers=headers,
    )
    body = response.get_json()
    check("second chance offered on a wrong first try", body.get("status") == "retry", body)

    response = client.post(
        f"/api/quest/{quest_id}/answer",
        json={
            "question_id": wrong_then_right["id"],
            "answer": solutions[wrong_then_right["id"]],
            "seconds": 4,
        },
        headers=headers,
    )
    body = response.get_json()
    check("correct answer on the second try is accepted", body.get("correct") is True, body)
    check("earns XP", body.get("xp", 0) > 0, body.get("xp"))

    response = client.post(
        f"/api/quest/{quest_id}/answer",
        json={"question_id": wrong_then_right["id"], "answer": "again", "seconds": 1},
        headers=headers,
    )
    check("cannot answer the same question twice", response.status_code == 400, response.status_code)

    # Answer the rest: all correct except the last, which we get wrong twice.
    remaining = quest["questions"][1:]
    deliberate_wrong = remaining[-1]["id"] if remaining else None
    for question in remaining:
        qid = question["id"]
        if qid == deliberate_wrong:
            for _ in range(2):
                client.post(
                    f"/api/quest/{quest_id}/answer",
                    json={"question_id": qid, "answer": "~nope~", "seconds": 3},
                    headers=headers,
                )
        else:
            client.post(
                f"/api/quest/{quest_id}/answer",
                json={"question_id": qid, "answer": solutions[qid], "seconds": 6},
                headers=headers,
            )

    response = client.post("/api/heartbeat", json={"seconds": 15}, headers=headers)
    check("heartbeat records time", response.get_json().get("ok") is True, response.get_json())

    response = client.post(f"/api/quest/{quest_id}/finish", json={}, headers=headers)
    summary = response.get_json()
    check("quest finishes", response.status_code == 200 and "stars" in summary, summary)
    check("all questions answered", summary.get("answered") == len(quest["questions"]), summary.get("answered"))
    check(
        "score matches what we sent",
        summary.get("correct") == len(quest["questions"]) - 1,
        f"{summary.get('correct')} of {len(quest['questions'])}",
    )
    check("at least one star awarded", summary.get("stars", 0) >= 1, summary.get("stars"))
    check("badges awarded on first quest", len(summary.get("badges", [])) >= 1, summary.get("badges"))
    check("review lists every question", len(summary.get("review", [])) == len(quest["questions"]))

    response = client.get(f"/done/{quest_id}")
    check("results page renders", response.status_code == 200, response.status_code)

    with app.app_context():
        quest_row = db.session.get(Quest, quest_id)
        check("quest marked finished in the database", quest_row.finished_at is not None)
        progress = (
            db.session.execute(db.select(SkillProgress).where(SkillProgress.child_id == quest_row.child_id))
            .scalars()
            .all()
        )
        check("skill progress written", len(progress) >= 1, len(progress))
        check("mastery moved above zero", any(p.mastery > 0 for p in progress))
        check("spaced repetition scheduled a due date", all(p.due_on is not None for p in progress))
        child_row = db.session.get(Child, quest_row.child_id)
        check("XP accumulated", child_row.xp > 0, child_row.xp)
        check("coins accumulated", child_row.coins > 0, child_row.coins)
        check("day streak started", child_row.streak_days == 1, child_row.streak_days)

    # ------------------------------------------------------------------
    print("\nOther quest modes")
    # ------------------------------------------------------------------
    for mode, extra in [
        ("revision", {}),
        ("ahead", {}),
        ("focus", {}),
        ("skill", {"skill_id": "m3.mult.times-4"}),
    ]:
        body = {"mode": mode, "count": 4}
        body.update(extra)
        response = client.post("/api/quest/start", json=body, headers=headers)
        data = response.get_json()
        ok = response.status_code == 200 and data.get("quest_id")
        check(f"{mode} quest starts", bool(ok), data)
        if ok:
            client.post(f"/api/quest/{data['quest_id']}/abandon", json={}, headers=headers)

    for subject in ("maths", "english", "science"):
        response = client.post(
            "/api/quest/start", json={"subject": subject, "count": 5}, headers=headers
        )
        data = response.get_json()
        check(f"{subject} quest starts", response.status_code == 200 and data.get("quest_id"), data)
        if data.get("quest_id"):
            detail = client.get(f"/api/quest/{data['quest_id']}", headers=headers).get_json()
            subjects = {q["skill_id"].split(".")[0][0] for q in detail["questions"]}
            expected = {"maths": "m", "english": "e", "science": "s"}[subject]
            check(f"{subject} quest only contains {subject}", subjects == {expected}, subjects)
            client.post(f"/api/quest/{data['quest_id']}/abandon", json={}, headers=headers)

    response = client.post("/api/quest/start", json={"subject": "bogus"}, headers=headers)
    check("unknown subject rejected", response.status_code == 400, response.status_code)

    # ------------------------------------------------------------------
    print("\nShop and profile")
    # ------------------------------------------------------------------
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.coins = 500
        db.session.commit()

    response = client.post(
        "/shop/buy", data={"_csrf": csrf, "item_id": "hat-crown"}, follow_redirects=True
    )
    check("can buy a shop item", b"yours" in response.data.lower(), response.status_code)
    response = client.post(
        "/shop/equip", data={"_csrf": csrf, "item_id": "hat-crown"}, follow_redirects=True
    )
    check("can equip a shop item", response.status_code == 200)
    response = client.post(
        "/shop/buy", data={"_csrf": csrf, "item_id": "hat-crown"}, follow_redirects=True
    )
    check("cannot buy the same item twice", b"already own" in response.data.lower())
    response = client.post(
        "/me",
        data={"_csrf": csrf, "avatar_emoji": "🐼", "avatar_colour": "grape"},
        follow_redirects=True,
    )
    check("can change the avatar", response.status_code == 200)

    # ------------------------------------------------------------------
    print("\nParent area")
    # ------------------------------------------------------------------
    response = client.get("/parent/", follow_redirects=True)
    check("parent area asks for a PIN", b"PIN" in response.data, response.status_code)

    response = client.post(
        "/parent/login", data={"_csrf": get_csrf(client), "pin": "0000"}, follow_redirects=True
    )
    check("wrong PIN is refused", b"not right" in response.data, response.status_code)

    response = client.post(
        "/parent/login",
        data={"_csrf": get_csrf(client), "pin": app.config["DEFAULT_PARENT_PIN"]},
        follow_redirects=True,
    )
    check(
        "the default PIN no longer works once one was chosen at setup",
        b"not right" in response.data,
        response.status_code,
    )

    response = client.post(
        "/parent/login", data={"_csrf": get_csrf(client), "pin": "4321"}, follow_redirects=True
    )
    check("correct PIN unlocks", b"progress" in response.data.lower(), response.status_code)

    for label, url in [
        ("overview", "/parent/"),
        ("progress: maths", "/parent/progress/maths"),
        ("progress: english", "/parent/progress/english"),
        ("progress: science", "/parent/progress/science"),
        ("activity", "/parent/activity"),
        ("settings", "/parent/settings"),
        ("learners", "/parent/children"),
        ("curriculum", "/parent/curriculum"),
        ("quest review", f"/parent/quest/{quest_id}"),
    ]:
        response = client.get(url)
        check(f"GET {url} ({label})", response.status_code == 200, response.status_code)

    # Save settings.
    csrf = get_csrf(client)
    response = client.post(
        "/parent/settings",
        data={
            "_csrf": csrf,
            "quest_length": "6",
            "daily_limit_minutes": "20",
            "daily_quest_goal": "2",
            "break_after_minutes": "10",
            "weekly_quest_goal": "14",
            # 0 to 0 means "any time", keeping the rest of the run independent
            # of the clock. Quiet hours get their own check further down.
            "allowed_from_hour": "0",
            "allowed_to_hour": "0",
            "subjects_enabled": ["maths", "english"],
            "years_enabled": ["2", "3"],
            "year_mix_1": "0",
            "year_mix_2": "40",
            "year_mix_3": "60",
            "difficulty_mode": "challenge",
            "allow_hints": "on",
            "show_explanations": "on",
            "sound_enabled": "on",
            "large_text": "on",
            "focus_skills": ["m3.mult.times-8"],
            "cheer_note": "Great effort today!",
            "reward_note": "Swimming on Saturday",
        },
        follow_redirects=True,
    )
    check("settings save", b"Settings saved" in response.data, response.status_code)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        s = child_row.settings
        check("quest length saved", s.quest_length == 6, s.quest_length)
        check("daily limit saved", s.daily_limit_minutes == 20, s.daily_limit_minutes)
        check("subjects saved", s.subjects_enabled == ["maths", "english"], s.subjects_enabled)
        check("years saved", s.years_enabled == [2, 3], s.years_enabled)
        check("difficulty saved", s.difficulty_mode == "challenge", s.difficulty_mode)
        check("focus skill saved", s.focus_skills == ["m3.mult.times-8"], s.focus_skills)
        check("unchecked box turned off", s.second_chance is False, s.second_chance)
        check("large text turned on", s.large_text is True, s.large_text)
        check("notes saved", s.cheer_note == "Great effort today!", s.cheer_note)

    # A disabled subject must now be refused.
    response = client.post(
        "/api/quest/start", json={"subject": "science"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    check("disabled subject is refused", response.status_code == 403, response.status_code)

    # Quest length setting is honoured.
    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    data = response.get_json()
    detail = client.get(f"/api/quest/{data['quest_id']}").get_json()
    check("quest length setting honoured", detail["total"] == 6, detail["total"])
    check(
        "disabled year 1 excluded",
        all(q["year"] in (2, 3) for q in detail["questions"]),
        {q["year"] for q in detail["questions"]},
    )

    # Focus skills bias selection.
    focus_hits = 0
    for _ in range(8):
        started = client.post(
            "/api/quest/start",
            json={"subject": "maths", "count": 8},
            headers={"X-CSRF-Token": get_csrf(client)},
        ).get_json()
        info = client.get(f"/api/quest/{started['quest_id']}").get_json()
        if any(q["skill_id"] == "m3.mult.times-8" for q in info["questions"]):
            focus_hits += 1
        client.post(
            f"/api/quest/{started['quest_id']}/abandon",
            json={},
            headers={"X-CSRF-Token": get_csrf(client)},
        )
    check("focus skill appears in every quest", focus_hits == 8, f"{focus_hits}/8 quests")

    # PIN change.
    csrf = get_csrf(client)
    response = client.post(
        "/parent/pin",
        data={"_csrf": csrf, "current_pin": "4321", "new_pin": "9876", "confirm_pin": "9876"},
        follow_redirects=True,
    )
    check("PIN can be changed", b"PIN updated" in response.data)

    response = client.post("/parent/logout", data={"_csrf": get_csrf(client)}, follow_redirects=True)
    check("parent area locks", response.status_code == 200)
    response = client.get("/parent/settings", follow_redirects=False)
    check("locked area redirects to login", response.status_code == 302, response.status_code)

    # Add and delete a second learner.
    client.post("/parent/login", data={"_csrf": get_csrf(client), "pin": "9876"})
    csrf = get_csrf(client)
    response = client.post(
        "/parent/children",
        data={"_csrf": csrf, "name": "Second", "year_group": "2",
              "avatar_emoji": "🐨", "avatar_colour": "ocean"},
        follow_redirects=True,
    )
    check("second learner added", b"Second" in response.data)
    with app.app_context():
        second = db.session.execute(db.select(Child).where(Child.name == "Second")).scalar_one()
        second_id = second.id
    response = client.post(
        f"/parent/children/{second_id}/delete",
        data={"_csrf": csrf, "confirm_name": "wrong name"},
        follow_redirects=True,
    )
    check("delete needs the exact name", b"exactly" in response.data)
    response = client.post(
        f"/parent/children/{second_id}/delete",
        data={"_csrf": csrf, "confirm_name": "Second"},
        follow_redirects=True,
    )
    check("learner can be deleted", b"deleted" in response.data)

    # ------------------------------------------------------------------
    print("\nClearing and resetting data")
    # ------------------------------------------------------------------
    from tutor.services import maintenance

    response = client.get("/parent/data")
    check("GET /parent/data renders", response.status_code == 200, response.status_code)

    # Build a known history: three finished quests, one per subject.
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.settings.subjects_enabled = ["maths", "english", "science"]
        child_row.settings.years_enabled = [1, 2, 3]
        child_row.settings.second_chance = False
        db.session.commit()

    made = {}
    for subject in ("maths", "english", "science"):
        started = client.post(
            "/api/quest/start",
            json={"subject": subject, "count": 4},
            headers={"X-CSRF-Token": get_csrf(client)},
        ).get_json()
        quest_id = started["quest_id"]
        detail = client.get(f"/api/quest/{quest_id}").get_json()
        with app.app_context():
            answers = {
                row.id: (row.solution or {}).get("answer", "")
                for row in db.session.execute(
                    db.select(QuestQuestion).where(QuestQuestion.quest_id == quest_id)
                ).scalars().all()
            }
        for question in detail["questions"]:
            client.post(
                f"/api/quest/{quest_id}/answer",
                json={"question_id": question["id"], "answer": answers[question["id"]], "seconds": 5},
                headers={"X-CSRF-Token": get_csrf(client)},
            )
        client.post(f"/api/quest/{quest_id}/finish", json={}, headers={"X-CSRF-Token": get_csrf(client)})
        made[subject] = quest_id

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        before = maintenance.stored_summary(child_row)
        check("summary counts the quests", before["quests"] >= 3, before["quests"])
        check("summary counts the answers", before["questions"] >= 12, before["questions"])
        check("summary counts tracked skills", before["skills"] >= 3, before["skills"])

        per_subject = {row["id"]: row for row in maintenance.subject_summary(child_row)}
        check(
            "per-subject counts are populated",
            all(per_subject[s]["questions"] >= 4 for s in ("maths", "english", "science")),
            {s: per_subject[s]["questions"] for s in per_subject},
        )

        # Rebuilding is idempotent: running it twice must give the same answer
        # as running it once. (The first run also normalises the coin balance,
        # which this test inflated by hand earlier when checking the shop.)
        maintenance.rebuild_derived(child_row)
        child_row = db.session.execute(db.select(Child)).scalars().first()
        once = maintenance.stored_summary(child_row)
        first = (child_row.xp, child_row.coins, once["skills"], once["questions"], once["badges"])

        maintenance.rebuild_derived(child_row)
        child_row = db.session.execute(db.select(Child)).scalars().first()
        twice = maintenance.stored_summary(child_row)
        second = (child_row.xp, child_row.coins, twice["skills"], twice["questions"], twice["badges"])
        check("rebuilding twice gives the same result", first == second, f"{first} -> {second}")
        check("a rebuild keeps every answer", twice["questions"] == before["questions"],
              f"{before['questions']} -> {twice['questions']}")
        check("a rebuild keeps every skill record", twice["skills"] == before["skills"],
              f"{before['skills']} -> {twice['skills']}")
        check("coins never go negative", child_row.coins >= 0, child_row.coins)
        before = twice

    # -- Deleting one quest recalculates everything ---------------------
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        xp_before = child_row.xp
        science_answers = db.session.execute(
            db.select(func.count(QuestQuestion.id)).where(
                QuestQuestion.quest_id == made["science"]
            )
        ).scalar_one()
        science_before = {
            row["id"]: row for row in maintenance.subject_summary(child_row)
        }["science"]["questions"]

    response = client.post(
        "/data/quests/delete",
        data={"_csrf": get_csrf(client), "quest_ids": [made["science"]]},
        follow_redirects=True,
    )
    check("deleting a quest needs the parent route", response.status_code in (200, 404, 405))

    response = client.post(
        "/parent/data/quests/delete",
        data={"_csrf": get_csrf(client), "quest_ids": [str(made["science"])]},
        follow_redirects=True,
    )
    check("a single quest can be removed", b"Removed 1 quest" in response.data, response.status_code)

    with app.app_context():
        check("the quest is gone", db.session.get(Quest, made["science"]) is None)
        check(
            "its answers went with it",
            db.session.execute(
                db.select(func.count(QuestQuestion.id)).where(
                    QuestQuestion.quest_id == made["science"]
                )
            ).scalar_one() == 0,
        )
        child_row = db.session.execute(db.select(Child)).scalars().first()
        check("XP was recalculated downwards", child_row.xp < xp_before, f"{xp_before} -> {child_row.xp}")
        counts = maintenance.stored_summary(child_row)
        check(
            "the answer count dropped by exactly that quest",
            counts["questions"] == before["questions"] - science_answers,
            f"{before['questions']} - {science_answers} vs {counts['questions']}",
        )
        per_subject = {row["id"]: row for row in maintenance.subject_summary(child_row)}
        check(
            "exactly that quest's science answers went",
            per_subject["science"]["questions"] == science_before - science_answers,
            f"{science_before} - {science_answers} vs {per_subject['science']['questions']}",
        )
        check("maths progress survived", per_subject["maths"]["skills"] > 0, per_subject["maths"])

    response = client.post(
        "/parent/data/quests/delete", data={"_csrf": get_csrf(client)}, follow_redirects=True
    )
    check("removing nothing is rejected", b"Tick at least one" in response.data)

    # -- Subject reset --------------------------------------------------
    response = client.post(
        "/parent/data/subject/english/reset",
        data={"_csrf": get_csrf(client), "confirm_name": "not the name"},
        follow_redirects=True,
    )
    check("a subject reset needs the exact name", b"to confirm" in response.data)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        name = child_row.name

    response = client.post(
        "/parent/data/subject/english/reset",
        data={"_csrf": get_csrf(client), "confirm_name": name},
        follow_redirects=True,
    )
    check("a subject can be reset", b"has been reset" in response.data, response.status_code)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        per_subject = {row["id"]: row for row in maintenance.subject_summary(child_row)}
        check("english progress is cleared", per_subject["english"]["skills"] == 0, per_subject["english"])
        check("maths still untouched", per_subject["maths"]["skills"] > 0, per_subject["maths"])
        check(
            "no maths answers were lost",
            per_subject["maths"]["questions"] >= 4,
            per_subject["maths"]["questions"],
        )

    # -- Coins already spent stay spent ---------------------------------
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        owned_before = len(child_row.owned_item_ids())
        maintenance.rebuild_derived(child_row)
        child_row = db.session.execute(db.select(Child)).scalars().first()
        check(
            "shop purchases are not refunded by a rebuild",
            len(child_row.owned_item_ids()) == owned_before,
            f"{owned_before} -> {len(child_row.owned_item_ids())}",
        )

    # -- Full reset -----------------------------------------------------
    response = client.post(
        "/parent/data/reset-all",
        data={"_csrf": get_csrf(client), "confirm_name": "wrong"},
        follow_redirects=True,
    )
    check("a full reset needs the exact name", b"to confirm" in response.data)

    response = client.post(
        "/parent/data/reset-all",
        data={"_csrf": get_csrf(client), "confirm_name": name, "keep_purchases": "on"},
        follow_redirects=True,
    )
    check("a full reset runs", b"clean slate" in response.data, response.status_code)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        counts = maintenance.stored_summary(child_row)
        check("all quests cleared", counts["quests"] == 0, counts["quests"])
        check("all answers cleared", counts["questions"] == 0, counts["questions"])
        check("all skill records cleared", counts["skills"] == 0, counts["skills"])
        check("badges cleared", counts["badges"] == 0, counts["badges"])
        check("XP and coins zeroed", (child_row.xp, child_row.coins) == (0, 0),
              (child_row.xp, child_row.coins))
        check("streak cleared", child_row.streak_days == 0, child_row.streak_days)
        check("shop items kept as asked", counts["items"] == owned_before, counts["items"])
        check("the profile itself survives", child_row.name == name)
        check("settings survive a reset", child_row.settings is not None
              and child_row.settings.quest_length == 6, child_row.settings.quest_length)

    # She can still start a fresh quest afterwards.
    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    check("a new quest works after a reset", response.status_code == 200, response.get_json())

    # -- Backups --------------------------------------------------------
    with app.app_context():
        backups = maintenance.list_backups()
        check("backups were taken automatically", len(backups) >= 3, len(backups))
        check(
            "backups sit beside the database in use",
            all("smoke" in str(b.path.parent.parent) or str(tmp) in str(b.path) for b in backups),
            [str(b.path) for b in backups[:2]],
        )
        check("backup reasons are recorded", any("reset" in b.reason for b in backups),
              [b.reason for b in backups])
        check("path traversal is refused", maintenance.delete_backup("../../tutor.sqlite3") is False)
        check("odd names are refused", maintenance.delete_backup("evil.txt") is False)
        first_name = backups[0].name

    response = client.post(
        "/parent/data/backup", data={"_csrf": get_csrf(client)}, follow_redirects=True
    )
    check("a backup can be taken on demand", b"Backup saved" in response.data)

    response = client.post(
        "/parent/data/backups/delete",
        data={"_csrf": get_csrf(client), "name": first_name},
        follow_redirects=True,
    )
    check("a backup can be deleted", b"Deleted backup" in response.data)

    # ------------------------------------------------------------------
    print("\nQuiet hours")
    # ------------------------------------------------------------------
    with app.app_context():
        from datetime import datetime, timedelta

        child_row = db.session.execute(db.select(Child)).scalars().first()
        now = datetime.now()
        # A one-hour window that definitely does not contain right now.
        shut = (now + timedelta(hours=3)).hour
        child_row.settings.allowed_from_hour = shut
        child_row.settings.allowed_to_hour = (shut + 1) % 24
        db.session.commit()
        check("outside the window is detected", not child_row.settings.within_allowed_hours())

    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    body = response.get_json()
    check("quiet hours block a new quest", response.status_code == 403 and body.get("blocked"), body)
    response = client.get("/home")
    check("home explains the quiet hours", b"The app is open between" in response.data)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.settings.allowed_from_hour = 0
        child_row.settings.allowed_to_hour = 0
        db.session.commit()

    # ------------------------------------------------------------------
    print("\nDaily time limit")
    # ------------------------------------------------------------------
    with app.app_context():
        from tutor.models import DailyActivity, today

        child_row = db.session.execute(db.select(Child)).scalars().first()
        row = db.session.execute(
            db.select(DailyActivity).where(
                DailyActivity.child_id == child_row.id, DailyActivity.on_date == today()
            )
        ).scalar_one_or_none()
        if row is None:
            row = DailyActivity(child_id=child_row.id, on_date=today())
            db.session.add(row)
        row.seconds = 99999
        db.session.commit()

    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    body = response.get_json()
    check("daily limit blocks a new quest", response.status_code == 403 and body.get("blocked"), body)

    response = client.get("/home")
    check("home explains the limit", b"minutes for today" in response.data, response.status_code)

    # ------------------------------------------------------------------
    print()
    print("=" * 62)
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} of {CHECKS} checks")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"PASSED: all {CHECKS} checks")
    _ = profiles
    return 0


if __name__ == "__main__":
    sys.exit(main())
