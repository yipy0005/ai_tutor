"""Creating learner profiles, and reading/writing the parent settings form."""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..config import Config
from ..content import (
    GCSE_BOARD_OPTIONS,
    GCSE_TIER_LABELS,
    GCSE_TIERS,
    PATHWAY_SUBJECT_ORDER,
    PRIMARY_YEARS,
    SKILLS_BY_ID,
    SUBJECT_ORDER,
    SUBJECTS,
)
from ..extensions import db
from ..models import (
    Child,
    LearnerAccount,
    ParentAccount,
    ParentChild,
    Settings,
)
from . import pathways

DIFFICULTY_MODES = {
    "gentle": "Gentle — keep it easy and confident",
    "adaptive": "Adaptive — match the questions to her level (recommended)",
    "challenge": "Challenge — push a bit harder",
}
GCSE_TIER_OPTIONS = {
    "off": "Primary — Years 1–6",
    "foundation": "Foundation",
    "higher": "Higher",
}
GCSE_SUBJECT_OPTIONS = {
    subject: SUBJECTS[subject].name for subject in PATHWAY_SUBJECT_ORDER
}


# ---------------------------------------------------------------------------
# Account identifiers and access
# ---------------------------------------------------------------------------


def normalize_login(value: str | None) -> str:
    """Normalise a human-entered account name for stable lookup."""
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return text.strip("-")[:60]


def validate_login(value: str | None, label: str = "learner") -> str:
    """Return a stable account handle or raise a form-friendly error."""
    normalized = normalize_login(value)
    if len(normalized) < 3:
        raise ValueError(
            f"The {label} sign-in name needs at least 3 letters or numbers."
        )
    return normalized


def validate_pin(value: str | None, *, required: bool = False, label: str = "learner") -> str | None:
    """Validate a numeric PIN while allowing a blank value when optional."""
    pin = str(value or "").strip()
    if not pin:
        if required:
            raise ValueError(f"The {label} PIN needs to be 4 to 8 digits.")
        return None
    if not pin.isdigit() or not 4 <= len(pin) <= 8:
        raise ValueError(f"The {label} PIN needs to be 4 to 8 digits.")
    return pin


def _is_loopback_address(value: str | None) -> bool:
    try:
        return bool(value) and ipaddress.ip_address(str(value)).is_loopback
    except ValueError:
        return False


def _is_local_setup_host(value: str | None) -> bool:
    try:
        hostname = urlsplit(f"//{value or ''}").hostname
    except ValueError:
        return False
    if not hostname:
        return False
    hostname = hostname.rstrip(".").lower()
    if hostname == "localhost":
        return True
    return _is_loopback_address(hostname)


def parent_setup_token_required(
    remote_addr: str | None,
    host: str | None,
) -> bool:
    """Require a bootstrap token unless setup is a direct local request.

    Forwarded headers are intentionally ignored. A reverse proxy must retain
    the public Host value, and deployments can force the gate with the config
    flag even when the origin itself receives loopback traffic.
    """
    if _configured_bootstrap_token() is not None:
        return True
    try:
        forced = bool(current_app.config.get("PARENT_SETUP_REQUIRE_TOKEN", False))
    except RuntimeError:
        forced = bool(Config.PARENT_SETUP_REQUIRE_TOKEN)
    if forced:
        return True
    return not (
        _is_loopback_address(remote_addr) and _is_local_setup_host(host)
    )


MIN_BOOTSTRAP_TOKEN_LENGTH = 32


def _bootstrap_token_file() -> Path:
    try:
        configured = current_app.config.get("BOOTSTRAP_TOKEN_FILE")
    except RuntimeError:
        configured = None
    return Path(configured or Config.BOOTSTRAP_TOKEN_FILE)


def _configured_bootstrap_token() -> str | None:
    token = os.environ.get("PARENT_BOOTSTRAP_TOKEN", "").strip()
    if not token:
        return None
    if len(token) < MIN_BOOTSTRAP_TOKEN_LENGTH:
        raise RuntimeError(
            "PARENT_BOOTSTRAP_TOKEN must be at least 32 characters long."
        )
    return token


def _read_local_bootstrap_token() -> str | None:
    path = _bootstrap_token_file()
    try:
        token = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if len(token) < MIN_BOOTSTRAP_TOKEN_LENGTH:
        raise RuntimeError(f"Bootstrap token file is invalid: {path}")
    path.chmod(0o600)
    return token


def _write_local_bootstrap_token(token: str) -> str:
    path = _bootstrap_token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        existing = _read_local_bootstrap_token()
        if existing is None:
            raise RuntimeError(f"Bootstrap token file could not be read: {path}") from None
        return existing

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    path.chmod(0o600)
    return token


def _local_bootstrap_token() -> str:
    return _read_local_bootstrap_token() or _write_local_bootstrap_token(
        secrets.token_urlsafe(32)
    )


def remove_bootstrap_token_file() -> None:
    """Best-effort removal of the local plaintext bootstrap token."""
    try:
        _bootstrap_token_file().unlink(missing_ok=True)
    except OSError:
        # Database setup state is authoritative if file cleanup is unavailable.
        pass


def ensure_bootstrap_token(account: ParentAccount) -> None:
    """Ensure an incomplete canonical account has a hashed bootstrap token."""
    if account.setup_complete or account.bootstrap_token_hash:
        return
    token = _configured_bootstrap_token() or _local_bootstrap_token()
    account.bootstrap_token_hash = generate_password_hash(token)
    account.bootstrap_token_consumed_at = None



def _delete_bootstrap_token_file_strict() -> None:
    try:
        _bootstrap_token_file().unlink(missing_ok=True)
    except OSError:
        raise RuntimeError("The local bootstrap token file could not be replaced.") from None


def _unique_login(base: str, model, exclude_id: int | None = None) -> str:
    root = normalize_login(base) or "learner"
    candidate = root
    number = 2
    while True:
        query = select(model).where(model.login_name == candidate)
        if exclude_id is not None:
            query = query.where(model.id != exclude_id)
        if db.session.execute(query).scalar_one_or_none() is None:
            return candidate
        candidate = f"{root}-{number}"
        number += 1


def _activation_hash() -> str:
    return generate_password_hash(secrets.token_urlsafe(32))


def find_learner_account(login_name: str | None) -> LearnerAccount | None:
    normalized = normalize_login(login_name)
    if not normalized:
        return None
    return db.session.execute(
        select(LearnerAccount).where(LearnerAccount.login_name == normalized)
    ).scalar_one_or_none()


def get_learner_account(account_id: int | None) -> LearnerAccount | None:
    if not account_id:
        return None
    return db.session.get(LearnerAccount, account_id)


def provision_learner_account(
    child: Child,
    login_name: str | None = None,
    pin: str | None = None,
) -> LearnerAccount:
    """Create or update credentials without changing the learner's history."""
    account = child.learner_account
    requested = validate_login(login_name) if login_name is not None else None
    if account is None:
        if requested and find_learner_account(requested) is not None:
            raise ValueError("That learner sign-in name is already in use.")
        account = LearnerAccount(
            child_id=child.id,
            login_name=requested or _unique_login(child.name, LearnerAccount),
            pin_hash=_activation_hash(),
            needs_activation=True,
        )
        db.session.add(account)
        db.session.flush()
    elif requested and requested != account.login_name:
        existing = db.session.execute(
            select(LearnerAccount).where(
                LearnerAccount.login_name == requested,
                LearnerAccount.id != account.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError("That learner sign-in name is already in use.")
        account.login_name = requested
        account.auth_version += 1

    pin_value = validate_pin(pin)
    if pin_value:
        account.set_pin(pin_value)
    return account


def update_learner_credentials(
    child: Child,
    login_name: str,
    pin: str | None = None,
) -> LearnerAccount:
    normalized = validate_login(login_name)
    account = child.learner_account or provision_learner_account(child)
    existing = db.session.execute(
        select(LearnerAccount).where(
            LearnerAccount.login_name == normalized,
            LearnerAccount.id != account.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("That learner sign-in name is already in use.")
    if account.login_name != normalized:
        account.login_name = normalized
        account.auth_version += 1
    pin_value = validate_pin(pin)
    if pin_value:
        account.set_pin(pin_value)
    return account


def get_parent_account(account_id: int | None) -> ParentAccount | None:
    if not account_id:
        return None
    return db.session.get(ParentAccount, account_id)


def find_parent_account(login_name: str | None) -> ParentAccount | None:
    normalized = normalize_login(login_name)
    if not normalized:
        return None
    return db.session.execute(
        select(ParentAccount).where(ParentAccount.login_name == normalized)
    ).scalar_one_or_none()


def create_parent_account(login_name: str, pin: str) -> ParentAccount:
    if parent_setup_required():
        raise ValueError("Complete initial parent setup before creating another parent account.")
    normalized = validate_login(login_name, label="parent")
    pin_value = validate_pin(pin, required=True, label="parent")
    if find_parent_account(normalized) is not None:
        raise ValueError("That parent account name is already in use.")
    account = ParentAccount(login_name=normalized, pin_hash="", setup_complete=True)
    account.set_pin(pin_value)
    db.session.add(account)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("That parent account name is already in use.") from exc
    return account


def link_parent_child(parent_id: int, child_id: int) -> ParentChild:
    link = db.session.execute(
        select(ParentChild).where(
            ParentChild.parent_id == parent_id,
            ParentChild.child_id == child_id,
        )
    ).scalar_one_or_none()
    if link is None:
        link = ParentChild(parent_id=parent_id, child_id=child_id)
        db.session.add(link)
        db.session.flush()
    return link


def children_for_parent(parent_id: int | None) -> list[Child]:
    if not parent_id:
        return []
    return list(
        db.session.execute(
            select(Child)
            .join(ParentChild, ParentChild.child_id == Child.id)
            .where(ParentChild.parent_id == parent_id)
            .order_by(Child.id)
        ).scalars().all()
    )


def get_child_for_parent(parent_id: int | None, child_id: int | None) -> Child | None:
    if not parent_id or not child_id:
        return None
    return db.session.execute(
        select(Child)
        .join(ParentChild, ParentChild.child_id == Child.id)
        .where(ParentChild.parent_id == parent_id, Child.id == child_id)
    ).scalar_one_or_none()


def parent_count_for_child(child_id: int) -> int:
    return len(
        db.session.execute(
            select(ParentChild).where(ParentChild.child_id == child_id)
        ).scalars().all()
    )


def unlink_parent_child(parent_id: int, child_id: int) -> bool:
    link = db.session.execute(
        select(ParentChild).where(
            ParentChild.parent_id == parent_id,
            ParentChild.child_id == child_id,
        )
    ).scalar_one_or_none()
    if link is None:
        return False
    db.session.delete(link)
    db.session.flush()
    return True


def ensure_account_data() -> None:
    """Backfill account rows without crossing existing parent boundaries."""
    parent = ensure_parent_account()
    if parent.auth_version is None:
        parent.auth_version = 1
    children = all_children()
    if children or (
        parent.pin_hash and not parent.check_pin(Config.DEFAULT_PARENT_PIN)
    ):
        # Existing populated databases already completed adult setup. A
        # custom PIN on an empty legacy database is also an explicit setup.
        mark_parent_setup_complete(parent)
    elif not parent.setup_complete:
        ensure_bootstrap_token(parent)
    for child in children:
        account = provision_learner_account(child)
        if not account.auth_nonce:
            account.auth_nonce = secrets.token_urlsafe(32)
        # Only legacy children without any ownership link belong to the
        # default parent. Never attach a learner already managed by another
        # parent to parent id 1 during a later app restart.
        if parent_count_for_child(child.id) == 0:
            link_parent_child(parent.id, child.id)
    db.session.commit()


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------


def all_children() -> list[Child]:
    return list(
        db.session.execute(select(Child).order_by(Child.id)).scalars().all()
    )


def get_child(child_id: int) -> Child | None:
    return db.session.get(Child, child_id)


def create_child(
    name: str,
    year_group: int = 3,
    avatar_emoji: str = "fox",
    avatar_colour: str = "sunshine",
    gcse_tier: str = "off",
    gcse_subject: str = "gcse_maths",
    learner_login: str | None = None,
    learner_pin: str | None = None,
) -> Child:
    child = Child(
        name=name.strip()[:60] or "Learner",
        year_group=max(1, min(6, int(year_group))),
        avatar_emoji=avatar_emoji,
        avatar_colour=avatar_colour,
    )
    db.session.add(child)
    db.session.flush()

    selected_tier = gcse_tier if gcse_tier in GCSE_TIER_OPTIONS else "off"
    selected_subject = (
        gcse_subject if gcse_subject in GCSE_SUBJECT_OPTIONS else "gcse_maths"
    )
    settings = Settings(
        child_id=child.id,
        gcse_subject=selected_subject,
        gcse_tier=selected_tier,
    )
    # Keep the original Year 1–3 defaults for existing primary behaviour, but
    # make a learner entering Years 4–6 eligible for all earlier primary years.
    if selected_tier == "off":
        highest_year = max(3, min(child.year_group, max(PRIMARY_YEARS)))
        settings.years_enabled = list(range(1, highest_year + 1))
        settings.year_mix = {
            str(year): (50 if year == highest_year else 10)
            for year in settings.years_enabled
        }
        if highest_year == 3:
            settings.year_mix = (
                {"1": 15, "2": 35, "3": 50}
                if child.year_group >= 3
                else {"1": 30, "2": 45, "3": 25}
            )
    db.session.add(settings)
    db.session.flush()
    account = provision_learner_account(child, learner_login, learner_pin)
    child.learner_account = account
    return child


def delete_child(child: Child) -> None:
    db.session.delete(child)
    db.session.commit()


# ---------------------------------------------------------------------------
# Parent account
# ---------------------------------------------------------------------------


def ensure_parent_account(pin: str | None = None) -> ParentAccount:
    """Fetch the parent account, creating it with ``pin`` if it does not exist.

    Note that an existing account is returned untouched — passing ``pin`` will
    not change an already-set PIN. Call ``set_pin`` for that.
    """
    account = ParentAccount.get()
    if account is None:
        account = ParentAccount(
            id=1,
            login_name="parent",
            pin_hash="",
            setup_complete=False,
        )
        account.set_pin(pin or Config.DEFAULT_PARENT_PIN)
        db.session.add(account)
        db.session.flush()
    elif not account.login_name:
        account.login_name = "parent"
    return account


def mark_parent_setup_complete(account: ParentAccount | None = None) -> ParentAccount:
    """Complete trusted setup paths and retire any bootstrap token."""
    account = account or ensure_parent_account()
    if not account.setup_complete:
        account.bootstrap_token_consumed_at = datetime.now()
    account.setup_complete = True
    account.bootstrap_token_hash = None
    remove_bootstrap_token_file()
    return account


def parent_setup_required() -> bool:
    """Whether the first learner must wait for adult parent setup."""
    if all_children():
        return False
    account = ensure_parent_account()
    if not account.setup_complete:
        ensure_bootstrap_token(account)
    return not bool(account.setup_complete)


def complete_parent_setup(
    token: str | None,
    pin: str,
    *,
    require_token: bool = True,
) -> ParentAccount:
    """Complete first-run setup, optionally consuming the bootstrap token."""
    account = ensure_parent_account()
    if account.setup_complete or all_children():
        raise ValueError("Parent setup is no longer available.")

    pin_value = validate_pin(pin, required=True, label="parent")
    token_hash = account.bootstrap_token_hash
    if require_token:
        ensure_bootstrap_token(account)
        token_hash = account.bootstrap_token_hash
        token_value = str(token or "").strip()
        if not token_hash or not check_password_hash(token_hash, token_value):
            raise ValueError("The setup token or parent PIN was not valid.")

    statement = update(ParentAccount).where(
        ParentAccount.id == account.id,
        ParentAccount.setup_complete.is_(False),
    )
    if require_token:
        statement = statement.where(ParentAccount.bootstrap_token_hash == token_hash)
    result = db.session.execute(
        statement.values(
            pin_hash=generate_password_hash(pin_value),
            auth_version=ParentAccount.auth_version + 1,
            setup_complete=True,
            bootstrap_token_hash=None,
            bootstrap_token_consumed_at=datetime.now(),
        )
    )
    if result.rowcount != 1:
        raise ValueError("The setup token or parent PIN was not valid.")
    db.session.flush()
    return db.session.get(ParentAccount, account.id)


def bootstrap_token_for_cli(*, rotate: bool = False) -> str:
    """Return the local token for an incomplete install when explicitly requested."""
    account = ensure_parent_account()
    if account.setup_complete or all_children():
        raise ValueError("Initial parent setup is already complete; no token is available.")
    if _configured_bootstrap_token():
        raise ValueError(
            "PARENT_BOOTSTRAP_TOKEN is externally managed; retrieve it from the secret manager."
        )
    if rotate:
        _delete_bootstrap_token_file_strict()
        account.bootstrap_token_hash = None
        account.bootstrap_token_consumed_at = None
    ensure_bootstrap_token(account)
    db.session.commit()
    token = _read_local_bootstrap_token()
    if token is None:
        raise ValueError("No local bootstrap token exists; rerun with --rotate.")
    return token


# ---------------------------------------------------------------------------
# Settings form
# ---------------------------------------------------------------------------

BOOLEAN_FIELDS = [
    "allow_hints",
    "great_diagnostic",
    "second_chance",
    "show_explanations",
    "sound_enabled",
    "animations_enabled",
    "read_aloud",
    "read_aloud_auto",
    "dyslexia_font",
    "large_text",
    "high_contrast",
    "show_timer",
    "shop_enabled",
]

INT_FIELDS = {
    # field: (minimum, maximum)
    "quest_length": (4, 15),
    "daily_limit_minutes": (0, 240),
    "daily_quest_goal": (0, 12),
    "break_after_minutes": (0, 60),
    "weekly_quest_goal": (0, 100),
    "allowed_from_hour": (0, 23),
    "allowed_to_hour": (0, 23),
}


def _as_int(value, low: int, high: int, fallback: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def apply_settings(settings: Settings, form) -> list[str]:
    """Update a Settings row from a submitted form. Returns warning messages."""
    warnings: list[str] = []

    for field, (low, high) in INT_FIELDS.items():
        if field in form:
            setattr(settings, field, _as_int(form.get(field), low, high, getattr(settings, field)))

    for field in BOOLEAN_FIELDS:
        # An unchecked checkbox is simply absent from the POST body.
        setattr(settings, field, form.get(field) in {"on", "1", "true", "yes"})

    mode = (form.get("difficulty_mode") or "").strip()
    if mode in DIFFICULTY_MODES:
        settings.difficulty_mode = mode

    subject = (form.get("gcse_subject") or "").strip().lower()
    if subject in GCSE_SUBJECT_OPTIONS:
        settings.gcse_subject = subject
    tier = (form.get("gcse_tier") or "").strip().lower()
    if tier in GCSE_TIER_OPTIONS:
        settings.gcse_tier = tier
    board = (form.get("gcse_board") or "").strip().lower()
    if board in GCSE_BOARD_OPTIONS:
        settings.gcse_board = board
    if settings.gcse_tier == "off":
        settings.gcse_board = "generic"
    if not pathways.is_gcse(settings):
        subjects = [s for s in form.getlist("subjects_enabled") if s in SUBJECT_ORDER]
        if subjects:
            settings.subjects_enabled = subjects
        else:
            warnings.append("At least one subject must stay switched on, so nothing was changed there.")

        years = []
        for value in form.getlist("years_enabled"):
            try:
                year = int(value)
            except (TypeError, ValueError):
                continue
            if year in PRIMARY_YEARS:
                years.append(year)
        if years:
            settings.years_enabled = sorted(set(years))
        else:
            warnings.append("At least one year group must stay switched on, so nothing was changed there.")

        mix = {}
        for year in PRIMARY_YEARS:
            mix[str(year)] = _as_int(
                form.get(f"year_mix_{year}"),
                0,
                100,
                (settings.year_mix or {}).get(str(year), 0),
            )
        if sum(mix.values()) == 0:
            warnings.append("The revision balance cannot be all zeros, so it was left as it was.")
        else:
            settings.year_mix = mix

    focus = []
    for sid in form.getlist("focus_skills"):
        skill = SKILLS_BY_ID.get(sid)
        if not skill:
            continue
        if skill.id in pathways.active_skill_ids(settings):
            focus.append(sid)
    settings.focus_skills = focus[:20]
    if len(focus) > 20:
        warnings.append("Only the first 20 focus skills were kept.")

    settings.reward_note = (form.get("reward_note") or "").strip()[:300]
    settings.cheer_note = (form.get("cheer_note") or "").strip()[:300]

    if settings.allowed_from_hour == settings.allowed_to_hour:
        warnings.append(
            "The start and end hour are the same, so the app is available all day."
        )

    return warnings


def settings_summary(settings: Settings) -> list[tuple[str, str]]:
    """A short human-readable summary shown at the top of the settings page."""
    limit = (
        f"{settings.daily_limit_minutes} minutes a day"
        if settings.daily_limit_minutes
        else "No daily time limit"
    )
    base = [
        ("Questions per quest", str(settings.quest_length)),
        ("Daily limit", limit),
        ("Available", f"{settings.allowed_from_hour}:00 – {settings.allowed_to_hour}:00"),
        ("Difficulty", DIFFICULTY_MODES.get(settings.difficulty_mode, settings.difficulty_mode)),
        ("Weekly goal", f"{settings.weekly_quest_goal} quests"),
        (
            "GREAT mode",
            "Evidence interview" if settings.great_diagnostic else "Self-reflection only",
        ),
    ]
    if settings.gcse_tier in GCSE_TIERS:
        subject_name = SUBJECTS.get(
            pathways.gcse_subject(settings), SUBJECTS["gcse_maths"]
        ).name
        return base[:4] + [
            ("Pathway", f"{subject_name} · {GCSE_TIER_LABELS[settings.gcse_tier]}"),
            ("Exam style", GCSE_BOARD_OPTIONS.get(settings.gcse_board, "Board-neutral practice")),
        ] + base[4:]

    mix = settings.year_weights()
    total = sum(mix.values()) or 1
    mix_text = ", ".join(
        f"Y{year} {round(weight / total * 100)}%" for year, weight in sorted(mix.items())
    )
    subject_names = [
        "Maths" if subject == "maths" else subject.title()
        for subject in (settings.subjects_enabled or [])
    ]
    return base[:4] + [
        ("Subjects", ", ".join(subject_names)),
        ("Pathway", "Primary · Years 1–6"),
        ("Year balance", mix_text),
    ] + base[4:]
