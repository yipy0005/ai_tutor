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

from .. import art
from ..content import (
    GCSE_TIERS,
    PATHWAY_SUBJECT_ORDER,
    PRIMARY_YEARS,
    SUBJECTS,
    gcse_skills_for,
    phonics_stage_summary,
    skills_for,
    topic_tree,
)
from ..extensions import db
from ..services import auth, pathways, profiles, quests, rewards, scheduler

bp = Blueprint("kid", __name__)


# ---------------------------------------------------------------------------
# Request setup
# ---------------------------------------------------------------------------


@bp.before_app_request
def load_child() -> None:
    g.child = None
    g.learner_account = None
    # The legacy child_id key represented a selectable profile, not an
    # authenticated identity. Ignore and clear it so old cookies cannot select
    # another learner after the account boundary is enabled.
    session.pop("child_id", None)
    account_id = session.get(auth.LEARNER_ACCOUNT_KEY)
    account = profiles.get_learner_account(account_id)
    if account is None or not account.active or account.needs_activation:
        if account_id:
            auth.learner_logout()
        return
    if (
        session.get(auth.LEARNER_AUTH_VERSION_KEY) != account.auth_version
        or session.get(auth.LEARNER_AUTH_NONCE_KEY) != account.auth_nonce
    ):
        auth.learner_logout()
        return

    child = account.child
    if child is None:
        auth.learner_logout()
        return
    if child.settings is None:  # a profile created outside the app
        from ..models import Settings

        db.session.add(Settings(child_id=child.id))
        db.session.commit()
    g.learner_account = account
    g.child = child


def _require_child():
    if g.child is None:
        return redirect(url_for("kid.login", next=request.full_path))
    return None


@bp.route("/")
def index():
    if g.child is not None:
        return redirect(url_for("kid.home"))
    if not profiles.all_children():
        if profiles.parent_setup_required():
            return redirect(url_for("parent.setup"))
        return redirect(url_for("kid.welcome"))
    return redirect(url_for("kid.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.child is not None:
        return redirect(url_for("kid.home"))

    next_url = request.args.get("next") or request.form.get("next") or ""
    if request.method == "POST":
        login_name = profiles.normalize_login(request.form.get("login_name"))
        pin = (request.form.get("pin") or "").strip()
        account = profiles.find_learner_account(login_name)
        if account is not None and account.check_pin(pin):
            auth.learner_login(account)
            target = next_url if next_url.startswith("/") and not next_url.startswith("//") else ""
            return redirect(target or url_for("kid.home"))
        flash("That learner sign-in name or PIN was not recognised.", "error")

    return render_template("kid/login.html", next_url=next_url)


@bp.post("/logout")
def logout():
    auth.learner_logout()
    flash("You are signed out. Sign in again when you are ready to learn.", "info")
    return redirect(url_for("kid.login"))


# ---------------------------------------------------------------------------
# Getting in
# ---------------------------------------------------------------------------


@bp.route("/welcome", methods=["GET", "POST"])
def welcome():
    """First run: create the first learner after adult parent setup."""
    if profiles.all_children():
        return redirect(url_for("kid.index"))
    if profiles.parent_setup_required():
        return redirect(url_for("parent.setup"))

    parent = profiles.get_parent_account(session.get(auth.PARENT_ACCOUNT_KEY))
    if not auth.first_learner_capability_valid(parent):
        auth.clear_first_learner_capability()
        session["parent_next"] = request.full_path
        return redirect(url_for("parent.login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        learner_login = request.form.get("learner_login")
        learner_pin = (request.form.get("learner_pin") or "").strip()
        year = request.form.get("year_group") or "3"
        gcse_tier = (request.form.get("gcse_tier") or "off").strip().lower()
        gcse_subject = (request.form.get("gcse_subject") or "gcse_maths").strip().lower()
        if gcse_tier not in profiles.GCSE_TIER_OPTIONS:
            gcse_tier = "off"
        if gcse_subject not in profiles.GCSE_SUBJECT_OPTIONS:
            gcse_subject = "gcse_maths"
        emoji = request.form.get("avatar_character") or art.CHARACTERS[0].id
        colour = request.form.get("avatar_colour") or "sunshine"

        try:
            year_number = max(1, min(6, int(year)))
        except (TypeError, ValueError):
            year_number = 3
        if gcse_tier != "off":
            year_number = 6

        errors = []
        if not name:
            errors.append("Please enter a name.")
        if not profiles.normalize_login(learner_login):
            errors.append("Please choose a learner sign-in name.")
        if not learner_pin:
            errors.append("Please choose a learner PIN.")
        elif not learner_pin.isdigit() or not 4 <= len(learner_pin) <= 8:
            errors.append("The learner PIN needs to be 4 to 8 digits.")

        if errors:
            for message in errors:
                flash(message, "error")
        else:
            try:
                child = profiles.create_child(
                    name,
                    year_number,
                    emoji,
                    colour,
                    gcse_tier=gcse_tier,
                    gcse_subject=gcse_subject,
                    learner_login=learner_login,
                    learner_pin=learner_pin,
                )
                profiles.link_parent_child(parent.id, child.id)
                auth.learner_login(child.learner_account)
                db.session.commit()
                auth.consume_first_learner_capability(parent)
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            else:
                flash(f"Welcome, {child.name}! Let's get started.", "success")
                return redirect(url_for("kid.home"))

    return render_template(
        "kid/welcome.html",
        characters=art.CHARACTERS,
        colours=rewards.AVATAR_COLOURS,
        gcse_tier_options=profiles.GCSE_TIER_OPTIONS,
        gcse_subject_options=profiles.GCSE_SUBJECT_OPTIONS,
        primary_years=PRIMARY_YEARS,
    )


@bp.route("/pick")
def pick():
    """Compatibility endpoint: learner identity must come from sign-in."""
    return redirect(url_for("kid.login"))


@bp.post("/pick/<int:child_id>")
def choose(child_id: int):
    """Never select a learner from a posted profile id."""
    _ = child_id
    auth.learner_logout()
    flash("Sign in with your own learner name and PIN.", "info")
    return redirect(url_for("kid.login"))


@bp.post("/switch")
def switch():
    """Legacy compatibility endpoint: sign out instead of switching profiles."""
    auth.learner_logout()
    return redirect(url_for("kid.login"))


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

    enabled = pathways.subject_ids(settings)
    is_gcse = pathways.is_gcse(settings)
    primary_years = pathways.year_ids(settings)
    latest_year = max(primary_years)
    subject_cards = []
    for subject_id in enabled:
        subject = SUBJECTS[subject_id]
        progress = scheduler.progress_map(child.id)
        if subject_id in PATHWAY_SUBJECT_ORDER:
            skills = gcse_skills_for(subject_id, settings.gcse_tier)
        else:
            skills = skills_for(subject_id, primary_years)
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
                "tier": settings.gcse_tier if subject_id in PATHWAY_SUBJECT_ORDER else None,
            }
        )

    phonics_card = None
    if not is_gcse and "english" in enabled:
        phonics_progress = scheduler.progress_map(child.id)
        phonics_skills = [
            skill
            for skill in skills_for("english", primary_years)
            if skill.is_phonics
        ]
        phonics_mastered = sum(
            1
            for skill in phonics_skills
            if (row := phonics_progress.get(skill.id))
            and row.mastery >= 0.85
            and row.attempts >= 4
        )
        stage = phonics_stage_summary(phonics_progress)
        phonics_card = {
            "skills": len(phonics_skills),
            "mastered": phonics_mastered,
            "pct": round(phonics_mastered / len(phonics_skills) * 100)
            if phonics_skills
            else 0,
            "stage": stage["label"],
        }

    return render_template(
        "kid/home.html",
        state=state,
        blocked=blocked,
        subject_cards=subject_cards,
        phonics_card=phonics_card,
        open_quest=quests.open_quest(child),
        recent=quests.recent_quests(child.id, 4),
        totals=quests.lifetime_totals(child.id),
        due=scheduler.due_count(child.id),
        weak=scheduler.weak_skills(child.id, 3),
        pathway_is_gcse=is_gcse,
        latest_year=latest_year,
        flame=rewards.streak_flame(child.streak_days),
        hat=rewards.equipped_art(child, "hat"),
        pet=rewards.equipped_art(child, "pet"),
        scene=rewards.equipped_art(child, "scene"),
        badge_count=len(rewards.visible_badge_awards(child)),
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
    phonics_mode = request.args.get("mode") == "phonics"
    if phonics_mode and (subject != "english" or pathways.is_gcse(settings)):
        return redirect(url_for("kid.home"))
    if pathways.is_gcse(settings):
        if subject != pathways.gcse_subject(settings):
            return redirect(url_for("kid.home"))
    elif subject in PATHWAY_SUBJECT_ORDER:
        return redirect(url_for("kid.home"))
    progress = scheduler.progress_map(child.id)
    groups = []
    if subject in PATHWAY_SUBJECT_ORDER:
        if settings.gcse_tier not in GCSE_TIERS:
            return redirect(url_for("kid.home"))
        topic_groups = topic_tree(subject, settings.gcse_tier)
        for year, topic, skills in topic_groups:
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
    else:
        years = pathways.year_ids(settings)
        for year, topic, skills in topic_tree(subject):
            if year not in years:
                continue
            if phonics_mode:
                skills = tuple(skill for skill in skills if skill.is_phonics)
                if not skills:
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
        phonics_mode=phonics_mode,
        tier=settings.gcse_tier if subject in PATHWAY_SUBJECT_ORDER else None,
        latest_year=max(pathways.year_ids(settings)),
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
        hat=rewards.equipped_art(g.child, "hat"),
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
    owned = {b.badge_id: b for b in rewards.visible_badge_awards(g.child)}
    badges = rewards.visible_badges(g.child)
    visible_ids = {badge.id for badge in badges}
    groups: dict[str, list] = {}
    for badge in badges:
        groups.setdefault(badge.group, []).append(
            {"badge": badge, "award": owned.get(badge.id)}
        )
    group_names = {
        "start": "Getting started",
        "streak": "Keeping it up",
        "skill": "Sharp thinking",
        "mastery": "Mastering skills",
        "subject": "Every subject",
        "ahead": "Ahead",
        "fun": "Just for fun",
    }
    return render_template(
        "kid/badges.html",
        groups=groups,
        group_names=group_names,
        earned=len(set(owned) & visible_ids),
        total=len(badges),
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
        chosen = request.form.get("avatar_character")
        colour = request.form.get("avatar_colour")
        if chosen in art.CHARACTERS_BY_ID:
            child.avatar_emoji = chosen
        if colour in {key for key, _ in rewards.AVATAR_COLOURS}:
            child.avatar_colour = colour
        db.session.commit()
        flash("Looking good!", "success")
        return redirect(url_for("kid.me"))

    return render_template(
        "kid/me.html",
        characters=art.CHARACTERS,
        colours=rewards.AVATAR_COLOURS,
        totals=quests.lifetime_totals(child.id),
        hat=rewards.equipped_art(child, "hat"),
        pet=rewards.equipped_art(child, "pet"),
        scene=rewards.equipped_art(child, "scene"),
        flame=rewards.streak_flame(child.streak_days),
    )
