"""Session helpers for the independent learner and parent accounts."""

from __future__ import annotations

import time

from flask import session

LEARNER_ACCOUNT_KEY = "learner_account_id"
LEARNER_AUTH_VERSION_KEY = "learner_auth_version"
LEARNER_AUTH_NONCE_KEY = "learner_auth_nonce"
PARENT_ACCOUNT_KEY = "parent_account_id"
PARENT_AUTH_VERSION_KEY = "parent_auth_version"


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


def parent_login(account) -> None:
    """Bind the parent dashboard to one parent account."""
    session["parent_ok"] = True
    session["parent_ok_at"] = time.time()
    session[PARENT_ACCOUNT_KEY] = account.id
    session[PARENT_AUTH_VERSION_KEY] = account.auth_version
    session.pop("parent_child_id", None)
    session.pop("pin_fails", None)
    session.pop("pin_lock_until", None)
    session.permanent = True


def parent_logout() -> None:
    session.pop("parent_ok", None)
    session.pop("parent_ok_at", None)
    session.pop(PARENT_ACCOUNT_KEY, None)
    session.pop(PARENT_AUTH_VERSION_KEY, None)
    session.pop("parent_child_id", None)
    session.pop("parent_next", None)
