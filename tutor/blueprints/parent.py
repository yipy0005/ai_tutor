"""The parent area: progress monitoring, activity history and settings.

Protected by a PIN rather than a full login, because the realistic threat model
is a curious seven-year-old, not the internet. The PIN is stored hashed, attempts
are rate limited, and the session times out after an hour of inactivity.
"""

from __future__ import annotations

import time
from functools import wraps

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
from ..config import Config
from ..content import (
    PATHWAY_SUBJECT_ORDER,
    SUBJECT_ORDER,
    SUBJECTS,
    subject_counts,
)
from ..extensions import db
from ..services import (
    auth,
    maintenance,
    pathways,
    profiles,
    quests,
    rewards,
    scheduler,
    stats,
)

bp = Blueprint("parent", __name__, url_prefix="/parent")

SESSION_MAX_IDLE = 60 * 60  # one hour
MAX_PIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@bp.before_app_request
def load_parent() -> None:
    """Resolve the parent account bound to this browser session."""
    g.parent_account = None
    account = profiles.get_parent_account(session.get(auth.PARENT_ACCOUNT_KEY))
    if account is None or (
        session.get("parent_ok")
        and session.get(auth.PARENT_AUTH_VERSION_KEY) != account.auth_version
    ):
        if account is not None or session.get("parent_ok"):
            auth.parent_logout()
        return
    g.parent_account = account


def parent_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        stamp = session.get("parent_ok_at", 0)
        if (
            not session.get("parent_ok")
            or g.parent_account is None
            or not g.parent_account.setup_complete
            or session.get(auth.PARENT_AUTH_VERSION_KEY) != g.parent_account.auth_version
            or time.time() - stamp > SESSION_MAX_IDLE
        ):
            auth.parent_logout()
            session["parent_next"] = request.full_path
            return redirect(url_for("parent.login"))
        session["parent_ok_at"] = time.time()
        return view(*args, **kwargs)

    return wrapper


def _viewed_child():
    """Which child this authenticated parent is looking at."""
    parent_id = g.parent_account.id if g.parent_account else None
    children = profiles.children_for_parent(parent_id)
    if not children:
        session.pop("parent_child_id", None)
        return None, []

    chosen_id = session.get("parent_child_id") or (g.child.id if g.child else None)
    chosen = profiles.get_child_for_parent(parent_id, chosen_id)
    if chosen is None:
        chosen = children[0]
    session["parent_child_id"] = chosen.id
    return chosen, children


def _owned_child(child_id: int):
    parent_id = g.parent_account.id if g.parent_account else None
    return profiles.get_child_for_parent(parent_id, child_id)


def _lockout_left() -> int:
    until = session.get("pin_lock_until", 0)
    return max(0, int(until - time.time()))


# ---------------------------------------------------------------------------
# Initial adult setup
# ---------------------------------------------------------------------------


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Configure the canonical parent account before the first learner."""
    if profiles.all_children():
        return redirect(url_for("parent.login"))

    account = profiles.ensure_parent_account()
    if account.setup_complete:
        return redirect(url_for("kid.welcome"))

    token_required = profiles.parent_setup_token_required(
        request.remote_addr,
        request.host,
    )
    if request.method == "POST":
        token = (request.form.get("bootstrap_token") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        confirm = (request.form.get("confirm_pin") or "").strip()
        if pin != confirm:
            flash("The two parent PINs did not match.", "error")
        else:
            try:
                account = profiles.complete_parent_setup(
                    token,
                    pin,
                    require_token=token_required,
                )
                db.session.commit()
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            else:
                profiles.remove_bootstrap_token_file()
                auth.parent_login(account)
                auth.grant_first_learner_capability(account)
                flash("Parent access is ready. Now create the first learner.", "success")
                return redirect(url_for("kid.welcome"))

    return render_template(
        "parent/setup.html",
        token_required=token_required,
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@bp.route("/login", methods=["GET", "POST"])
def login():
    default_account = profiles.ensure_parent_account()
    db.session.commit()

    if profiles.parent_setup_required():
        return redirect(url_for("parent.setup"))

    login_name = request.form.get("login_name") or default_account.login_name
    locked = _lockout_left()
    if request.method == "POST" and not locked:
        pin = (request.form.get("pin") or "").strip()
        account = profiles.find_parent_account(login_name)
        if account is not None and account.setup_complete and account.check_pin(pin):
            auth.parent_login(account)
            has_children = bool(profiles.all_children())
            if not has_children:
                auth.grant_first_learner_capability(account)
            target = session.pop("parent_next", None)
            return redirect(
                target
                or (url_for("kid.welcome") if not has_children else url_for("parent.dashboard"))
            )

        fails = session.get("pin_fails", 0) + 1
        session["pin_fails"] = fails
        if fails >= MAX_PIN_ATTEMPTS:
            session["pin_lock_until"] = time.time() + LOCKOUT_SECONDS
            session["pin_fails"] = 0
            flash("Too many tries. Please wait 5 minutes.", "error")
        else:
            flash(
                f"That parent name or PIN is not right. {MAX_PIN_ATTEMPTS - fails} tries left.",
                "error",
            )
        locked = _lockout_left()

    return render_template(
        "parent/login.html", locked=locked, login_name=login_name
    )


@bp.route("/register", methods=["GET", "POST"])
def register():
    if profiles.parent_setup_required():
        return redirect(url_for("parent.setup"))

    if request.method == "POST":
        login_name = request.form.get("login_name") or ""
        pin = (request.form.get("pin") or "").strip()
        confirm = (request.form.get("confirm_pin") or "").strip()
        if pin != confirm:
            flash("The two parent PINs did not match.", "error")
        else:
            try:
                account = profiles.create_parent_account(login_name, pin)
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            else:
                db.session.commit()
                auth.parent_login(account)
                flash("Parent account created.", "success")
                return redirect(url_for("parent.children_page"))
    return render_template("parent/register.html")


@bp.post("/logout")
def logout():
    auth.parent_logout()
    flash("Parent area locked.", "info")
    return redirect(url_for("kid.index"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@bp.route("/")
@parent_required
def dashboard():
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))

    return render_template(
        "parent/dashboard.html",
        view_child=child,
        children=children,
        overview=stats.overview(child),
        subjects=stats.subject_breakdown(child.id),
        years=stats.year_breakdown(child.id),
        minutes=stats.minutes_chart(child.id, 14),
        accuracy=stats.accuracy_chart(child.id, 14),
        heat=stats.heatmap(child.id, 10),
        attention=stats.attention_list(child.id, 6),
        wins=stats.wins_list(child.id, 6),
        recent=quests.recent_quests(child.id, 8),
        time_split=stats.subject_time_split(child.id),
        allowance=quests.allowance(child),
        flame=rewards.streak_flame(child.streak_days),
    )


@bp.post("/view/<int:child_id>")
@parent_required
def view_child(child_id: int):
    child = _owned_child(child_id)
    if child is not None:
        session["parent_child_id"] = child.id
    return redirect(request.referrer or url_for("parent.dashboard"))


# ---------------------------------------------------------------------------
# Progress detail
# ---------------------------------------------------------------------------


@bp.route("/progress")
@bp.route("/progress/<subject>")
@parent_required
def progress(subject: str | None = None):
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))
    subject = subject if subject in SUBJECTS else SUBJECT_ORDER[0]
    phonics_mode = request.args.get("mode") == "phonics" and subject == "english"
    if pathways.is_gcse(child.settings):
        selected = pathways.gcse_subject(child.settings)
        if subject != selected:
            return redirect(url_for("parent.progress", subject=selected))
    elif subject in PATHWAY_SUBJECT_ORDER:
        subject = SUBJECT_ORDER[0]

    return render_template(
        "parent/progress.html",
        view_child=child,
        children=children,
        subject=SUBJECTS[subject],
        subject_id=subject,
        groups=stats.skill_matrix(
            child.id,
            subject,
            tier=child.settings.gcse_tier,
            phonics_only=phonics_mode,
        ),
        counts=subject_counts().get(subject, {}),
        focus_skills=set(child.settings.focus_skills or []),
        phonics_mode=phonics_mode,
    )


@bp.post("/focus")
@parent_required
def toggle_focus():
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))
    skill_id = request.form.get("skill_id") or ""
    from ..content import SKILLS_BY_ID

    skill = SKILLS_BY_ID.get(skill_id)
    if skill and skill.id in pathways.active_skill_ids(child.settings):
        current = list(child.settings.focus_skills or [])
        if skill_id in current:
            current.remove(skill_id)
            message = "Removed from the focus list."
        else:
            current.append(skill_id)
            message = "Added to the focus list — it will come up more often."
        child.settings.focus_skills = current[:20]
        db.session.commit()
        flash(message, "success")
    return redirect(request.referrer or url_for("parent.progress"))


# ---------------------------------------------------------------------------
# Activity history
# ---------------------------------------------------------------------------


@bp.route("/activity")
@parent_required
def activity():
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))
    return render_template(
        "parent/activity.html",
        view_child=child,
        children=children,
        series=list(reversed(stats.daily_series(child.id, 28))),
        heat=stats.heatmap(child.id, 12),
        recent=quests.recent_quests(child.id, 40),
        mistakes=stats.recent_mistakes(child.id, 15),
    )


@bp.route("/quest/<int:quest_id>")
@parent_required
def quest_detail(quest_id: int):
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))
    detail = stats.quest_detail(child.id, quest_id)
    if detail is None:
        flash("That quest could not be found for this learner.", "error")
        return redirect(url_for("parent.activity"))
    return render_template(
        "parent/quest.html", view_child=child, children=children, **detail
    )


@bp.post("/quest/<int:quest_id>/great-review")
@parent_required
def great_review(quest_id: int):
    """Save the parent's 0/1/2 judgement for submitted child evidence."""
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))

    question_id = request.form.get("question_id", type=int)
    scores = {
        stage: request.form.get(f"score_{stage}", type=int)
        for stage in "GREAT"
    }
    result = quests.record_great_review(child, quest_id, question_id, scores)
    if result.get("error"):
        flash(result["error"], "error")
        target = url_for("parent.quest_detail", quest_id=quest_id)
        return redirect(target + (f"#question-{question_id}" if question_id else ""))

    flash("GREAT evidence review saved.", "success")
    next_interview = next(iter(stats.pending_great_interviews(child)), None)
    if next_interview is not None:
        target = url_for(
            "parent.quest_detail",
            quest_id=next_interview["quest_id"],
            _anchor=f"question-{next_interview['question_id']}",
        )
        return redirect(target)
    return redirect(url_for("parent.dashboard"))


@bp.post("/quest/<int:quest_id>/assessment-review")
@parent_required
def assessment_review(quest_id: int):
    """Save a rubric review for a submitted open-ended response."""
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))
    question_id = request.form.get("question_id", type=int)
    scores = {
        key[6:]: request.form.get(key, type=int)
        for key in request.form
        if key.startswith("score_")
    }
    feedback = request.form.get("feedback", "")
    result = quests.record_assessment_review(
        child, quest_id, question_id, scores, feedback
    )
    if result.get("error"):
        flash(result["error"], "error")
    else:
        flash("Open-ended response review saved.", "success")
    target = url_for("parent.quest_detail", quest_id=quest_id)
    return redirect(target + (f"#question-{question_id}" if question_id else ""))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@bp.route("/settings", methods=["GET", "POST"])
@parent_required
def settings_page():
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))

    if request.method == "POST":
        warnings = profiles.apply_settings(child.settings, request.form)
        db.session.commit()
        for warning in warnings:
            flash(warning, "info")
        flash("Settings saved.", "success")
        return redirect(url_for("parent.settings_page"))

    weak = scheduler.weak_skills(child.id, 20)
    active = pathways.active_skills(child.settings)
    return render_template(
        "parent/settings.html",
        view_child=child,
        children=children,
        modes=profiles.DIFFICULTY_MODES,
        gcse_tier_options=profiles.GCSE_TIER_OPTIONS,
        gcse_subject_options=profiles.GCSE_SUBJECT_OPTIONS,
        gcse_board_options=profiles.GCSE_BOARD_OPTIONS,
        summary=profiles.settings_summary(child.settings),
        suggested_focus=weak,
        all_skills=active,
        focus_skills=set(child.settings.focus_skills or []),
        pathway_is_gcse=pathways.is_gcse(child.settings),
        primary_years=tuple(range(1, 7)),
    )


@bp.post("/pin")
@parent_required
def change_pin():
    account = g.parent_account
    current = (request.form.get("current_pin") or "").strip()
    new = (request.form.get("new_pin") or "").strip()
    confirm = (request.form.get("confirm_pin") or "").strip()

    if account is None or not account.check_pin(current):
        flash("Your current PIN was not correct.", "error")
    elif not new.isdigit() or not 4 <= len(new) <= 8:
        flash("The new PIN needs to be 4 to 8 digits.", "error")
    elif new != confirm:
        flash("The two new PINs did not match.", "error")
    else:
        account.set_pin(new)
        db.session.commit()
        flash("PIN updated.", "success")
    return redirect(url_for("parent.settings_page"))


# ---------------------------------------------------------------------------
# Learner profiles
# ---------------------------------------------------------------------------


@bp.route("/children", methods=["GET", "POST"])
@parent_required
def children_page():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        year = request.form.get("year_group") or "3"
        emoji = request.form.get("avatar_character") or "fox"
        colour = request.form.get("avatar_colour") or "sunshine"
        gcse_tier = (request.form.get("gcse_tier") or "off").strip().lower()
        gcse_subject = (request.form.get("gcse_subject") or "gcse_maths").strip().lower()
        login_name = request.form.get("login_name")
        learner_pin = (request.form.get("learner_pin") or "").strip()
        if gcse_tier not in profiles.GCSE_TIER_OPTIONS:
            gcse_tier = "off"
        if gcse_subject not in profiles.GCSE_SUBJECT_OPTIONS:
            gcse_subject = "gcse_maths"
        try:
            year_number = int(year)
        except (TypeError, ValueError):
            year_number = 3
        if gcse_tier != "off":
            # Child.year_group remains a required legacy numeric field; GCSE
            # display and scheduling use Settings.gcse_tier instead.
            year_number = 6
        if not name:
            flash("Please enter a name.", "error")
        else:
            try:
                child = profiles.create_child(
                    name,
                    year_number,
                    emoji,
                    colour,
                    gcse_tier=gcse_tier,
                    gcse_subject=gcse_subject,
                    learner_login=login_name,
                    learner_pin=profiles.validate_pin(
                        learner_pin, required=True, label="learner"
                    ),
                )
                profiles.link_parent_child(g.parent_account.id, child.id)
                db.session.commit()
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            else:
                flash(f"{child.name} added.", "success")
        return redirect(url_for("parent.children_page"))

    child, children = _viewed_child()
    rows = []
    for candidate in children:
        rows.append(
            {
                "child": candidate,
                "totals": quests.lifetime_totals(candidate.id),
                "overview": stats.overview(candidate),
            }
        )
    return render_template(
        "parent/children.html",
        view_child=child,
        children=children,
        rows=rows,
        characters=art.CHARACTERS,
        colours=rewards.AVATAR_COLOURS,
        gcse_subject_options=profiles.GCSE_SUBJECT_OPTIONS,
    )


@bp.post("/children/<int:child_id>/update")
@parent_required
def update_child(child_id: int):
    child = _owned_child(child_id)
    if child is None:
        flash("That profile is not managed by this parent.", "error")
        return redirect(url_for("parent.children_page"))
    name = (request.form.get("name") or "").strip()
    login_name = request.form.get("login_name")
    learner_pin = (request.form.get("learner_pin") or "").strip()
    try:
        if login_name is not None:
            profiles.update_learner_credentials(
                child, login_name, learner_pin or None
            )
        elif learner_pin:
            account = child.learner_account
            if account is None:
                account = profiles.provision_learner_account(child)
            profiles.update_learner_credentials(child, account.login_name, learner_pin)
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("parent.children_page"))

    if name:
        child.name = name[:60]
    tier = request.form.get("gcse_tier")
    if tier is not None:
        tier = tier.strip().lower()
        if tier in profiles.GCSE_TIER_OPTIONS:
            child.settings.gcse_tier = tier
    subject = request.form.get("gcse_subject")
    if subject is not None:
        subject = subject.strip().lower()
        if subject in profiles.GCSE_SUBJECT_OPTIONS:
            child.settings.gcse_subject = subject
    year = request.form.get("year_group")
    if child.settings.gcse_tier in profiles.GCSE_TIER_OPTIONS and child.settings.gcse_tier != "off":
        child.year_group = 6
    elif year and year.isdigit():
        child.year_group = max(1, min(6, int(year)))
    db.session.commit()
    flash("Profile and learner access updated.", "success")
    return redirect(url_for("parent.children_page"))


@bp.post("/children/<int:child_id>/delete")
@parent_required
def delete_child(child_id: int):
    child = _owned_child(child_id)
    if child is None:
        flash("That profile is not managed by this parent.", "error")
        return redirect(url_for("parent.children_page"))
    if not _confirmed(child):
        flash("Type the learner's name exactly to confirm deletion.", "error")
        return redirect(url_for("parent.children_page"))

    name = child.name
    if g.learner_account is not None and g.learner_account.child_id == child.id:
        auth.learner_logout()
    if session.get("parent_child_id") == child.id:
        session.pop("parent_child_id", None)
    profiles.delete_child(child)
    flash(f"{name} and all their progress were deleted.", "info")
    return redirect(url_for("parent.children_page"))


# ---------------------------------------------------------------------------
# Clearing and resetting data
# ---------------------------------------------------------------------------


def _confirmed(child) -> bool:
    """True when the parent typed the learner's name exactly.

    The field is deliberately not called "confirm": an input of that name inside
    a form shadows ``window.confirm`` in inline event handlers, which silently
    breaks the "are you sure?" prompt on exactly the forms that need it most.
    """
    typed = (request.form.get("confirm_name") or "").strip().lower()
    return typed == child.name.strip().lower()


@bp.route("/data")
@parent_required
def data_page():
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))
    return render_template(
        "parent/data.html",
        view_child=child,
        children=children,
        stored=maintenance.stored_summary(child),
        subjects=maintenance.subject_summary(child),
        quests=quests.recent_quests(child.id, 40),
        backups=maintenance.list_backups(),
        db_path=str(Config.DB_PATH),
    )


@bp.post("/data/quests/delete")
@parent_required
def delete_quests():
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))

    ids = []
    for raw in request.form.getlist("quest_ids"):
        if str(raw).isdigit():
            ids.append(int(raw))
    if not ids:
        flash("Tick at least one quest to remove.", "error")
        return redirect(url_for("parent.data_page"))

    result = maintenance.delete_quests(child, ids)
    if not result.get("removed"):
        flash("Those quests could not be found.", "error")
    else:
        flash(
            f"Removed {result['removed']} quest"
            f"{'' if result['removed'] == 1 else 's'} and recalculated "
            f"{child.name}'s progress from the {result['answers']} answers that remain.",
            "success",
        )
    return redirect(url_for("parent.data_page"))


@bp.post("/data/subject/<subject>/reset")
@parent_required
def reset_subject(subject: str):
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))
    if subject not in pathways.subject_ids(child.settings):
        flash("That subject is not available on this learner's pathway.", "error")
        return redirect(url_for("parent.data_page"))
    if not _confirmed(child):
        flash(f"Type “{child.name}” exactly to confirm the reset.", "error")
        return redirect(url_for("parent.data_page"))

    result = maintenance.reset_subject(child, subject)
    name = SUBJECTS[subject].name
    if result.get("removed"):
        flash(
            f"{name} has been reset for {child.name}: {result['removed']} answers cleared. "
            "Other subjects were left untouched.",
            "success",
        )
    elif result.get("skills_cleared"):
        flash(f"Cleared {result['skills_cleared']} unused {name} skill records.", "info")
    else:
        flash(f"There was no {name} progress to clear.", "info")
    return redirect(url_for("parent.data_page"))


@bp.post("/data/reset-all")
@parent_required
def reset_all():
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))
    if not _confirmed(child):
        flash(f"Type “{child.name}” exactly to confirm the reset.", "error")
        return redirect(url_for("parent.data_page"))

    keep = request.form.get("keep_purchases") in {"on", "1", "true"}
    result = maintenance.reset_all_progress(child, keep_purchases=keep)
    cleared = result["cleared"]
    flash(
        f"{child.name} is back to a clean slate: {cleared['quests']} quests and "
        f"{cleared['questions']} answers cleared. "
        + ("Shop items were kept. " if keep else "Shop items were also removed. ")
        + "Settings and the profile are unchanged.",
        "success",
    )
    return redirect(url_for("parent.data_page"))


@bp.post("/data/backup")
@parent_required
def make_backup():
    child, _ = _viewed_child()
    path = maintenance.backup_database("manual backup")
    if path is None:
        flash("There was no database to back up.", "error")
    else:
        flash(f"Backup saved as {path.name}.", "success")
    _ = child
    return redirect(url_for("parent.data_page"))


@bp.post("/data/backups/delete")
@parent_required
def remove_backup():
    name = request.form.get("name") or ""
    if maintenance.delete_backup(name):
        flash(f"Deleted backup {name}.", "info")
    else:
        flash("That backup could not be found.", "error")
    return redirect(url_for("parent.data_page"))


@bp.post("/children/<int:child_id>/reset-progress")
@parent_required
def reset_progress(child_id: int):
    """Kept for the link on the Learners page; the real tools live on /parent/data."""
    child = _owned_child(child_id)
    if child is None:
        return redirect(url_for("parent.children_page"))
    if not _confirmed(child):
        flash("Type the learner's name exactly to confirm the reset.", "error")
        return redirect(url_for("parent.children_page"))

    maintenance.reset_all_progress(child, keep_purchases=True)
    flash(f"{child.name}'s progress was reset. Shop items were kept.", "info")
    return redirect(url_for("parent.children_page"))


# ---------------------------------------------------------------------------
# Curriculum reference
# ---------------------------------------------------------------------------


@bp.route("/curriculum")
@parent_required
def curriculum():
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("parent.children_page"))
    from ..content import bank_size, topic_tree

    active_subjects = pathways.subject_ids(child.settings)
    active_years = set(pathways.year_ids(child.settings))
    sections = []
    for subject_id in active_subjects:
        groups = []
        tier = child.settings.gcse_tier if subject_id in PATHWAY_SUBJECT_ORDER else None
        for year, topic, skills in topic_tree(subject_id, tier):
            if subject_id not in PATHWAY_SUBJECT_ORDER and year not in active_years:
                continue
            groups.append(
                {
                    "year": year,
                    "topic": topic,
                    "skills": [
                        {
                            "skill": skill,
                            "questions": (
                                "generated"
                                if skill.source == "generated"
                                else str(bank_size(skill.id))
                            ),
                        }
                        for skill in skills
                    ],
                }
            )
        sections.append({"subject": SUBJECTS[subject_id], "groups": groups})
    total_skills = sum(
        len(pathways.active_skills(child.settings, subject_id))
        for subject_id in active_subjects
    )
    return render_template(
        "parent/curriculum.html",
        view_child=child,
        children=children,
        sections=sections,
        total_skills=total_skills,
        pathway_is_gcse=pathways.is_gcse(child.settings),
    )
