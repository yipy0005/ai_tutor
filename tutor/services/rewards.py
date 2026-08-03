"""Gamification: XP, coins, stars, streaks, badges and the coin shop.

The numbers here are deliberately generous. The goal is a child who finishes a
short quest and feels like coming back tomorrow, not a child grinding for a
reward. Everything is cosmetic — nothing here gates access to learning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select

from ..extensions import db
from ..models import BadgeAward, Child, DailyActivity, OwnedItem, Quest, SkillProgress

# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------

XP_FIRST_TRY = 10
XP_SECOND_TRY = 5
XP_FOR_TRYING = 2
XP_QUEST_BONUS = 15
XP_PER_STAR = 10

COINS_PER_CORRECT = 1
COINS_QUEST_BONUS = 3
COINS_PER_STAR = 2


def xp_for_answer(is_correct: bool, tries: int) -> int:
    """Effort always earns something. Getting it right first time earns most."""
    if not is_correct:
        return XP_FOR_TRYING
    return XP_FIRST_TRY if tries <= 1 else XP_SECOND_TRY


def stars_for(correct: int, total: int) -> int:
    """Finishing a quest is always worth at least one star."""
    if total <= 0:
        return 0
    pct = correct / total * 100
    if pct >= 90:
        return 3
    if pct >= 70:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------


def touch_streak(child: Child, on: date | None = None) -> bool:
    """Record activity for today and update the day streak.

    Returns True if this is the child's first activity today.
    """
    on = on or date.today()
    if child.last_active_on == on:
        return False

    if child.last_active_on == on - timedelta(days=1):
        child.streak_days += 1
    else:
        child.streak_days = 1
    child.best_streak = max(child.best_streak, child.streak_days)
    child.last_active_on = on
    return True


def streak_flame(days: int) -> str:
    if days >= 30:
        return "🌟"
    if days >= 14:
        return "💫"
    if days >= 7:
        return "🔥"
    if days >= 3:
        return "✨"
    return "🕯️"


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Badge:
    id: str
    name: str
    emoji: str
    description: str
    group: str = "general"

    @property
    def rosette(self) -> str:
        """The rosette artwork to draw behind this badge's emblem."""
        return f"rosette-{self.group}"


BADGES: list[Badge] = [
    Badge("first-quest", "First Steps", "👣", "Finish your very first quest", "start"),
    Badge("five-quests", "Getting Going", "🚀", "Finish 5 quests", "start"),
    Badge("twenty-quests", "Quest Hunter", "🗺️", "Finish 20 quests", "start"),
    Badge("fifty-quests", "Quest Legend", "🏆", "Finish 50 quests", "start"),
    Badge("hundred-quests", "Century Club", "💯", "Finish 100 quests", "start"),

    Badge("streak-3", "Three in a Row", "✨", "Practise 3 days in a row", "streak"),
    Badge("streak-7", "Week Warrior", "🔥", "Practise 7 days in a row", "streak"),
    Badge("streak-14", "Fortnight Hero", "💫", "Practise 14 days in a row", "streak"),
    Badge("streak-30", "Unstoppable", "🌟", "Practise 30 days in a row", "streak"),

    Badge("perfect-quest", "Full Marks", "🎯", "Get every question right in a quest", "skill"),
    Badge("three-perfect", "Sharp Shooter", "🏹", "Get full marks in 3 quests", "skill"),
    Badge("hundred-correct", "Century of Answers", "🧠", "Answer 100 questions correctly", "skill"),
    Badge("five-hundred-correct", "Super Brain", "🦉", "Answer 500 questions correctly", "skill"),

    Badge("master-5", "Skill Collector", "⭐", "Master 5 different skills", "mastery"),
    Badge("master-15", "Skill Champion", "🥇", "Master 15 different skills", "mastery"),
    Badge("master-30", "Skill Master", "👑", "Master 30 different skills", "mastery"),

    Badge("maths-10", "Number Cruncher", "🔢", "Finish 10 maths quests", "subject"),
    Badge("english-10", "Word Wizard", "📖", "Finish 10 English quests", "subject"),
    Badge("science-10", "Little Scientist", "🔬", "Finish 10 science quests", "subject"),
    Badge("all-subjects", "All Rounder", "🌈", "Finish a quest in every subject", "subject"),

    Badge("year3-ready", "Year 3 Ready", "🎓", "Master 10 Year 3 skills", "ahead"),
    Badge("revision-star", "Revision Star", "🔁", "Master 10 Year 1 or 2 skills", "ahead"),

    Badge("early-bird", "Early Bird", "🌅", "Finish a quest before 9am", "fun"),
    Badge("comeback", "Never Give Up", "💪", "Get a question right on your second try 10 times", "fun"),
]

BADGES_BY_ID = {b.id: b for b in BADGES}


def _count_quests(child_id: int, **filters) -> int:
    stmt = select(func.count(Quest.id)).where(
        Quest.child_id == child_id, Quest.finished_at.is_not(None)
    )
    for key, value in filters.items():
        stmt = stmt.where(getattr(Quest, key) == value)
    return db.session.execute(stmt).scalar_one()


def evaluate_badges(child: Child) -> list[Badge]:
    """Award any newly earned badges. Returns the badges earned just now."""
    already = child.badge_ids()
    earned: list[str] = []

    quests_done = _count_quests(child.id)
    if quests_done >= 1:
        earned.append("first-quest")
    if quests_done >= 5:
        earned.append("five-quests")
    if quests_done >= 20:
        earned.append("twenty-quests")
    if quests_done >= 50:
        earned.append("fifty-quests")
    if quests_done >= 100:
        earned.append("hundred-quests")

    if child.streak_days >= 3:
        earned.append("streak-3")
    if child.streak_days >= 7:
        earned.append("streak-7")
    if child.streak_days >= 14:
        earned.append("streak-14")
    if child.streak_days >= 30:
        earned.append("streak-30")

    perfect = db.session.execute(
        select(func.count(Quest.id)).where(
            Quest.child_id == child.id,
            Quest.finished_at.is_not(None),
            Quest.answered_count > 0,
            Quest.correct_count == Quest.answered_count,
        )
    ).scalar_one()
    if perfect >= 1:
        earned.append("perfect-quest")
    if perfect >= 3:
        earned.append("three-perfect")

    totals = db.session.execute(
        select(
            func.coalesce(func.sum(SkillProgress.correct), 0),
            func.coalesce(func.sum(SkillProgress.attempts), 0),
        ).where(SkillProgress.child_id == child.id)
    ).one()
    total_correct = int(totals[0] or 0)
    if total_correct >= 100:
        earned.append("hundred-correct")
    if total_correct >= 500:
        earned.append("five-hundred-correct")

    mastered_rows = db.session.execute(
        select(SkillProgress.skill_id).where(
            SkillProgress.child_id == child.id,
            SkillProgress.mastery >= 0.85,
            SkillProgress.attempts >= 4,
        )
    ).scalars().all()
    mastered = list(mastered_rows)
    if len(mastered) >= 5:
        earned.append("master-5")
    if len(mastered) >= 15:
        earned.append("master-15")
    if len(mastered) >= 30:
        earned.append("master-30")

    from ..content import get_skill  # local import avoids a cycle at start-up

    year3 = sum(1 for sid in mastered if (s := get_skill(sid)) and s.year == 3)
    lower = sum(1 for sid in mastered if (s := get_skill(sid)) and s.year in (1, 2))
    if year3 >= 10:
        earned.append("year3-ready")
    if lower >= 10:
        earned.append("revision-star")

    subjects_done = set()
    for subject in ("maths", "english", "science"):
        count = _count_quests(child.id, subject=subject)
        if count:
            subjects_done.add(subject)
        if count >= 10:
            earned.append(f"{subject}-10")
    if len(subjects_done) >= 3:
        earned.append("all-subjects")

    early = db.session.execute(
        select(func.count(Quest.id)).where(
            Quest.child_id == child.id,
            Quest.finished_at.is_not(None),
            func.strftime("%H", Quest.finished_at) < "09",
        )
    ).scalar_one()
    if early:
        earned.append("early-bird")

    from ..models import QuestQuestion

    comebacks = db.session.execute(
        select(func.count(QuestQuestion.id))
        .join(Quest, Quest.id == QuestQuestion.quest_id)
        .where(
            Quest.child_id == child.id,
            QuestQuestion.is_correct.is_(True),
            QuestQuestion.tries > 1,
        )
    ).scalar_one()
    if comebacks >= 10:
        earned.append("comeback")

    fresh: list[Badge] = []
    for badge_id in earned:
        if badge_id in already or badge_id not in BADGES_BY_ID:
            continue
        db.session.add(BadgeAward(child_id=child.id, badge_id=badge_id))
        already.add(badge_id)
        fresh.append(BADGES_BY_ID[badge_id])
    return fresh


# ---------------------------------------------------------------------------
# Coin shop — purely cosmetic avatar bits, no assets needed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShopItem:
    id: str
    name: str
    art: str          # symbol id in the artwork sprite
    cost: int
    slot: str         # "hat" | "pet" | "scene"


SHOP_ITEMS: list[ShopItem] = [
    ShopItem("hat-cap", "Baseball Cap", "hat-cap", 15, "hat"),
    ShopItem("hat-party", "Party Hat", "hat-party", 20, "hat"),
    ShopItem("hat-flower", "Flower Crown", "hat-flower", 30, "hat"),
    ShopItem("hat-wizard", "Wizard Hat", "hat-wizard", 45, "hat"),
    ShopItem("hat-crown", "Golden Crown", "hat-crown", 60, "hat"),
    ShopItem("hat-graduate", "Graduation Cap", "hat-graduate", 80, "hat"),

    # Pets are drawn from the same character family as the avatars, so a pet
    # looks like a smaller friend rather than a different art style.
    ShopItem("pet-cat", "Mitts the Kitten", "char-cat", 25, "pet"),
    ShopItem("pet-dog", "Bramble the Cub", "char-bear", 25, "pet"),
    ShopItem("pet-frog", "Hop the Frog", "char-frog", 35, "pet"),
    ShopItem("pet-penguin", "Puff the Penguin", "char-penguin", 40, "pet"),
    ShopItem("pet-owl", "Hoot the Owl", "char-owl", 55, "pet"),
    ShopItem("pet-hedgehog", "Prickle the Hedgehog", "char-hedgehog", 65, "pet"),
    ShopItem("pet-dragon", "Ember the Dragon", "char-dragon", 90, "pet"),
    ShopItem("pet-unicorn", "Twinkle the Unicorn", "char-unicorn", 100, "pet"),

    ShopItem("scene-rainbow", "Rainbow Meadow", "scene-rainbow", 40, "scene"),
    ShopItem("scene-beach", "Sunny Beach", "scene-beach", 50, "scene"),
    ShopItem("scene-forest", "Magic Forest", "scene-forest", 50, "scene"),
    ShopItem("scene-space", "Outer Space", "scene-space", 70, "scene"),
    ShopItem("scene-castle", "Castle", "scene-castle", 75, "scene"),
]

SHOP_BY_ID = {i.id: i for i in SHOP_ITEMS}

AVATAR_COLOURS = [
    ("sunshine", "Sunshine"),
    ("berry", "Berry"),
    ("ocean", "Ocean"),
    ("leaf", "Leaf"),
    ("grape", "Grape"),
    ("peach", "Peach"),
]


def buy_item(child: Child, item_id: str) -> tuple[bool, str]:
    """Spend coins on a cosmetic item. Returns (success, message)."""
    item = SHOP_BY_ID.get(item_id)
    if item is None:
        return False, "That item does not exist."
    if item_id in child.owned_item_ids():
        return False, "You already own that."
    if child.coins < item.cost:
        return False, f"You need {item.cost - child.coins} more coins."

    child.coins -= item.cost
    db.session.add(OwnedItem(child_id=child.id, item_id=item_id))
    equip_item(child, item)
    return True, f"{item.name} is yours!"


def equip_item(child: Child, item: ShopItem) -> None:
    if item.slot == "hat":
        child.equipped_hat = item.id
    elif item.slot == "pet":
        child.equipped_pet = item.id
    elif item.slot == "scene":
        child.equipped_scene = item.id


def equipped_art(child: Child, slot: str) -> str:
    """The sprite symbol id for whatever is equipped in a slot, or ""."""
    item_id = {
        "hat": child.equipped_hat,
        "pet": child.equipped_pet,
        "scene": child.equipped_scene,
    }.get(slot)
    item = SHOP_BY_ID.get(item_id or "")
    return item.art if item else ""


# ---------------------------------------------------------------------------
# Encouragement
# ---------------------------------------------------------------------------

CHEERS_CORRECT = [
    "Brilliant!", "Spot on!", "Nice one!", "You got it!", "Excellent!",
    "Well done!", "Perfect!", "Great thinking!", "Yes!", "Superb!",
]
CHEERS_RETRY = [
    "Not quite — have another go.",
    "Close! Try once more.",
    "Nearly. Give it another try.",
    "Have another think.",
]
CHEERS_WRONG = [
    "Good try. Here's how it works.",
    "That one was tricky. Let's look at it.",
    "No worries — mistakes help us learn.",
    "Nearly! Take a look at the answer.",
]
QUEST_END = {
    3: ["Amazing work!", "You smashed it!", "Superstar!"],
    2: ["Great effort!", "Really good work!", "Nicely done!"],
    1: ["Well done for finishing!", "Good effort — keep going!", "You did it!"],
    0: ["Thanks for having a go!"],
}


def day_progress(child: Child) -> DailyActivity | None:
    return db.session.execute(
        select(DailyActivity).where(
            DailyActivity.child_id == child.id, DailyActivity.on_date == date.today()
        )
    ).scalar_one_or_none()
