"""Session helpers for the independent learner and parent accounts."""

from __future__ import annotations

import time

from flask import session

LEARNER_ACCOUNT_KEY = "learner_account_id"
LEARNER_AUTH_VERSION_KEY = "learner_auth_version"
LEARNER_AUTH_NONCE_KEY = "learner_auth_nonce"
PARENT_ACCOUNT_KEY = "parent_account_id"
PARENT_AUTH_VERSION_KEY = "parent_auth_version"
FIRST_LEARNER_CAPABILITY_KEY = "first_learner_capability"
FIRST_LEARNER_CAPABILITY_TTL = 10 * 60


def learner_login(account) -> None:
    """Bind the browser to exactly one learner account."""
    session.pop("child_id", None)  # legacy profile-selection session key
    session[LEARNER_ACCOUNT_KEY] = account.id
    session[LEARNER_AUTH_VERSION_KEY] = account.auth_version
    session[LEARNER_AUTH_NONCE_KEY] = account.auth_nonce
    session.permanent = True


def learner_logout() -> None:
    session.pop(LEARNER_ACCOUNT_KEY, None)
    session.pop(LEARNER_AUTH_VERSION_KEY, None)
    session.pop(LEARNER_AUTH_NONCE_KEY, None)
    session.pop("child_id", None)


def clear_first_learner_capability() -> None:
    """Remove the one-time permission to create the first learner."""
    session.pop(FIRST_LEARNER_CAPABILITY_KEY, None)


def grant_first_learner_capability(account, *, ttl: int = FIRST_LEARNER_CAPABILITY_TTL) -> None:
    """Allow this authenticated parent to open first-learner setup briefly."""
    session[FIRST_LEARNER_CAPABILITY_KEY] = {
        "parent_id": account.id,
        "auth_version": account.auth_version,
        "expires_at": time.time() + ttl,
    }


def first_learner_capability_valid(account) -> bool:
    """Check the short-lived capability against the current parent session."""
    capability = session.get(FIRST_LEARNER_CAPABILITY_KEY)
    if not isinstance(capability, dict):
        return False

    try:
        expires_at = float(capability.get("expires_at", 0))
    except (TypeError, ValueError):
        clear_first_learner_capability()
        return False

    if expires_at <= time.time():
        clear_first_learner_capability()
        return False
    if (
        account is None
        or not session.get("parent_ok")
        or session.get(PARENT_ACCOUNT_KEY) != account.id
        or session.get(PARENT_AUTH_VERSION_KEY) != account.auth_version
        or capability.get("parent_id") != account.id
        or capability.get("auth_version") != account.auth_version
    ):
        return False
    return True


def consume_first_learner_capability(account) -> bool:
    """Consume the capability after the first learner is committed."""
    valid = first_learner_capability_valid(account)
    clear_first_learner_capability()
    return valid


def parent_login(account) -> None:
    """Bind the parent dashboard to one parent account."""
    clear_first_learner_capability()
    session["parent_ok"] = True
    session["parent_ok_at"] = time.time()
    session[PARENT_ACCOUNT_KEY] = account.id
    session[PARENT_AUTH_VERSION_KEY] = account.auth_version
    session.pop("parent_child_id", None)
    session.pop("pin_fails", None)
    session.pop("pin_lock_until", None)
    session.permanent = True


def parent_logout() -> None:
    clear_first_learner_capability()
    session.pop("parent_ok", None)
    session.pop("parent_ok_at", None)
    session.pop(PARENT_ACCOUNT_KEY, None)
    session.pop(PARENT_AUTH_VERSION_KEY, None)
    session.pop("parent_child_id", None)
    session.pop("parent_next", None)
