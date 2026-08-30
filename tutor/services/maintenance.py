"""Clearing and resetting a learner's data, safely.

The guiding rule is that **only answers are recorded; everything else is
derived**. Skill mastery, daily activity, XP, coins, streaks and badges are all
recomputed from the surviving ``QuestQuestion`` rows by replaying them through
the same ``SkillProgress.register`` the live app uses. That means:

* a parent can remove one bad session without the rest of the figures going
  stale or inconsistent,
* there is no second copy of the scoring rules to drift out of step,
* any reset is a matter of deleting some answers and rebuilding, so the same
  code path covers "undo this quest" and "start the whole subject again".

Every destructive action takes a timestamped backup of the database first.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, or_, select

from ..config import Config
from ..content import SUBJECTS, get_skill
from ..extensions import db
from ..models import (
    BadgeAward,
    Child,
    DailyActivity,
    OwnedItem,
    Quest,
    QuestQuestion,
    SkillProgress,
)
from . import assessments, rewards

KEEP_BACKUPS = 20


def live_db_path() -> Path:
    """The SQLite file actually in use, honouring DATABASE_URL.

    Reading this from the app config rather than a module constant matters: the
    smoke test points DATABASE_URL at a throwaway file, and backing up the real
    family database from a test run would be unforgivable.
    """
    try:
        from flask import current_app

        uri = str(current_app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    except Exception:  # noqa: BLE001 - outside an application context
        uri = ""
    prefix = "sqlite:///"
    if uri.startswith(prefix):
        return Path(uri[len(prefix) :])
    return Config.DB_PATH


def backup_dir() -> Path:
    """Backups sit next to whichever database is in use."""
    return live_db_path().parent / "backups"


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Backup:
    path: Path
    made_at: datetime
    reason: str
    size_kb: int

    @property
    def name(self) -> str:
        return self.path.name


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "backup"


def backup_database(reason: str) -> Path | None:
    """Take a consistent snapshot of the database. Returns the file written.

    Uses SQLite's own backup API rather than copying the file, so it is safe to
    run while the app is serving and captures anything still in the WAL.
    """
    source_path = live_db_path()
    if not source_path.exists():
        return None

    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S.%f")[:-4]
    destination = folder / f"{stamp}--{_slug(reason)}.sqlite3"

    source = sqlite3.connect(source_path)
    target = sqlite3.connect(destination)
    try:
        with target:
            source.backup(target)
    finally:
        target.close()
        source.close()

    _prune_backups()
    return destination


def _prune_backups() -> None:
    backups = sorted(backup_dir().glob("*.sqlite3"), key=lambda p: p.name, reverse=True)
    for stale in backups[KEEP_BACKUPS:]:
        stale.unlink(missing_ok=True)


def list_backups() -> list[Backup]:
    folder = backup_dir()
    if not folder.is_dir():
        return []
    out: list[Backup] = []
    for path in sorted(folder.glob("*.sqlite3"), reverse=True):
        stem = path.stem
        made_at = datetime.fromtimestamp(path.stat().st_mtime)
        reason = ""
        if "--" in stem:
            raw_stamp, _, raw_reason = stem.partition("--")
            reason = raw_reason.replace("-", " ")
            for pattern in ("%Y%m%d-%H%M%S.%f", "%Y%m%d-%H%M%S"):
                try:
                    made_at = datetime.strptime(raw_stamp, pattern)
                    break
                except ValueError:
                    continue
        out.append(
            Backup(
                path=path,
                made_at=made_at,
                reason=reason or "backup",
                size_kb=round(path.stat().st_size / 1024),
            )
        )
    return out


def delete_backup(name: str) -> bool:
    """Delete one backup by file name. Refuses anything outside the folder."""
    if not name.endswith(".sqlite3") or "/" in name or "\\" in name or ".." in name:
        return False
    folder = backup_dir()
    target = (folder / name).resolve()
    try:
        target.relative_to(folder.resolve())
    except ValueError:
        return False
    if not target.is_file():
        return False
    target.unlink()
    return True


def restore_backup(name: str) -> str | None:
    """Copy a backup over the live database. Returns a problem, or None.

    Only meaningful with the server stopped, which is why this is driven from
    the command line (``pixi run restore-backup``) rather than the web UI.
    """
    if not name.endswith(".sqlite3") or "/" in name or ".." in name:
        return "That is not a valid backup name."
    folder = backup_dir()
    source = (folder / name).resolve()
    try:
        source.relative_to(folder.resolve())
    except ValueError:
        return "That backup is outside the backups folder."
    if not source.is_file():
        return f"No backup called {name}."

    live = live_db_path()
    if live.exists():
        shutil.copy2(live, folder / f"{datetime.now():%Y%m%d-%H%M%S}--replaced-by-restore.sqlite3")
    for suffix in ("-wal", "-shm"):
        stale = live.with_name(live.name + suffix)
        stale.unlink(missing_ok=True)
    shutil.copy2(source, live)
    return None


# ---------------------------------------------------------------------------
# What is stored
# ---------------------------------------------------------------------------


def _quest_is_active(child: Child, quest: Quest) -> bool:
    """Return true only for quests in the learner's current curriculum."""
    from . import pathways

    return pathways.quest_matches_path(
        child.settings,
        quest.subject,
        [question.skill_id for question in quest.questions],
    )


def _child_quests(child: Child, *, finished_only: bool = False) -> list[Quest]:
    stmt = select(Quest).where(Quest.child_id == child.id)
    if finished_only:
        stmt = stmt.where(Quest.finished_at.is_not(None))
    return db.session.execute(stmt.order_by(Quest.started_at)).scalars().all()


def _active_quests(child: Child, *, finished_only: bool = False) -> list[Quest]:
    return [
        quest
        for quest in _child_quests(child, finished_only=finished_only)
        if _quest_is_active(child, quest)
    ]


def stored_summary(child: Child) -> dict:
    """Counts for the learner's active pathway, not incompatible old history."""
    from . import pathways

    active_quests = _active_quests(child, finished_only=True)
    active_ids = {skill.id for skill in pathways.active_skills(child.settings)}
    progress_rows = db.session.execute(
        select(SkillProgress).where(SkillProgress.child_id == child.id)
    ).scalars().all()
    answered = sum(
        1
        for quest in active_quests
        for question in quest.questions
        if question.is_answered
    )
    first = min((quest.started_at for quest in active_quests), default=None)
    seconds = sum(quest.seconds or 0 for quest in active_quests)
    items = db.session.execute(
        select(func.count(OwnedItem.id)).where(OwnedItem.child_id == child.id)
    ).scalar_one()
    days = {
        (question.answered_at or quest.started_at).date()
        for quest in active_quests
        for question in quest.questions
        if question.is_answered
    }

    return {
        "quests": len(active_quests),
        "questions": answered,
        "skills": sum(1 for row in progress_rows if row.skill_id in active_ids),
        "badges": len(rewards.visible_badge_awards(child)),
        "days": len(days),
        "items": int(items or 0),
        "minutes": round(seconds / 60),
        "xp": child.xp,
        "coins": child.coins,
        "first_activity": first,
    }


def subject_summary(child: Child) -> list[dict]:
    """Counts only subjects available on the learner's active pathway."""
    from . import pathways

    allowed = pathways.subject_ids(child.settings)
    rows = db.session.execute(
        select(QuestQuestion.skill_id, func.count(QuestQuestion.id))
        .join(Quest, Quest.id == QuestQuestion.quest_id)
        .where(
            Quest.child_id == child.id,
            or_(
                QuestQuestion.is_correct.is_not(None),
                QuestQuestion.response_status != "unanswered",
            ),
        )
        .group_by(QuestQuestion.skill_id)
    ).all()

    tally: dict[str, int] = dict.fromkeys(allowed, 0)
    for skill_id, number in rows:
        skill = get_skill(skill_id)
        if skill and skill.subject in tally:
            tally[skill.subject] += int(number)

    progress_rows = db.session.execute(
        select(SkillProgress).where(SkillProgress.child_id == child.id)
    ).scalars().all()
    skills_touched: dict[str, int] = dict.fromkeys(allowed, 0)
    for row in progress_rows:
        skill = get_skill(row.skill_id)
        if skill and skill.subject in skills_touched:
            skills_touched[skill.subject] += 1

    return [
        {
            "id": key,
            "subject": SUBJECTS[key],
            "questions": tally[key],
            "skills": skills_touched[key],
        }
        for key in allowed
    ]


# ---------------------------------------------------------------------------
# Rebuilding derived progress
# ---------------------------------------------------------------------------


def rebuild_derived(child: Child) -> dict:
    """Recompute derived data from surviving answers on the active pathway."""
    # 1. Re-derive each quest's own totals, and drop any left with no questions.
    quests = _child_quests(child)
    removed_quests = 0
    for quest in quests:
        questions = list(quest.questions)
        if not questions:
            db.session.delete(quest)
            removed_quests += 1
            continue
        answered = [q for q in questions if q.is_answered]
        quest.target_count = len(questions)
        quest.answered_count = len(answered)
        quest.correct_count = sum(1 for q in answered if q.is_correct)
        quest.seconds = sum(q.seconds or 0 for q in answered)
        if quest.finished_at is not None:
            quest.stars = rewards.stars_for(quest.correct_count, quest.answered_count)
            quest.xp_earned = (
                rewards.XP_QUEST_BONUS + quest.stars * rewards.XP_PER_STAR
                if quest.answered_count
                else 0
            )
            quest.coins_earned = (
                rewards.COINS_QUEST_BONUS + quest.stars * rewards.COINS_PER_STAR
                if quest.answered_count
                else 0
            )
    db.session.flush()

    active_quests = [quest for quest in quests if _quest_is_active(child, quest)]
    active_quest_ids = {quest.id for quest in active_quests}

    # 2. Clear the derived tables.
    for model in (SkillProgress, DailyActivity, BadgeAward):
        for row in db.session.execute(
            select(model).where(model.child_id == child.id)
        ).scalars().all():
            db.session.delete(row)
    child.xp = 0
    child.coins = 0
    child.streak_days = 0
    child.best_streak = 0
    child.last_active_on = None
    db.session.flush()

    # 3. Replay only answers belonging to the active pathway.
    answers = db.session.execute(
        select(QuestQuestion)
        .join(Quest, Quest.id == QuestQuestion.quest_id)
        .where(
            Quest.child_id == child.id,
            or_(
                QuestQuestion.is_correct.is_not(None),
                QuestQuestion.response_status != "unanswered",
            ),
        )
        .order_by(QuestQuestion.answered_at, QuestQuestion.id)
    ).scalars().all()
    answers = [answer for answer in answers if answer.quest_id in active_quest_ids]

    progress: dict[str, SkillProgress] = {}
    activity: dict[object, DailyActivity] = {}

    def activity_for(day) -> DailyActivity:
        row = activity.get(day)
        if row is None:
            row = DailyActivity(child_id=child.id, on_date=day)
            db.session.add(row)
            db.session.flush()
            activity[day] = row
        return row

    for answer in answers:
        when = answer.answered_at or datetime.now()
        day = when.date()

        # Pending open-ended responses count as activity, but cannot affect
        # mastery or answer rewards until a parent has reviewed them.
        xp = 0
        if answer.is_correct is not None:
            row = progress.get(answer.skill_id)
            if row is None:
                row = SkillProgress(child_id=child.id, skill_id=answer.skill_id, due_on=day)
                db.session.add(row)
                db.session.flush()
                progress[answer.skill_id] = row
            row.register(bool(answer.is_correct), answer.seconds or 0, on=day, at=when)
            if not assessments.is_manual(answer.kind):
                xp = rewards.xp_for_answer(bool(answer.is_correct), answer.tries or 1)

        today_row = activity_for(day)
        today_row.questions += 1
        today_row.correct += 1 if answer.is_correct else 0
        today_row.seconds += answer.seconds or 0
        today_row.xp += xp
        child.xp += xp
        child.coins += rewards.COINS_PER_CORRECT if answer.is_correct else 0

    # 4. Quest completion bonuses from active-path quests only.
    for quest in active_quests:
        if quest.finished_at is None:
            continue
        child.xp += quest.xp_earned or 0
        child.coins += quest.coins_earned or 0
        row = activity_for(quest.finished_at.date())
        row.quests += 1
        row.xp += quest.xp_earned or 0

    # 5. Coins already spent in the shop stay spent, so the totals stay honest.
    owned = db.session.execute(
        select(OwnedItem).where(OwnedItem.child_id == child.id)
    ).scalars().all()
    spent = sum(
        rewards.SHOP_BY_ID[item.item_id].cost
        for item in owned
        if item.item_id in rewards.SHOP_BY_ID
    )
    child.coins = max(0, child.coins - spent)

    # 6. Streak, from days that really have activity.
    active_days = sorted(day for day, row in activity.items() if row.questions)
    if active_days:
        child.last_active_on = active_days[-1]
        streak = 1
        best = 1
        for earlier, later in zip(active_days, active_days[1:], strict=False):
            streak = streak + 1 if (later - earlier).days == 1 else 1
            best = max(best, streak)
        child.streak_days = streak
        child.best_streak = best

    db.session.flush()
    fresh_badges = rewards.evaluate_badges(child)
    db.session.commit()

    return {
        "answers": len(answers),
        "skills": len(progress),
        "days": len(activity),
        "empty_quests_removed": removed_quests,
        "badges": len(fresh_badges),
    }


# ---------------------------------------------------------------------------
# The resets themselves
# ---------------------------------------------------------------------------


def delete_quests(child: Child, quest_ids: list[int]) -> dict:
    """Remove active-path quests, then rebuild derived data."""
    wanted = set(quest_ids)
    quests = [
        quest
        for quest in db.session.execute(
            select(Quest).where(Quest.child_id == child.id, Quest.id.in_(wanted))
        ).scalars().all()
        if _quest_is_active(child, quest)
    ]
    if not quests:
        return {"removed": 0}

    backup = backup_database(f"before removing {len(quests)} quests")
    titles = [q.title for q in quests]
    for quest in quests:
        db.session.delete(quest)
    db.session.commit()

    result = rebuild_derived(child)
    result.update({"removed": len(quests), "titles": titles, "backup": backup})
    return result


def reset_subject(child: Child, subject: str) -> dict:
    """Forget one active-path subject, keeping other subjects intact."""
    from . import pathways

    if subject not in pathways.subject_ids(child.settings):
        return {"error": "inactive_subject", "removed": 0}

    rows = db.session.execute(
        select(QuestQuestion)
        .join(Quest, Quest.id == QuestQuestion.quest_id)
        .where(Quest.child_id == child.id)
    ).scalars().all()

    doomed = []
    for row in rows:
        skill = get_skill(row.skill_id)
        if skill and skill.subject == subject:
            doomed.append(row)

    if not doomed:
        # Nothing answered, but there may still be stale skill rows to clear.
        stale = []
        for row in db.session.execute(
            select(SkillProgress).where(SkillProgress.child_id == child.id)
        ).scalars().all():
            skill = get_skill(row.skill_id)
            if skill and skill.subject == subject:
                stale.append(row)
        if not stale:
            return {"removed": 0, "skills_cleared": 0}
        backup = backup_database(f"before resetting {subject}")
        for row in stale:
            db.session.delete(row)
        db.session.commit()
        return {
            "removed": 0,
            "skills_cleared": len(stale),
            "subject": subject,
            "backup": backup,
        }

    backup = backup_database(f"before resetting {subject}")
    for row in doomed:
        db.session.delete(row)
    db.session.commit()

    result = rebuild_derived(child)
    result.update({"removed": len(doomed), "subject": subject, "backup": backup})
    return result


def reset_all_progress(child: Child, keep_purchases: bool = True) -> dict:
    """Wipe every quest and all progress, keeping the profile and settings."""
    backup = backup_database(f"before resetting {child.name}")

    counts = stored_summary(child)
    for model in (Quest, SkillProgress, DailyActivity, BadgeAward):
        for row in db.session.execute(
            select(model).where(model.child_id == child.id)
        ).scalars().all():
            db.session.delete(row)

    if not keep_purchases:
        for row in db.session.execute(
            select(OwnedItem).where(OwnedItem.child_id == child.id)
        ).scalars().all():
            db.session.delete(row)
        child.equipped_hat = None
        child.equipped_pet = None
        child.equipped_scene = None

    child.xp = 0
    child.coins = 0
    child.streak_days = 0
    child.best_streak = 0
    child.last_active_on = None
    db.session.commit()

    return {"cleared": counts, "backup": backup, "kept_purchases": keep_purchases}
