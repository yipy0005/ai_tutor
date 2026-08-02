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

from ..content import ALL_SKILLS, SUBJECT_ORDER, SUBJECTS, subject_counts
from ..extensions import db
from ..models import ParentAccount
from ..services import profiles, quests, rewards, scheduler, stats

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
        emoji = request.form.get("avatar_emoji") or "🦊"
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
        emojis=rewards.AVATAR_EMOJIS,
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
    if (request.form.get("confirm") or "").strip().lower() != child.name.strip().lower():
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


@bp.post("/children/<int:child_id>/reset-progress")
@parent_required
def reset_progress(child_id: int):
    child = profiles.get_child(child_id)
    if child is None:
        return redirect(url_for("parent.children_page"))
    if (request.form.get("confirm") or "").strip().lower() != child.name.strip().lower():
        flash("Type the learner's name exactly to confirm the reset.", "error")
        return redirect(url_for("parent.children_page"))

    from ..models import BadgeAward, DailyActivity, Quest, SkillProgress

    for model in (SkillProgress, DailyActivity, Quest, BadgeAward):
        for row in db.session.execute(
            db.select(model).where(model.child_id == child.id)
        ).scalars().all():
            db.session.delete(row)
    child.xp = 0
    child.coins = 0
    child.streak_days = 0
    child.best_streak = 0
    child.last_active_on = None
    db.session.commit()
    flash(f"{child.name}'s progress was reset. Cosmetic items were kept.", "info")
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
