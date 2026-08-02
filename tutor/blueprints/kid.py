"""The child's side of the app: hub, subject pages, quest player, shop, badges."""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..content import SUBJECT_ORDER, SUBJECTS, skills_for, topic_tree
from ..extensions import db
from ..services import profiles, quests, rewards, scheduler

bp = Blueprint("kid", __name__)


# ---------------------------------------------------------------------------
# Request setup
# ---------------------------------------------------------------------------


@bp.before_app_request
def load_child() -> None:
    g.child = None
    child_id = session.get("child_id")
    if child_id:
        child = profiles.get_child(child_id)
        if child is not None:
            if child.settings is None:  # a profile created outside the app
                from ..models import Settings

                db.session.add(Settings(child_id=child.id))
                db.session.commit()
            g.child = child
        else:
            session.pop("child_id", None)


def _require_child():
    if g.child is None:
        return redirect(url_for("kid.pick"))
    return None


# ---------------------------------------------------------------------------
# Getting in
# ---------------------------------------------------------------------------


@bp.route("/")
def index():
    children = profiles.all_children()
    if not children:
        return redirect(url_for("kid.welcome"))
    if g.child is None:
        if len(children) == 1:
            session["child_id"] = children[0].id
            session.permanent = True
            return redirect(url_for("kid.home"))
        return redirect(url_for("kid.pick"))
    return redirect(url_for("kid.home"))


@bp.route("/welcome", methods=["GET", "POST"])
def welcome():
    """First run: create the first learner and set the parent PIN."""
    if profiles.all_children() and request.method == "GET":
        return redirect(url_for("kid.index"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        year = request.form.get("year_group") or "3"
        emoji = request.form.get("avatar_emoji") or "🦊"
        colour = request.form.get("avatar_colour") or "sunshine"
        pin = (request.form.get("pin") or "").strip()

        errors = []
        if not name:
            errors.append("Please enter a name.")
        if pin and (not pin.isdigit() or not 4 <= len(pin) <= 8):
            errors.append("The parent PIN needs to be 4 to 8 digits.")

        if errors:
            for message in errors:
                flash(message, "error")
        else:
            child = profiles.create_child(name, int(year), emoji, colour)
            # `pixi run setup` may already have created the parent account with
            # the default PIN, so set it explicitly rather than relying on the
            # create-if-missing path. Otherwise the PIN typed here is ignored.
            account = profiles.ensure_parent_account()
            if pin:
                account.set_pin(pin)
            db.session.commit()
            session["child_id"] = child.id
            session.permanent = True
            flash(f"Welcome, {child.name}! Let's get started.", "success")
            return redirect(url_for("kid.home"))

    return render_template(
        "kid/welcome.html",
        emojis=rewards.AVATAR_EMOJIS,
        colours=rewards.AVATAR_COLOURS,
        default_pin_hint=True,
    )


@bp.route("/pick")
def pick():
    children = profiles.all_children()
    if not children:
        return redirect(url_for("kid.welcome"))
    return render_template("kid/pick.html", children=children)


@bp.post("/pick/<int:child_id>")
def choose(child_id: int):
    child = profiles.get_child(child_id)
    if child is None:
        flash("That profile no longer exists.", "error")
        return redirect(url_for("kid.pick"))
    session["child_id"] = child.id
    session.permanent = True
    return redirect(url_for("kid.home"))


@bp.post("/switch")
def switch():
    session.pop("child_id", None)
    return redirect(url_for("kid.pick"))


# ---------------------------------------------------------------------------
# Home hub
# ---------------------------------------------------------------------------


@bp.route("/home")
def home():
    if (response := _require_child()) is not None:
        return response
    child = g.child
    settings = child.settings

    state = quests.allowance(child)
    blocked = quests.blocked_reason(child)

    enabled = [s for s in SUBJECT_ORDER if s in (settings.subjects_enabled or SUBJECT_ORDER)]
    subject_cards = []
    for subject_id in enabled:
        subject = SUBJECTS[subject_id]
        progress = scheduler.progress_map(child.id)
        skills = skills_for(subject_id, settings.years_enabled or [1, 2, 3])
        touched = sum(1 for s in skills if (p := progress.get(s.id)) and p.attempts)
        mastered = sum(
            1
            for s in skills
            if (p := progress.get(s.id)) and p.mastery >= 0.85 and p.attempts >= 4
        )
        subject_cards.append(
            {
                "subject": subject,
                "skills": len(skills),
                "touched": touched,
                "mastered": mastered,
                "pct": round(mastered / len(skills) * 100) if skills else 0,
            }
        )

    return render_template(
        "kid/home.html",
        state=state,
        blocked=blocked,
        subject_cards=subject_cards,
        open_quest=quests.open_quest(child),
        recent=quests.recent_quests(child.id, 4),
        totals=quests.lifetime_totals(child.id),
        due=scheduler.due_count(child.id),
        weak=scheduler.weak_skills(child.id, 3),
        flame=rewards.streak_flame(child.streak_days),
        hat=rewards.equipped_emoji(child, "hat"),
        pet=rewards.equipped_emoji(child, "pet"),
        scene=rewards.equipped_emoji(child, "scene"),
        badge_count=len(child.badges),
    )


@bp.route("/blocked")
def blocked():
    if (response := _require_child()) is not None:
        return response
    reason = quests.blocked_reason(g.child) or "All done for now."
    return render_template("kid/blocked.html", reason=reason, state=quests.allowance(g.child))


# ---------------------------------------------------------------------------
# Subject pages
# ---------------------------------------------------------------------------


@bp.route("/learn/<subject>")
def learn(subject: str):
    if (response := _require_child()) is not None:
        return response
    if subject not in SUBJECTS:
        return redirect(url_for("kid.home"))

    child = g.child
    settings = child.settings
    years = [int(y) for y in (settings.years_enabled or [1, 2, 3])]
    progress = scheduler.progress_map(child.id)

    groups = []
    for year, topic, skills in topic_tree(subject):
        if year not in years:
            continue
        entries = []
        for skill in skills:
            row = progress.get(skill.id)
            entries.append(
                {
                    "skill": skill,
                    "mastery": row.mastery_pct if row else 0,
                    "attempts": row.attempts if row else 0,
                    "stage": row.stage if row else "not started",
                    "due": bool(row and row.is_due and row.attempts),
                }
            )
        groups.append({"year": year, "topic": topic, "entries": entries})

    return render_template(
        "kid/learn.html",
        subject=SUBJECTS[subject],
        groups=groups,
        blocked=quests.blocked_reason(child),
        state=quests.allowance(child),
    )


# ---------------------------------------------------------------------------
# Quest player
# ---------------------------------------------------------------------------


@bp.route("/play/<int:quest_id>")
def play(quest_id: int):
    if (response := _require_child()) is not None:
        return response
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        flash("That quest could not be found.", "error")
        return redirect(url_for("kid.home"))
    if quest.is_finished:
        return redirect(url_for("kid.done", quest_id=quest.id))
    return render_template(
        "kid/play.html",
        quest=quest,
        payload=quests.quest_payload(quest, g.child),
        hat=rewards.equipped_emoji(g.child, "hat"),
    )


@bp.route("/done/<int:quest_id>")
def done(quest_id: int):
    if (response := _require_child()) is not None:
        return response
    quest = quests.get_quest(g.child, quest_id)
    if quest is None:
        return redirect(url_for("kid.home"))
    summary = quests.quest_summary(g.child, quest, [])
    return render_template("kid/done.html", quest=quest, summary=summary)


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------


@bp.route("/badges")
def badges():
    if (response := _require_child()) is not None:
        return response
    owned = {b.badge_id: b for b in g.child.badges}
    groups: dict[str, list] = {}
    for badge in rewards.BADGES:
        groups.setdefault(badge.group, []).append(
            {"badge": badge, "award": owned.get(badge.id)}
        )
    group_names = {
        "start": "Getting started",
        "streak": "Keeping it up",
        "skill": "Sharp thinking",
        "mastery": "Mastering skills",
        "subject": "Every subject",
        "ahead": "Year 3 ready",
        "fun": "Just for fun",
    }
    return render_template(
        "kid/badges.html",
        groups=groups,
        group_names=group_names,
        earned=len(owned),
        total=len(rewards.BADGES),
    )


@bp.route("/shop")
def shop():
    if (response := _require_child()) is not None:
        return response
    child = g.child
    if not child.settings.shop_enabled:
        flash("The shop is switched off at the moment.", "info")
        return redirect(url_for("kid.home"))
    owned = child.owned_item_ids()
    slots = {"hat": [], "pet": [], "scene": []}
    for item in rewards.SHOP_ITEMS:
        slots.setdefault(item.slot, []).append(
            {
                "item": item,
                "owned": item.id in owned,
                "affordable": child.coins >= item.cost,
                "equipped": item.id
                in {child.equipped_hat, child.equipped_pet, child.equipped_scene},
            }
        )
    return render_template("kid/shop.html", slots=slots)


@bp.post("/shop/buy")
def shop_buy():
    if (response := _require_child()) is not None:
        return response
    item_id = request.form.get("item_id") or ""
    ok, message = rewards.buy_item(g.child, item_id)
    db.session.commit()
    flash(message, "success" if ok else "error")
    return redirect(url_for("kid.shop"))


@bp.post("/shop/equip")
def shop_equip():
    if (response := _require_child()) is not None:
        return response
    item_id = request.form.get("item_id") or ""
    item = rewards.SHOP_BY_ID.get(item_id)
    if item and item_id in g.child.owned_item_ids():
        rewards.equip_item(g.child, item)
        db.session.commit()
        flash(f"{item.name} on!", "success")
    return redirect(url_for("kid.shop"))


@bp.post("/shop/remove")
def shop_remove():
    if (response := _require_child()) is not None:
        return response
    slot = request.form.get("slot") or ""
    if slot == "hat":
        g.child.equipped_hat = None
    elif slot == "pet":
        g.child.equipped_pet = None
    elif slot == "scene":
        g.child.equipped_scene = None
    db.session.commit()
    return redirect(url_for("kid.shop"))


@bp.route("/me", methods=["GET", "POST"])
def me():
    if (response := _require_child()) is not None:
        return response
    child = g.child
    if request.method == "POST":
        emoji = request.form.get("avatar_emoji")
        colour = request.form.get("avatar_colour")
        if emoji in rewards.AVATAR_EMOJIS:
            child.avatar_emoji = emoji
        if colour in {key for key, _ in rewards.AVATAR_COLOURS}:
            child.avatar_colour = colour
        db.session.commit()
        flash("Looking good!", "success")
        return redirect(url_for("kid.me"))

    return render_template(
        "kid/me.html",
        emojis=rewards.AVATAR_EMOJIS,
        colours=rewards.AVATAR_COLOURS,
        totals=quests.lifetime_totals(child.id),
        hat=rewards.equipped_emoji(child, "hat"),
        pet=rewards.equipped_emoji(child, "pet"),
        scene=rewards.equipped_emoji(child, "scene"),
        flame=rewards.streak_flame(child.streak_days),
    )
