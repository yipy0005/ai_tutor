"""Database models.

Design notes
------------
* Curriculum content (subjects, topics, skills, questions) lives in code and
  JSON under ``tutor/content`` so a parent can edit it without a migration.
  The database only stores *progress* against skill ids.
* Every question a child is shown is written to ``QuestQuestion`` so a parent
  can review the exact wording later, and so answers are never trusted from
  the browser.
* Times are stored as naive local datetimes. For a household app "did she
  practise today" is a local-time question.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

JSON = db.JSON


def now() -> datetime:
    return datetime.now()


def today() -> date:
    return date.today()


def _new_auth_nonce() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Learner
# ---------------------------------------------------------------------------


class Child(db.Model):
    __tablename__ = "child"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    year_group: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    avatar_emoji: Mapped[str] = mapped_column(String(16), default="🦊")
    avatar_colour: Mapped[str] = mapped_column(String(20), default="sunshine")

    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_active_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    equipped_hat: Mapped[str | None] = mapped_column(String(40), nullable=True)
    equipped_pet: Mapped[str | None] = mapped_column(String(40), nullable=True)
    equipped_scene: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    settings: Mapped[Settings] = relationship(
        back_populates="child", uselist=False, cascade="all, delete-orphan"
    )
    learner_account: Mapped[LearnerAccount | None] = relationship(
        back_populates="child", uselist=False, cascade="all, delete-orphan"
    )
    parent_links: Mapped[list[ParentChild]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    progress: Mapped[list[SkillProgress]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    quests: Mapped[list[Quest]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    activity: Mapped[list[DailyActivity]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    badges: Mapped[list[BadgeAward]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    items: Mapped[list[OwnedItem]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )

    # -- levels -------------------------------------------------------------
    # A level costs a bit more each time, so early levels come quickly.
    @property
    def level(self) -> int:
        lvl, need, spent = 1, 100, 0
        while self.xp >= spent + need:
            spent += need
            lvl += 1
            need = 100 + (lvl - 1) * 40
        return lvl

    @property
    def level_floor(self) -> int:
        lvl, need, spent = 1, 100, 0
        while self.xp >= spent + need:
            spent += need
            lvl += 1
            need = 100 + (lvl - 1) * 40
        return spent

    @property
    def level_span(self) -> int:
        return 100 + (self.level - 1) * 40

    @property
    def level_progress_pct(self) -> int:
        span = self.level_span
        if span <= 0:
            return 0
        return min(100, round((self.xp - self.level_floor) / span * 100))

    @property
    def xp_to_next_level(self) -> int:
        return max(0, self.level_floor + self.level_span - self.xp)

    def badge_ids(self) -> set[str]:
        return {b.badge_id for b in self.badges}

    def owned_item_ids(self) -> set[str]:
        return {i.item_id for i in self.items}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Child {self.id} {self.name!r} Y{self.year_group}>"


# ---------------------------------------------------------------------------
# Parent
# ---------------------------------------------------------------------------


class ParentAccount(db.Model):
    """A parent sign-in account that manages linked learner profiles."""

    __tablename__ = "parent_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login_name: Mapped[str] = mapped_column(
        String(80), default="parent", nullable=False, unique=True, index=True
    )
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bootstrap_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bootstrap_token_consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    parent_links: Mapped[list[ParentChild]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )

    def set_pin(self, pin: str) -> None:
        self.pin_hash = generate_password_hash(str(pin))
        self.auth_version = (self.auth_version or 1) + 1

    def check_pin(self, pin: str) -> bool:
        return check_password_hash(self.pin_hash, str(pin))

    @classmethod
    def get(cls) -> ParentAccount | None:
        return db.session.get(cls, 1)


class LearnerAccount(db.Model):
    """Credentials for one learner profile.

    Progress remains on ``Child``. This table only decides which learner may
    open that profile, so account changes never move or duplicate history.
    """

    __tablename__ = "learner_account"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    login_name: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, index=True
    )
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    needs_activation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    auth_nonce: Mapped[str] = mapped_column(
        String(64), default=_new_auth_nonce, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    child: Mapped[Child] = relationship(back_populates="learner_account")

    def set_pin(self, pin: str) -> None:
        self.pin_hash = generate_password_hash(str(pin))
        self.needs_activation = False
        self.auth_version += 1

    def check_pin(self, pin: str) -> bool:
        return (
            self.active
            and not self.needs_activation
            and bool(self.pin_hash)
            and check_password_hash(self.pin_hash, str(pin))
        )


class ParentChild(db.Model):
    """A parent account's permission to manage one learner profile."""

    __tablename__ = "parent_child"
    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", name="uq_parent_child"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("parent_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    parent: Mapped[ParentAccount] = relationship(back_populates="parent_links")
    child: Mapped[Child] = relationship(back_populates="parent_links")


class Settings(db.Model):
    """Per-child settings a parent controls."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    child: Mapped[Child] = relationship(back_populates="settings")

    # -- Session shape (the short-attention-span controls) ------------------
    quest_length: Mapped[int] = mapped_column(Integer, default=8)
    daily_limit_minutes: Mapped[int] = mapped_column(Integer, default=30)
    daily_quest_goal: Mapped[int] = mapped_column(Integer, default=3)
    break_after_minutes: Mapped[int] = mapped_column(Integer, default=12)

    # -- What to practise --------------------------------------------------
    subjects_enabled: Mapped[list] = mapped_column(
        JSON, default=lambda: ["maths", "english", "science"]
    )
    years_enabled: Mapped[list] = mapped_column(JSON, default=lambda: list(range(1, 7)))
    # Weighting between earlier revision and new work for the enabled years.
    year_mix: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"1": 15, "2": 35, "3": 50}
    )
    difficulty_mode: Mapped[str] = mapped_column(String(20), default="adaptive")
    focus_skills: Mapped[list] = mapped_column(JSON, default=list)
    # Explicit pathway selector. "off" keeps existing primary-only behaviour;
    # Foundation and Higher are independent of adaptive/gentle/challenge difficulty.
    gcse_tier: Mapped[str] = mapped_column(String(20), default="off", nullable=False)
    # Exam-board presentation only. Skill ids and tier authorization remain
    # board-neutral so changing this never duplicates or widens mastery.
    gcse_board: Mapped[str] = mapped_column(String(20), default="generic", nullable=False)

    # -- Help and feedback -------------------------------------------------
    allow_hints: Mapped[bool] = mapped_column(Boolean, default=True)
    second_chance: Mapped[bool] = mapped_column(Boolean, default=True)
    show_explanations: Mapped[bool] = mapped_column(Boolean, default=True)
    # Evidence-based GREAT mode asks for stage responses which a parent can
    # review. It is off by default because it makes a quest longer.
    great_diagnostic: Mapped[bool] = mapped_column(Boolean, default=False)

    # -- Comfort and accessibility -----------------------------------------
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    animations_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    read_aloud: Mapped[bool] = mapped_column(Boolean, default=True)
    read_aloud_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    dyslexia_font: Mapped[bool] = mapped_column(Boolean, default=False)
    large_text: Mapped[bool] = mapped_column(Boolean, default=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    show_timer: Mapped[bool] = mapped_column(Boolean, default=False)

    # -- Motivation --------------------------------------------------------
    shop_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_quest_goal: Mapped[int] = mapped_column(Integer, default=18)
    reward_note: Mapped[str] = mapped_column(Text, default="")
    cheer_note: Mapped[str] = mapped_column(Text, default="")

    # -- When the app may be used ------------------------------------------
    # Both zero means "any time". Off by default: a parent trying the app at
    # nine in the evening should not meet a locked door, and the daily time
    # limit is the more useful lever anyway.
    allowed_from_hour: Mapped[int] = mapped_column(Integer, default=0)
    allowed_to_hour: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    # -- Helpers -----------------------------------------------------------
    def year_weights(self) -> dict[int, int]:
        """Normalised {year: weight} limited to the years a parent enabled."""
        enabled = {int(y) for y in (self.years_enabled or range(1, 7))}
        raw = self.year_mix or {}
        out: dict[int, int] = {}
        for year in sorted(enabled):
            out[year] = max(0, int(raw.get(str(year), raw.get(year, 0)) or 0))
        if not out or sum(out.values()) == 0:
            out = dict.fromkeys(sorted(enabled) or [3], 1)
        return out

    def within_allowed_hours(self, at: datetime | None = None) -> bool:
        at = at or now()
        start, end = self.allowed_from_hour, self.allowed_to_hour
        if start == end:
            return True
        if start < end:
            return start <= at.hour < end
        return at.hour >= start or at.hour < end  # window crosses midnight


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


class SkillProgress(db.Model):
    """One row per (child, skill). Drives adaptive practice and the parent view.

    ``box`` is a Leitner-style spaced-repetition box:
        0 = brand new / just got it wrong   -> review today
        1 = review tomorrow
        2 = 3 days      3 = 7 days
        4 = 16 days     5 = 35 days (mastered)
    """

    __tablename__ = "skill_progress"
    __table_args__ = (UniqueConstraint("child_id", "skill_id", name="uq_child_skill"),)

    BOX_INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 16, 5: 35}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child: Mapped[Child] = relationship(back_populates="progress")

    skill_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)

    mastery: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 - 1.0
    box: Mapped[int] = mapped_column(Integer, default=0)
    due_on: Mapped[date] = mapped_column(Date, default=today)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_seconds: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def accuracy(self) -> float:
        return (self.correct / self.attempts) if self.attempts else 0.0

    @property
    def accuracy_pct(self) -> int:
        return round(self.accuracy * 100)

    @property
    def mastery_pct(self) -> int:
        return round(self.mastery * 100)

    @property
    def stage(self) -> str:
        """Plain-English label used in the parent dashboard."""
        if self.attempts < 3:
            return "not started" if self.attempts == 0 else "just started"
        if self.mastery >= 0.85:
            return "mastered"
        if self.mastery >= 0.6:
            return "getting there"
        if self.mastery >= 0.35:
            return "needs practice"
        return "needs help"

    @property
    def is_due(self) -> bool:
        return self.due_on <= today()

    # Exponential moving average weights. LEARN_RATE is set so that five
    # correct answers in a row reach the 0.85 "mastered" mark: a child should
    # not need a fortnight of perfection to see a skill go green.
    LEARN_RATE = 0.35
    DECAY = 0.7

    def register(
        self,
        was_correct: bool,
        seconds: int = 0,
        on: date | None = None,
        at: datetime | None = None,
    ) -> None:
        """Update the row after one answered question.

        ``on`` and ``at`` exist so historical data can be replayed with the same
        rules the live app uses, rather than a second copy of this logic.
        """
        on = on or today()
        self.attempts += 1
        self.total_seconds += max(0, min(seconds, 600))
        self.last_seen_at = at or now()

        if was_correct:
            self.correct += 1
            self.current_streak += 1
            self.best_streak = max(self.best_streak, self.current_streak)
            # Move up a box, but only once the answer is not a fluke.
            if self.current_streak >= 2 or self.box == 0:
                self.box = min(5, self.box + 1)
            self.mastery = round(
                min(1.0, self.mastery * self.DECAY + self.LEARN_RATE), 4
            )
        else:
            self.current_streak = 0
            self.box = max(0, self.box - 2)
            self.mastery = round(max(0.0, self.mastery * self.DECAY), 4)

        self.due_on = on + timedelta(days=self.BOX_INTERVALS[self.box])


class DailyActivity(db.Model):
    """Per-day rollup: powers time limits, streaks and the parent charts."""

    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("child_id", "on_date", name="uq_child_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child: Mapped[Child] = relationship(back_populates="activity")

    on_date: Mapped[date] = mapped_column(Date, default=today, nullable=False, index=True)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    questions: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    quests: Mapped[int] = mapped_column(Integer, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def minutes(self) -> int:
        return round(self.seconds / 60)

    @property
    def accuracy_pct(self) -> int:
        return round(self.correct / self.questions * 100) if self.questions else 0


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------


class Quest(db.Model):
    __tablename__ = "quest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child: Mapped[Child] = relationship(back_populates="quests")

    subject: Mapped[str] = mapped_column(String(30), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), default="mixed")
    skill_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(120), default="Quest")

    target_count: Mapped[int] = mapped_column(Integer, default=8)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)

    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    coins_earned: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    seconds: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list[QuestQuestion]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="QuestQuestion.position",
    )

    @property
    def is_finished(self) -> bool:
        return self.finished_at is not None

    @property
    def accuracy_pct(self) -> int:
        return round(self.correct_count / self.answered_count * 100) if self.answered_count else 0

    @property
    def minutes(self) -> float:
        return round(self.seconds / 60, 1)


class QuestQuestion(db.Model):
    __tablename__ = "quest_question"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quest_id: Mapped[int] = mapped_column(
        ForeignKey("quest.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quest: Mapped[Quest] = relationship(back_populates="questions")

    position: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), default="choice")
    difficulty_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Everything shown to the child (prompt, choices, visual, response spec).
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    # The correct answer, private rubric and explanations. Never sent to the
    # browser before a child has answered; manual rubrics stay private until a
    # parent opens the review page.
    solution: Mapped[dict] = mapped_column(JSON, default=dict)

    given_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_status: Mapped[str] = mapped_column(
        String(20), default="unanswered", nullable=False
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_json: Mapped[dict] = mapped_column(JSON, default=dict)
    tries: Mapped[int] = mapped_column(Integer, default=0)
    used_hint: Mapped[bool] = mapped_column(Boolean, default=False)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_answered(self) -> bool:
        """Whether a legacy answer or a rich response has been submitted."""
        return self.is_correct is not None or self.response_status != "unanswered"

    @property
    def is_pending(self) -> bool:
        return self.response_status == "submitted" and self.is_correct is None

    @property
    def is_scored(self) -> bool:
        return self.is_correct is not None

    def public(self) -> dict:
        """The safe-to-send view of this question.

        ``correct`` is included for questions already answered so that a
        resumed quest can repaint its progress dots with the real outcome. The
        correct answer text itself is never included.
        """
        data = dict(self.payload or {})
        data.update(
            {
                "id": self.id,
                "position": self.position,
                "skill_id": self.skill_id,
                "kind": self.kind,
                "answered": self.is_answered,
                "status": self.response_status,
                "pending": self.is_pending,
                "correct": self.is_correct,
                "score": self.score,
                "max_score": self.max_score,
                # GREAT lives in the server-only solution JSON; expose only
                # whether a reflection exists so a resumed player can know it
                # has already been recorded.
                "great_assessed": bool(
                    isinstance((self.solution or {}).get("great"), dict)
                    and isinstance((self.solution or {}).get("great", {}).get("scores"), dict)
                ),
                "great_diagnostic_submitted": bool(
                    isinstance((self.solution or {}).get("great_diagnostic"), dict)
                    and isinstance(
                        (self.solution or {}).get("great_diagnostic", {}).get("responses"), dict
                    )
                ),
            }
        )
        data.pop("answer", None)
        data.pop("accept", None)
        data.pop("explain", None)
        data.pop("great_rubric", None)
        data.pop("response_answer", None)
        return data


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------


class BadgeAward(db.Model):
    __tablename__ = "badge_award"
    __table_args__ = (UniqueConstraint("child_id", "badge_id", name="uq_child_badge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child: Mapped[Child] = relationship(back_populates="badges")
    badge_id: Mapped[str] = mapped_column(String(60), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OwnedItem(db.Model):
    """Something bought from the coin shop (avatar hats, pets, scenes)."""

    __tablename__ = "owned_item"
    __table_args__ = (UniqueConstraint("child_id", "item_id", name="uq_child_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child: Mapped[Child] = relationship(back_populates="items")
    item_id: Mapped[str] = mapped_column(String(40), nullable=False)
    bought_at: Mapped[datetime] = mapped_column(DateTime, default=now)
