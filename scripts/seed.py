"""Prepare the database for first use.

    pixi run seed
    pixi run seed -- --name Amelia --year 3
    pixi run seed -- --demo          # add a few weeks of pretend history

The demo data is handy for seeing what the parent dashboard looks like with a
term's worth of practice in it. It only ever applies to a profile called
"Demo" so it can never mix in with real progress.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta

from tutor import create_app, db
from tutor.config import Config
from tutor.content import ALL_SKILLS, content_summary, draw_question, split_question
from tutor.models import DailyActivity, Quest, QuestQuestion, SkillProgress
from tutor.services import maintenance, profiles, rewards, scheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the tutor database.")
    parser.add_argument(
        "--name",
        default=None,
        help="Create a learner profile now. Omit it and the app will guide you through adult setup.",
    )
    parser.add_argument("--year", type=int, default=3, help="Year group they are entering")
    parser.add_argument("--pin", default=None, help="Parent PIN (defaults to 1234)")
    parser.add_argument("--learner-login", default=None, help="Learner sign-in name for --name")
    parser.add_argument("--learner-pin", default=None, help="Learner PIN for --name")
    parser.add_argument("--demo", action="store_true", help="Also create a Demo profile with history")
    args = parser.parse_args()
    if args.learner_pin and not args.learner_login:
        parser.error("--learner-pin requires --learner-login")
    return args


def build_demo_history(child, weeks: int = 6) -> None:
    """Invent a believable practice history so the dashboard has something to show."""
    rng = random.Random(20260802)
    today = date.today()
    start = today - timedelta(days=weeks * 7)

    skills = [s for s in ALL_SKILLS if scheduler.is_playable(s)]
    rng.shuffle(skills)
    # A realistic child has touched some of the curriculum, not all of it.
    working_set = skills[: int(len(skills) * 0.55)]

    day = start
    while day <= today:
        # Practised on roughly 5 days in 7, less often at weekends. The last
        # few days are always active so the demo shows a live streak.
        recent = (today - day).days <= 2
        chance = 1.0 if recent else (0.55 if day.weekday() >= 5 else 0.85)
        if rng.random() > chance:
            day += timedelta(days=1)
            continue

        quests_today = rng.choice([1, 1, 2, 2, 3])
        activity = DailyActivity(child_id=child.id, on_date=day)
        db.session.add(activity)

        for _ in range(quests_today):
            subject = rng.choice(["maths", "english", "science"])
            pool = [s for s in working_set if s.subject == subject] or working_set
            length = rng.choice([6, 8, 8, 10])
            picks = [rng.choice(pool) for _ in range(length)]

            quest = Quest(
                child_id=child.id,
                subject=subject,
                mode=rng.choice(["mixed", "mixed", "revision", "ahead"]),
                title=f"{subject.title()} Mix",
                target_count=length,
                started_at=datetime.combine(day, datetime.min.time())
                + timedelta(hours=rng.randint(8, 18), minutes=rng.randint(0, 59)),
            )
            db.session.add(quest)
            db.session.flush()

            correct_count = 0
            total_seconds = 0
            for position, skill in enumerate(picks):
                question = draw_question(skill.id, rng, level=1)
                payload, solution = split_question(question)
                # Later weeks go better than earlier ones.
                progress_ratio = (day - start).days / max(1, (today - start).days)
                success_chance = 0.55 + 0.3 * progress_ratio
                is_right = rng.random() < success_chance
                seconds = rng.randint(8, 45)
                total_seconds += seconds

                db.session.add(
                    QuestQuestion(
                        quest_id=quest.id,
                        position=position,
                        skill_id=skill.id,
                        kind=question.get("kind", "choice"),
                        difficulty_level=1,
                        payload=payload,
                        solution=solution,
                        given_answer=solution["answer"] if is_right else "(a wrong answer)",
                        is_correct=is_right,
                        tries=1 if is_right else rng.choice([1, 2]),
                        seconds=seconds,
                        answered_at=quest.started_at + timedelta(seconds=total_seconds),
                    )
                )
                if is_right:
                    correct_count += 1

                # Replay through the same code path the live app uses, so the
                # demo numbers cannot drift from the real scoring rules.
                row = db.session.execute(
                    db.select(SkillProgress).where(
                        SkillProgress.child_id == child.id,
                        SkillProgress.skill_id == skill.id,
                    )
                ).scalar_one_or_none()
                if row is None:
                    row = SkillProgress(child_id=child.id, skill_id=skill.id, due_on=day)
                    db.session.add(row)
                    db.session.flush()
                row.register(is_right, seconds, on=day, at=quest.started_at)

            quest.answered_count = length
            quest.correct_count = correct_count
            quest.seconds = total_seconds
            quest.stars = rewards.stars_for(correct_count, length)
            quest.xp_earned = rewards.XP_QUEST_BONUS + quest.stars * rewards.XP_PER_STAR
            quest.coins_earned = rewards.COINS_QUEST_BONUS + quest.stars * rewards.COINS_PER_STAR
            quest.finished_at = quest.started_at + timedelta(seconds=total_seconds + 30)

            activity.quests += 1
            activity.questions += length
            activity.correct += correct_count
            activity.seconds += total_seconds
            activity.xp += quest.xp_earned + length * 8
            child.xp += quest.xp_earned + length * 8
            child.coins += quest.coins_earned + correct_count

        child.last_active_on = day
        day += timedelta(days=1)

    # Rebuild the streak from the activity we just wrote.
    days_active = sorted(
        row.on_date
        for row in db.session.execute(
            db.select(DailyActivity).where(DailyActivity.child_id == child.id)
        ).scalars().all()
    )
    streak = 0
    cursor = today
    active = set(days_active)
    while cursor in active:
        streak += 1
        cursor -= timedelta(days=1)
    child.streak_days = streak
    child.best_streak = max(streak, 9)

    db.session.flush()
    rewards.evaluate_badges(child)
    db.session.commit()


def main() -> int:
    args = parse_args()
    app = create_app()

    with app.app_context():
        db.create_all()

        account = profiles.ensure_parent_account()
        if args.pin is not None:
            pin = profiles.validate_pin(args.pin, required=True, label="parent")
            account.set_pin(pin)
        if args.name or args.demo or args.pin is not None:
            profiles.mark_parent_setup_complete(account)
        db.session.commit()

        existing = profiles.all_children()
        if existing:
            print(f"Existing profiles: {', '.join(c.name for c in existing)}")
        elif args.name:
            child = profiles.create_child(
                args.name,
                args.year,
                learner_login=args.learner_login,
                learner_pin=args.learner_pin,
            )
            profiles.link_parent_child(account.id, child.id)
            db.session.commit()
            print(f"Created learner profile: {child.name} (Year {child.year_group})")
            print(f"Learner sign-in name: {child.learner_account.login_name}")
            if child.learner_account.needs_activation:
                print("Set the learner PIN from Parent → Learners before signing in.")
        else:
            print("No learner profile yet — the app will ask for a name on first visit.")

        if args.demo:
            demo = next((c for c in profiles.all_children() if c.name == "Demo"), None)
            if demo is None:
                demo = profiles.create_child("Demo", 3, "panda", "grape")
                profiles.link_parent_child(account.id, demo.id)
                db.session.commit()
                print("Building six weeks of demo history (this takes a moment)…")
                build_demo_history(demo)
                print("Demo profile ready.")
            else:
                print("Demo profile already exists — leaving it alone.")

        summary = content_summary()
        print()
        print(f"Database:        {maintenance.live_db_path()}")
        print(f"Skills:          {summary['skills']}")
        print(f"Bank questions:  {summary['bank_questions']}")
        print(f"Maths generators:{summary['generators']}")
        print(f"Parent PIN:      {'as supplied' if args.pin else 'choose in adult setup'}")
        print()
        print(f"Next:  pixi run serve   then open http://127.0.0.1:{Config.PORT}")
        _ = account
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
