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
from ..content import ALL_SKILLS, SUBJECT_ORDER, SUBJECTS, subject_counts
from ..extensions import db
from ..models import ParentAccount
from ..services import maintenance, profiles, quests, rewards, scheduler, stats

bp = Blueprint("parent", __name__, url_prefix="/parent")

SESSION_MAX_IDLE = 60 * 60  # one hour
MAX_PIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def parent_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        stamp = session.get("parent_ok_at", 0)
        if not session.get("parent_ok") or time.time() - stamp > SESSION_MAX_IDLE:
            session.pop("parent_ok", None)
            session["parent_next"] = request.full_path
            return redirect(url_for("parent.login"))
        session["parent_ok_at"] = time.time()
        return view(*args, **kwargs)

    return wrapper


def _viewed_child():
    """Which child's data the parent is looking at."""
    children = profiles.all_children()
    if not children:
        return None, []
    chosen_id = session.get("parent_child_id") or (g.child.id if g.child else None)
    chosen = next((c for c in children if c.id == chosen_id), None) or children[0]
    session["parent_child_id"] = chosen.id
    return chosen, children


def _lockout_left() -> int:
    until = session.get("pin_lock_until", 0)
    return max(0, int(until - time.time()))


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@bp.route("/login", methods=["GET", "POST"])
def login():
    account = profiles.ensure_parent_account()
    db.session.commit()

    locked = _lockout_left()
    if request.method == "POST" and not locked:
        pin = (request.form.get("pin") or "").strip()
        if account.check_pin(pin):
            session["parent_ok"] = True
            session["parent_ok_at"] = time.time()
            session.pop("pin_fails", None)
            session.pop("pin_lock_until", None)
            target = session.pop("parent_next", None)
            return redirect(target or url_for("parent.dashboard"))

        fails = session.get("pin_fails", 0) + 1
        session["pin_fails"] = fails
        if fails >= MAX_PIN_ATTEMPTS:
            session["pin_lock_until"] = time.time() + LOCKOUT_SECONDS
            session["pin_fails"] = 0
            flash("Too many tries. Please wait 5 minutes.", "error")
        else:
            flash(
                f"That PIN is not right. {MAX_PIN_ATTEMPTS - fails} tries left.",
                "error",
            )
        locked = _lockout_left()

    return render_template("parent/login.html", locked=locked)


@bp.post("/logout")
def logout():
    session.pop("parent_ok", None)
    session.pop("parent_ok_at", None)
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
        return redirect(url_for("kid.welcome"))

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
    child = profiles.get_child(child_id)
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
        return redirect(url_for("kid.welcome"))
    subject = subject if subject in SUBJECTS else SUBJECT_ORDER[0]

    return render_template(
        "parent/progress.html",
        view_child=child,
        children=children,
        subject=SUBJECTS[subject],
        subject_id=subject,
        groups=stats.skill_matrix(child.id, subject),
        counts=subject_counts()[subject],
        focus_skills=set(child.settings.focus_skills or []),
    )


@bp.post("/focus")
@parent_required
def toggle_focus():
    child, _ = _viewed_child()
    if child is None:
        return redirect(url_for("parent.dashboard"))
    skill_id = request.form.get("skill_id") or ""
    from ..content import SKILLS_BY_ID

    if skill_id in SKILLS_BY_ID:
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
        return redirect(url_for("kid.welcome"))
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
        return redirect(url_for("kid.welcome"))
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


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@bp.route("/settings", methods=["GET", "POST"])
@parent_required
def settings_page():
    child, children = _viewed_child()
    if child is None:
        return redirect(url_for("kid.welcome"))

    if request.method == "POST":
        warnings = profiles.apply_settings(child.settings, request.form)
        db.session.commit()
        for warning in warnings:
            flash(warning, "info")
        flash("Settings saved.", "success")
        return redirect(url_for("parent.settings_page"))

    weak = scheduler.weak_skills(child.id, 20)
    return render_template(
        "parent/settings.html",
        view_child=child,
        children=children,
        modes=profiles.DIFFICULTY_MODES,
        summary=profiles.settings_summary(child.settings),
        suggested_focus=weak,
        all_skills=ALL_SKILLS,
        focus_skills=set(child.settings.focus_skills or []),
    )


@bp.post("/pin")
@parent_required
def change_pin():
    account = ParentAccount.get()
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
        if not name:
            flash("Please enter a name.", "error")
        else:
            child = profiles.create_child(name, int(year), emoji, colour)
            db.session.commit()
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
    )


@bp.post("/children/<int:child_id>/update")
@parent_required
def update_child(child_id: int):
    child = profiles.get_child(child_id)
    if child is None:
        flash("That profile no longer exists.", "error")
        return redirect(url_for("parent.children_page"))
    name = (request.form.get("name") or "").strip()
    if name:
        child.name = name[:60]
    year = request.form.get("year_group")
    if year and year.isdigit():
        child.year_group = max(1, min(6, int(year)))
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("parent.children_page"))


@bp.post("/children/<int:child_id>/delete")
@parent_required
def delete_child(child_id: int):
    child = profiles.get_child(child_id)
    if child is None:
        return redirect(url_for("parent.children_page"))
    if not _confirmed(child):
        flash("Type the learner's name exactly to confirm deletion.", "error")
        return redirect(url_for("parent.children_page"))

    name = child.name
    if session.get("child_id") == child.id:
        session.pop("child_id", None)
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
        return redirect(url_for("kid.welcome"))
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
    if subject not in SUBJECTS:
        flash("Unknown subject.", "error")
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
    child = profiles.get_child(child_id)
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
    from ..content import bank_size, topic_tree

    sections = []
    for subject_id in SUBJECT_ORDER:
        groups = []
        for year, topic, skills in topic_tree(subject_id):
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
    return render_template(
        "parent/curriculum.html",
        view_child=child,
        children=children,
        sections=sections,
        total_skills=len(ALL_SKILLS),
    )
