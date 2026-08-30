"""End-to-end check that every page renders and the whole quest flow works.

    pixi run smoke

Runs against a temporary throwaway database so it never touches real progress.
Exercises: first-run setup, every child page, starting a quest, answering every
question (correctly and incorrectly), the second-chance path, hints, finishing,
the PIN gate, and every parent page.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ✓ {label}")
    else:
        print(f"  ✗ {label} {detail}")
        FAILURES.append(f"{label} {detail}".strip())


def get_csrf(client, base_url: str | None = None) -> str:
    session_args = {"base_url": base_url} if base_url else {}
    with client.session_transaction(**session_args) as session:
        return session.get("_csrf", "")


def answer_body(
    question: dict,
    answer: str = "",
    seconds: int = 5,
    solution: dict | None = None,
) -> dict:
    """Build a valid local submission for scalar, interactive, or rich questions."""
    body = {"question_id": question["id"], "seconds": seconds}
    kind = question.get("kind")
    if kind == "free_text":
        body["response"] = {
            "text": (
                "This smoke test records a clear response with enough detail "
                "for the local review flow to store and review safely."
            )
        }
    elif kind == "handwriting":
        body["response"] = {"text": "Typed handwriting fallback for the smoke test."}
    elif kind == "audio":
        body["response"] = {"transcript": "I would explain this answer clearly."}
    elif kind == "evidence":
        body["response"] = {
            "fields": {
                str(field["id"]): f"Smoke test evidence for {field['label']}."
                for field in question.get("response_spec", {}).get("fields", [])
            }
        }
    elif kind in {"coordinate_points", "transformation_polygon"}:
        response = (solution or {}).get("response_answer")
        body["response"] = response if isinstance(response, dict) else {"type": kind, "points": []}
    else:
        body["answer"] = answer
    return body


def legacy_schema_check() -> None:
    """Exercise account backfill against a database from before account tables."""
    from datetime import date

    from flask import Flask
    from werkzeug.security import generate_password_hash

    from tutor import create_app, db
    from tutor.config import Config
    from tutor.models import Child, ParentAccount, Settings, SkillProgress

    root = Path(tempfile.mkdtemp(prefix="tutor-legacy-"))
    database = root / "legacy.sqlite3"
    legacy_config = type(
        "LegacyConfig",
        (Config,),
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}",
            "INSTANCE_DIR": root,
            "SECRET_KEY": "legacy-schema-check",
        },
    )

    bare = Flask("legacy-fixture")
    bare.config.from_object(legacy_config)
    db.init_app(bare)
    with bare.app_context():
        db.metadata.create_all(
            bind=db.engine,
            tables=[Child.__table__, Settings.__table__, SkillProgress.__table__],
        )
        child = Child(name="Legacy", year_group=3, xp=321)
        db.session.add(child)
        db.session.flush()
        db.session.add(Settings(child_id=child.id))
        db.session.add(
            SkillProgress(
                child_id=child.id,
                skill_id="m3.mult.times-8",
                attempts=4,
                correct=3,
                mastery=0.65,
                due_on=date.today(),
            )
        )
        db.session.commit()
        child_id = child.id

    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE parent_account ("
        "id INTEGER PRIMARY KEY, pin_hash VARCHAR(255) NOT NULL, "
        "auth_version INTEGER NOT NULL DEFAULT 1, updated_at DATETIME)"
    )
    connection.execute(
        "INSERT INTO parent_account (id, pin_hash, auth_version) VALUES (1, ?, 1)",
        (generate_password_hash("5678"),),
    )
    connection.commit()
    connection.close()

    legacy_app = create_app(legacy_config)
    with legacy_app.app_context():
        migrated_child = db.session.get(Child, child_id)
        migrated_parent = db.session.get(ParentAccount, 1)
        migrated_account = migrated_child.learner_account if migrated_child else None
        migrated_progress = db.session.execute(
            db.select(SkillProgress).where(SkillProgress.child_id == child_id)
        ).scalar_one_or_none()
        check(
            "legacy parent setup state is backfilled",
            migrated_parent is not None and migrated_parent.setup_complete is True,
        )
        check(
            "legacy parent PIN is preserved",
            migrated_parent is not None and migrated_parent.check_pin("5678"),
        )
        check(
            "legacy learner account is backfilled",
            migrated_account is not None and migrated_account.login_name == "legacy" and migrated_account.needs_activation,
        )
        check(
            "legacy parent ownership is backfilled",
            migrated_child is not None and any(link.parent_id == 1 for link in migrated_child.parent_links),
        )
        check("legacy learner XP is preserved", migrated_child is not None and migrated_child.xp == 321)
        check(
            "legacy skill progress is preserved",
            migrated_progress is not None and migrated_progress.attempts == 4 and migrated_progress.mastery == 0.65,
        )


def local_first_run_check(create_app, db, config_class) -> None:
    """Exercise tokenless loopback setup and the first-learner capability."""
    from tutor.models import Child
    from tutor.services import auth

    root = Path(tempfile.mkdtemp(prefix="tutor-local-setup-"))
    database = root / "local.sqlite3"
    token_file = root / "bootstrap_token"
    previous_token = os.environ.pop("PARENT_BOOTSTRAP_TOKEN", None)
    try:
        local_config = type(
            "LocalSetupConfig",
            (config_class,),
            {
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}",
                "INSTANCE_DIR": root,
                "DB_PATH": database,
                "BOOTSTRAP_TOKEN_FILE": token_file,
                "SECRET_KEY": "local-setup-smoke-secret",
                "PARENT_SETUP_REQUIRE_TOKEN": False,
            },
        )
        local_app = create_app(local_config)
        local_app.config.update(TESTING=True)

        def open_request(
            client,
            path: str,
            method: str = "GET",
            *,
            remote_addr: str,
            base_url: str,
            **kwargs,
        ):
            environ_overrides = {"REMOTE_ADDR": remote_addr}
            environ_overrides.update(kwargs.pop("environ_overrides", {}))
            return client.open(
                path,
                method=method,
                base_url=base_url,
                environ_overrides=environ_overrides,
                **kwargs,
            )

        remote = local_app.test_client()
        response = open_request(
            remote,
            "/parent/setup",
            remote_addr="192.168.1.44",
            base_url="http://192.168.1.44:5001",
        )
        check(
            "LAN setup still requires a bootstrap token",
            response.status_code == 200 and b'name="bootstrap_token"' in response.data,
            response.status_code,
        )
        response = open_request(
            remote,
            "/parent/setup",
            "POST",
            remote_addr="192.168.1.44",
            base_url="http://192.168.1.44:5001",
            data={
                "_csrf": get_csrf(remote, "http://192.168.1.44:5001"),
                "pin": "4321",
                "confirm_pin": "4321",
            },
            follow_redirects=False,
        )
        check(
            "LAN setup without a token is refused",
            response.status_code == 200 and b"setup token" in response.data.lower(),
            response.status_code,
        )

        spoof = local_app.test_client()
        response = open_request(
            spoof,
            "/parent/setup",
            remote_addr="192.168.1.45",
            base_url="http://127.0.0.1:5001",
            environ_overrides={"HTTP_X_FORWARDED_FOR": "127.0.0.1"},
        )
        check(
            "forwarded loopback spoof does not unlock setup",
            response.status_code == 200 and b'name="bootstrap_token"' in response.data,
            response.status_code,
        )

        local = local_app.test_client()
        response = open_request(
            local,
            "/parent/setup",
            remote_addr="127.0.0.1",
            base_url="http://127.0.0.1:5001",
        )
        check(
            "direct loopback setup does not ask for a token",
            response.status_code == 200
            and b'name="bootstrap_token"' not in response.data
            and b"no setup token is needed" in response.data.lower(),
            response.status_code,
        )
        response = open_request(
            local,
            "/parent/setup",
            "POST",
            remote_addr="127.0.0.1",
            base_url="http://127.0.0.1:5001",
            data={
                "_csrf": get_csrf(local, "http://127.0.0.1:5001"),
                "pin": "4321",
                "confirm_pin": "4321",
            },
            follow_redirects=False,
        )
        check(
            "direct loopback setup accepts no token",
            response.status_code == 302
            and response.headers.get("Location", "").endswith("/welcome"),
            response.status_code,
        )
        with local.session_transaction(base_url="http://127.0.0.1:5001") as browser_session:
            capability = browser_session.get(auth.FIRST_LEARNER_CAPABILITY_KEY)
            check(
                "setup grants a scoped first-learner capability",
                capability is not None
                and capability.get("parent_id") == 1
                and capability.get("auth_version") == browser_session.get(auth.PARENT_AUTH_VERSION_KEY),
            )

        anonymous = local_app.test_client()
        anonymous.get("/parent/login", base_url="http://127.0.0.1:5001")
        response = open_request(
            anonymous,
            "/welcome",
            remote_addr="127.0.0.1",
            base_url="http://127.0.0.1:5001",
            follow_redirects=False,
        )
        check(
            "anonymous first-learner claim is rejected",
            response.status_code == 302
            and "/parent/login" in response.headers.get("Location", ""),
            response.status_code,
        )

        response = open_request(
            local,
            "/welcome",
            remote_addr="127.0.0.1",
            base_url="http://127.0.0.1:5001",
        )
        check("authorized first-learner form renders", response.status_code == 200)
        first_learner_data = {
            "_csrf": get_csrf(local, "http://127.0.0.1:5001"),
            "name": "Local Smoke",
            "year_group": "2",
            "avatar_character": "fox",
            "avatar_colour": "sunshine",
            "learner_login": "local-smoke",
            "learner_pin": "2468",
        }
        response = open_request(
            local,
            "/welcome",
            "POST",
            remote_addr="127.0.0.1",
            base_url="http://127.0.0.1:5001",
            data=first_learner_data,
            follow_redirects=False,
        )
        check(
            "authorized first learner is created",
            response.status_code == 302
            and response.headers.get("Location", "").endswith("/home"),
            response.status_code,
        )
        with local.session_transaction(base_url="http://127.0.0.1:5001") as browser_session:
            check(
                "first-learner capability is consumed",
                auth.FIRST_LEARNER_CAPABILITY_KEY not in browser_session,
            )
        with local_app.app_context():
            child_count = db.session.query(Child).count()
        replay = open_request(
            local,
            "/welcome",
            "POST",
            remote_addr="127.0.0.1",
            base_url="http://127.0.0.1:5001",
            data=first_learner_data,
            follow_redirects=False,
        )
        with local_app.app_context():
            replay_count = db.session.query(Child).count()
        check(
            "first-learner form cannot be replayed",
            replay.status_code == 302
            and replay.headers.get("Location", "").endswith("/")
            and replay_count == child_count == 1,
            replay.status_code,
        )
        with local_app.app_context():
            db.session.remove()
    finally:
        if previous_token is None:
            os.environ.pop("PARENT_BOOTSTRAP_TOKEN", None)
        else:
            os.environ["PARENT_BOOTSTRAP_TOKEN"] = previous_token


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tutor-smoke-"))
    bootstrap_token = "smoke-bootstrap-token-0123456789abcdef0123456789abcdef"
    bootstrap_token_file = tmp / "bootstrap_token"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'smoke.sqlite3'}"
    os.environ["SECRET_KEY"] = "smoke-test-secret-key"
    os.environ["PARENT_BOOTSTRAP_TOKEN"] = bootstrap_token
    os.environ["BOOTSTRAP_TOKEN_FILE"] = str(bootstrap_token_file)

    from sqlalchemy import func
    from werkzeug.security import check_password_hash

    from tutor import create_app, db
    from tutor.config import Config
    from tutor.content import SKILLS_BY_ID
    from tutor.models import Child, Quest, QuestQuestion, SkillProgress
    from tutor.services import profiles

    print("\nLegacy schema compatibility")
    legacy_schema_check()
    print("\nLocal setup gate and first learner authorization")
    local_first_run_check(create_app, db, Config)

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.create_all()
        # Reproduce what `pixi run setup` does before a parent ever opens the
        # app: the parent account already exists with the default PIN. Adult
        # setup must configure it before the learner welcome form is allowed.
        profiles.ensure_parent_account()
        db.session.commit()
        pending_parent = profiles.ensure_parent_account()
        check(
            "external bootstrap token is stored as a hash",
            pending_parent.bootstrap_token_hash is not None
            and bootstrap_token not in pending_parent.bootstrap_token_hash,
        )
        check("external bootstrap token is not written locally", not bootstrap_token_file.exists())

    client = app.test_client()

    seed_tmp = Path(tempfile.mkdtemp(prefix="tutor-seed-check-"))
    seed_db = seed_tmp / "seed.sqlite3"
    seed_env = os.environ.copy()
    seed_env["DATABASE_URL"] = f"sqlite:///{seed_db}"
    seed_env["BOOTSTRAP_TOKEN_FILE"] = str(seed_tmp / "bootstrap_token")
    seed_args = [
        sys.executable,
        "-m",
        "scripts.seed",
        "--name",
        "Seed",
        "--year",
        "3",
        "--learner-login",
        "seed",
        "--learner-pin",
        "2468",
        "--pin",
        "9876",
    ]
    seed_result = subprocess.run(
        seed_args,
        cwd=Path(__file__).resolve().parents[1],
        env=seed_env,
        capture_output=True,
        text=True,
    )
    check("seed CLI completes", seed_result.returncode == 0, seed_result.stderr[-300:])
    if seed_db.exists():
        connection = sqlite3.connect(seed_db)
        row = connection.execute(
            "SELECT pin_hash, setup_complete, bootstrap_token_hash, "
            "bootstrap_token_consumed_at FROM parent_account WHERE id = 1"
        ).fetchone()
        connection.close()
        check("seed CLI applies the requested parent PIN", row is not None and check_password_hash(row[0], "9876"))
        check("seed CLI does not leave the default parent PIN", row is not None and not check_password_hash(row[0], "1234"))
        check(
            "seed CLI retires the bootstrap token",
            row is not None and row[1] == 1 and row[2] is None and row[3] is not None,
        )

    # Local installations retrieve the plaintext token only through the
    # explicit CLI. Keep this database and file separate from the hosted-token
    # app above so both provisioning modes are covered in one run.
    cli_tmp = Path(tempfile.mkdtemp(prefix="tutor-bootstrap-cli-"))
    cli_db = cli_tmp / "cli.sqlite3"
    cli_token_file = cli_tmp / "bootstrap_token"
    cli_env = os.environ.copy()
    cli_env.pop("PARENT_BOOTSTRAP_TOKEN", None)
    cli_env["DATABASE_URL"] = f"sqlite:///{cli_db}"
    cli_env["BOOTSTRAP_TOKEN_FILE"] = str(cli_token_file)
    cli_env["SECRET_KEY"] = "smoke-cli-secret-key"

    def run_bootstrap_cli(*arguments: str):
        return subprocess.run(
            [sys.executable, "-m", "scripts.bootstrap_token", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            env=cli_env,
            capture_output=True,
            text=True,
        )

    local_result = run_bootstrap_cli()
    local_token = local_result.stdout.strip()
    check("local bootstrap-token CLI succeeds", local_result.returncode == 0, local_result.stderr[-300:])
    check("local CLI returns a high-entropy token", len(local_token) >= 32)
    check(
        "local bootstrap token file is created",
        cli_token_file.exists() and cli_token_file.read_text(encoding="utf-8").strip() == local_token,
    )
    check(
        "local bootstrap token file is mode 0600",
        cli_token_file.exists() and cli_token_file.stat().st_mode & 0o777 == 0o600,
    )

    repeat_result = run_bootstrap_cli()
    check(
        "repeated local CLI retrieval is stable",
        repeat_result.returncode == 0
        and bool(local_token)
        and repeat_result.stdout.strip() == local_token,
    )
    rotate_result = run_bootstrap_cli("--rotate")
    rotated_token = rotate_result.stdout.strip()
    check("local bootstrap-token rotation succeeds", rotate_result.returncode == 0, rotate_result.stderr[-300:])
    check(
        "rotation replaces the local token",
        len(rotated_token) >= 32 and rotated_token != local_token,
    )
    check(
        "rotated token is persisted with mode 0600",
        cli_token_file.exists()
        and cli_token_file.read_text(encoding="utf-8").strip() == rotated_token
        and cli_token_file.stat().st_mode & 0o777 == 0o600,
    )
    cli_seed_result = subprocess.run(
        seed_args,
        cwd=Path(__file__).resolve().parents[1],
        env=cli_env,
        capture_output=True,
        text=True,
    )
    check("trusted local seed retires the local token", cli_seed_result.returncode == 0, cli_seed_result.stderr[-300:])
    unavailable_result = run_bootstrap_cli()
    check("bootstrap-token CLI is unavailable after setup", unavailable_result.returncode != 0)
    check("trusted setup removes the local token file", not cli_token_file.exists())

    # ------------------------------------------------------------------
    print("\nFirst run")
    # ------------------------------------------------------------------
    response = client.get("/", follow_redirects=False)
    check(
        "redirects to adult parent setup",
        response.status_code == 302 and response.headers.get("Location", "").endswith("/parent/setup"),
        response.status_code,
    )
    response = client.get("/welcome", follow_redirects=False)
    check(
        "direct welcome requires adult setup",
        response.status_code == 302 and response.headers.get("Location", "").endswith("/parent/setup"),
        response.status_code,
    )

    pre_setup = app.test_client()
    pre_setup.get("/parent/setup")
    response = pre_setup.post(
        "/parent/login",
        data={
            "_csrf": get_csrf(pre_setup),
            "login_name": "parent",
            "pin": app.config["DEFAULT_PARENT_PIN"],
        },
        follow_redirects=False,
    )
    check(
        "default parent credentials cannot bypass bootstrap setup",
        response.status_code == 302 and response.headers.get("Location", "").endswith("/parent/setup"),
        response.status_code,
    )
    response = pre_setup.get("/parent/register", follow_redirects=False)
    check(
        "new parent registration waits for bootstrap setup",
        response.status_code == 302 and response.headers.get("Location", "").endswith("/parent/setup"),
        response.status_code,
    )
    with app.app_context():
        incomplete_parent = profiles.ensure_parent_account()
        incomplete_auth_version = incomplete_parent.auth_version
    with pre_setup.session_transaction() as pre_setup_session:
        pre_setup_session["parent_ok"] = True
        pre_setup_session["parent_ok_at"] = 9999999999
        pre_setup_session["parent_account_id"] = 1
        pre_setup_session["parent_auth_version"] = incomplete_auth_version
    response = pre_setup.get("/parent/children", follow_redirects=False)
    check(
        "incomplete parent sessions cannot manage learners",
        response.status_code == 302 and "/login" in response.headers.get("Location", ""),
        response.status_code,
    )

    response = client.get("/parent/setup", follow_redirects=True)
    setup_markup = response.get_data(as_text=True)
    check("adult setup page renders", b"Set up parent access" in response.data, response.status_code)
    check("adult setup asks for a bootstrap token", b'name="bootstrap_token"' in response.data)
    check("bootstrap token is not rendered in setup HTML", bootstrap_token not in setup_markup)
    response = client.post(
        "/parent/setup",
        data={
            "_csrf": get_csrf(client),
            "bootstrap_token": "wrong-bootstrap-token",
            "pin": "4321",
            "confirm_pin": "4321",
        },
        follow_redirects=False,
    )
    check(
        "wrong bootstrap token is refused",
        response.status_code == 200 and b"setup token or parent pin" in response.data.lower(),
        response.status_code,
    )
    with app.app_context():
        pending_parent = profiles.ensure_parent_account()
        check(
            "wrong bootstrap token does not consume setup",
            pending_parent.setup_complete is False and pending_parent.bootstrap_token_hash is not None,
        )

    response = client.post(
        "/parent/setup",
        data={
            "_csrf": get_csrf(client),
            "bootstrap_token": bootstrap_token,
            "pin": "4321",
            "confirm_pin": "4321",
        },
        follow_redirects=True,
    )
    check("adult setup opens learner welcome", b"Set up the first learner" in response.data, response.status_code)
    with app.app_context():
        configured_parent = profiles.ensure_parent_account()
        check(
            "bootstrap token is consumed after setup",
            configured_parent.setup_complete is True
            and configured_parent.bootstrap_token_hash is None
            and configured_parent.bootstrap_token_consumed_at is not None,
        )
    replay = client.post(
        "/parent/setup",
        data={
            "_csrf": get_csrf(client),
            "bootstrap_token": bootstrap_token,
            "pin": "4321",
            "confirm_pin": "4321",
        },
        follow_redirects=False,
    )
    check(
        "consumed bootstrap token cannot be replayed",
        replay.status_code == 302 and replay.headers.get("Location", "").endswith("/welcome"),
        replay.status_code,
    )
    check(
        "learner welcome omits parent setup fields",
        b"parent_pin" not in response.data and b"Parent PIN" not in response.data,
    )
    check(
        "learner pathway control is labelled",
        b'for="gcse_tier"' in response.data and b"Learning pathway" in response.data,
    )

    response = client.post(
        "/welcome",
        data={
            "_csrf": get_csrf(client),
            "name": "Smoke",
            "year_group": "3",
            "avatar_character": "fox",
            "avatar_colour": "sunshine",
            "learner_login": "smoke",
            "learner_pin": "2468",
            # Legacy clients may still send this field. It must not change the
            # already-configured parent PIN.
            "parent_pin": "9999",
        },
        follow_redirects=True,
    )
    check("creates the first learner", b"Smoke" in response.data, response.status_code)

    with app.app_context():
        child = db.session.execute(db.select(Child)).scalars().first()
        check("learner is stored", child is not None and child.name == "Smoke")
        check("settings row created", child is not None and child.settings is not None)
        check(
            "year mix favours Year 3",
            child is not None and child.settings.year_mix.get("3", 0) >= 40,
            child.settings.year_mix if child else "",
        )
        check(
            "quiet hours are off by default",
            child.settings.allowed_from_hour == 0 and child.settings.allowed_to_hour == 0,
            f"{child.settings.allowed_from_hour}-{child.settings.allowed_to_hour}",
        )
        check("the app is available by default", child.settings.within_allowed_hours())
        account = child.learner_account
        check(
            "learner account is provisioned and active",
            account is not None and account.login_name == "smoke" and not account.needs_activation,
            account.login_name if account else None,
        )
        check("learner account is linked to the default parent", account is not None and any(link.parent_id == 1 for link in child.parent_links))
        configured_parent = profiles.ensure_parent_account()
        check("adult setup is recorded", configured_parent.setup_complete is True)
        check("legacy welcome PIN cannot change parent access", configured_parent.check_pin("4321") and not configured_parent.check_pin("9999"))

    # ------------------------------------------------------------------
    print("\nChild pages")
    # ------------------------------------------------------------------
    learner_markup: dict[str, str] = {}
    for label, url in [
        ("home", "/home"),
        ("maths", "/learn/maths"),
        ("english", "/learn/english"),
        ("science", "/learn/science"),
        ("badges", "/badges"),
        ("shop", "/shop"),
        ("profile", "/me"),
        ("blocked screen", "/blocked"),
    ]:
        response = client.get(url)
        check(f"GET {url} ({label})", response.status_code == 200, response.status_code)
        if url in {"/home", "/learn/maths", "/badges", "/me"}:
            markup = response.get_data(as_text=True)
            learner_markup[url] = markup
            check(f"{url} includes the safe-area viewport", 'viewport-fit=cover' in markup)
            check(f"{url} includes learner chrome", 'class="topbar"' in markup and 'class="tabbar"' in markup)
            if url == "/home":
                check("home navigation marks the active page", 'aria-current="page"' in markup)

    response = client.get("/pick", follow_redirects=False)
    check(
        "legacy learner picker redirects to sign in",
        response.status_code == 302 and response.headers.get("Location", "").endswith("/login"),
        response.status_code,
    )
    response = client.get("/pick", follow_redirects=False)
    check(
        "learner picker does not enumerate profiles",
        b"Smoke" not in response.data and b"Second" not in response.data,
    )

    response = client.post(
        "/logout", data={"_csrf": get_csrf(client)}, follow_redirects=False
    )
    check("learner logout redirects to sign in", response.status_code == 302)
    response = client.get("/home", follow_redirects=False)
    check("learner pages reject a signed-out session", response.status_code == 302 and "/login" in response.headers.get("Location", ""))
    legacy = app.test_client()
    legacy.get("/")
    with legacy.session_transaction() as legacy_session:
        legacy_session["child_id"] = 1
    response = legacy.get("/home", follow_redirects=False)
    check("legacy child sessions are rejected", response.status_code == 302 and "/login" in response.headers.get("Location", ""))
    with legacy.session_transaction() as legacy_session:
        check("legacy child session key is cleared", "child_id" not in legacy_session)
    response = client.post(
        "/login",
        data={"_csrf": get_csrf(client), "login_name": "smoke", "pin": "2468"},
        follow_redirects=True,
    )
    check("learner can sign in with their own credentials", b"Smoke" in response.data, response.status_code)

    response = client.get("/learn/nonsense", follow_redirects=True)
    check("unknown subject redirects home", response.status_code == 200)

    response = client.get("/definitely-not-a-page")
    check("404 page renders", response.status_code == 404)

    # ------------------------------------------------------------------
    print("\nCSRF protection")
    # ------------------------------------------------------------------
    bare = app.test_client()
    bare.get("/")
    response = bare.post("/api/quest/start", json={"mode": "mixed"})
    check("API rejects a missing CSRF token", response.status_code == 400, response.status_code)

    # ------------------------------------------------------------------
    print("\nQuest flow")
    # ------------------------------------------------------------------
    csrf = get_csrf(client)
    headers = {"X-CSRF-Token": csrf}

    response = client.post("/api/quest/start", json={"mode": "mixed"}, headers=headers)
    payload = response.get_json()
    check("quest starts", response.status_code == 200 and payload.get("quest_id"), payload)
    quest_id = payload["quest_id"]

    response = client.get(f"/api/quest/{quest_id}", headers=headers)
    quest = response.get_json()
    check("quest has questions", len(quest.get("questions", [])) >= 4, len(quest.get("questions", [])))
    check(
        "no answers leak to the browser",
        all("answer" not in q for q in quest["questions"]),
    )
    check(
        "every question names a real skill",
        all(q["skill_id"] in SKILLS_BY_ID for q in quest["questions"]),
    )

    response = client.get(f"/play/{quest_id}")
    play_markup = response.get_data(as_text=True)
    check("player page renders", response.status_code == 200, response.status_code)
    check("player page omits learner topbar", 'class="topbar"' not in play_markup)
    check("player page omits learner tabbar", 'class="tabbar"' not in play_markup)

    # Static mobile presentation contracts are checked against the stable
    # learner responses captured before the quest state changed.
    check("home uses responsive action and totals grids", 'class="action-grid"' in learner_markup["/home"] and 'class="score-grid totals-grid"' in learner_markup["/home"])

    css_markup = (Path(__file__).resolve().parents[1] / "tutor/static/css/kid.css").read_text()
    check("mobile shell is breakpoint-scoped", "@media (max-width: 760px)" in css_markup)
    check("desktop answer-pair layout remains", "@media (min-width: 560px)" in css_markup and ".choices.pairs" in css_markup)
    check("mobile controls keep large touch targets", ".btn.big { min-height: 66px" in css_markup and ".choice { min-height: 72px" in css_markup)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.settings.shop_enabled = False
        db.session.commit()
    response = client.get("/shop", follow_redirects=False)
    check("disabled shop still redirects home", response.status_code == 302 and response.headers.get("Location", "").endswith("/home"), response.status_code)
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.settings.shop_enabled = True
        db.session.commit()
    check("enabled shop still renders", client.get("/shop").status_code == 200)

    with app.app_context():
        rows = (
            db.session.execute(
                db.select(QuestQuestion).where(QuestQuestion.quest_id == quest_id)
            )
            .scalars()
            .all()
        )
        solutions = {row.id: row.solution or {} for row in rows}

    # Ask for a hint on the first question.
    first_id = quest["questions"][0]["id"]
    response = client.post(
        f"/api/quest/{quest_id}/hint", json={"question_id": first_id}, headers=headers
    )
    check("hint endpoint responds", response.status_code == 200, response.status_code)

    # Answer one auto-marked question wrongly first (exercises the
    # second-chance path), then correctly. Mixed quests can also contain
    # manual and interactive responses, so the smoke flow submits each kind
    # with its valid response shape.
    manual_kinds = {"free_text", "handwriting", "audio", "evidence"}
    interactive_kinds = {"coordinate_points", "transformation_polygon"}
    scored_questions = [
        question for question in quest["questions"] if question.get("kind") not in manual_kinds
    ]
    retryable_questions = [
        question for question in scored_questions if question.get("kind") not in interactive_kinds
    ]
    check("quest includes an auto-marked question", bool(retryable_questions))
    if not retryable_questions:
        return 1

    wrong_then_right = retryable_questions[0]
    response = client.post(
        f"/api/quest/{quest_id}/answer",
        json={"question_id": wrong_then_right["id"], "answer": "!!definitely wrong!!", "seconds": 5},
        headers=headers,
    )
    body = response.get_json()
    check("second chance offered on a wrong first try", body.get("status") == "retry", body)

    response = client.post(
        f"/api/quest/{quest_id}/answer",
        json=answer_body(
            wrong_then_right,
            solutions[wrong_then_right["id"]].get("answer", ""),
            seconds=4,
            solution=solutions[wrong_then_right["id"]],
        ),
        headers=headers,
    )
    body = response.get_json()
    check("correct answer on the second try is accepted", body.get("correct") is True, body)
    check("earns XP", body.get("xp", 0) > 0, body.get("xp"))

    response = client.post(
        f"/api/quest/{quest_id}/answer",
        json={"question_id": wrong_then_right["id"], "answer": "again", "seconds": 1},
        headers=headers,
    )
    check("cannot answer the same question twice", response.status_code == 400, response.status_code)

    # Answer the rest: all remaining scored questions are correct, except a
    # second auto-marked question when one is available, which gets wrong twice.
    remaining = [
        question for question in quest["questions"] if question["id"] != wrong_then_right["id"]
    ]
    deliberate_wrong = retryable_questions[-1]["id"] if len(retryable_questions) > 1 else None
    for question in remaining:
        qid = question["id"]
        solution = solutions[qid]
        if qid == deliberate_wrong:
            for _ in range(2):
                client.post(
                    f"/api/quest/{quest_id}/answer",
                    json=answer_body(question, "~nope~", seconds=3, solution=solution),
                    headers=headers,
                )
        else:
            client.post(
                f"/api/quest/{quest_id}/answer",
                json=answer_body(
                    question,
                    solution.get("answer", ""),
                    seconds=6,
                    solution=solution,
                ),
                headers=headers,
            )

    response = client.post("/api/heartbeat", json={"seconds": 15}, headers=headers)
    check("heartbeat records time", response.get_json().get("ok") is True, response.get_json())

    response = client.post(f"/api/quest/{quest_id}/finish", json={}, headers=headers)
    summary = response.get_json()
    check("quest finishes", response.status_code == 200 and "stars" in summary, summary)
    check("all questions answered", summary.get("answered") == len(quest["questions"]), summary.get("answered"))
    check(
        "score matches what we sent",
        summary.get("correct") == len(scored_questions) - (1 if deliberate_wrong else 0),
        f"{summary.get('correct')} of {len(scored_questions) - (1 if deliberate_wrong else 0)}",
    )
    check("at least one star awarded", summary.get("stars", 0) >= 1, summary.get("stars"))
    check("badges awarded on first quest", len(summary.get("badges", [])) >= 1, summary.get("badges"))
    check("review lists every question", len(summary.get("review", [])) == len(quest["questions"]))

    response = client.get(f"/done/{quest_id}")
    check("results page renders", response.status_code == 200, response.status_code)

    with app.app_context():
        quest_row = db.session.get(Quest, quest_id)
        check("quest marked finished in the database", quest_row.finished_at is not None)
        progress = (
            db.session.execute(db.select(SkillProgress).where(SkillProgress.child_id == quest_row.child_id))
            .scalars()
            .all()
        )
        check("skill progress written", len(progress) >= 1, len(progress))
        check("mastery moved above zero", any(p.mastery > 0 for p in progress))
        check("spaced repetition scheduled a due date", all(p.due_on is not None for p in progress))
        child_row = db.session.get(Child, quest_row.child_id)
        check("XP accumulated", child_row.xp > 0, child_row.xp)
        check("coins accumulated", child_row.coins > 0, child_row.coins)
        check("day streak started", child_row.streak_days == 1, child_row.streak_days)

    # ------------------------------------------------------------------
    print("\nOther quest modes")
    # ------------------------------------------------------------------
    for mode, extra in [
        ("revision", {}),
        ("ahead", {}),
        ("focus", {}),
        ("skill", {"skill_id": "m3.mult.times-4"}),
    ]:
        body = {"mode": mode, "count": 4}
        body.update(extra)
        response = client.post("/api/quest/start", json=body, headers=headers)
        data = response.get_json()
        ok = response.status_code == 200 and data.get("quest_id")
        check(f"{mode} quest starts", bool(ok), data)
        if ok:
            client.post(f"/api/quest/{data['quest_id']}/abandon", json={}, headers=headers)

    for subject in ("maths", "english", "science"):
        response = client.post(
            "/api/quest/start", json={"subject": subject, "count": 5}, headers=headers
        )
        data = response.get_json()
        check(f"{subject} quest starts", response.status_code == 200 and data.get("quest_id"), data)
        if data.get("quest_id"):
            detail = client.get(f"/api/quest/{data['quest_id']}", headers=headers).get_json()
            subjects = {q["skill_id"].split(".")[0][0] for q in detail["questions"]}
            expected = {"maths": "m", "english": "e", "science": "s"}[subject]
            check(f"{subject} quest only contains {subject}", subjects == {expected}, subjects)
            client.post(f"/api/quest/{data['quest_id']}/abandon", json={}, headers=headers)

    response = client.post("/api/quest/start", json={"subject": "bogus"}, headers=headers)
    check("unknown subject rejected", response.status_code == 400, response.status_code)

    # ------------------------------------------------------------------
    print("\nShop and profile")
    # ------------------------------------------------------------------
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.coins = 500
        db.session.commit()

    response = client.post(
        "/shop/buy", data={"_csrf": csrf, "item_id": "hat-crown"}, follow_redirects=True
    )
    check("can buy a shop item", b"yours" in response.data.lower(), response.status_code)
    response = client.post(
        "/shop/equip", data={"_csrf": csrf, "item_id": "hat-crown"}, follow_redirects=True
    )
    check("can equip a shop item", response.status_code == 200)
    response = client.post(
        "/shop/buy", data={"_csrf": csrf, "item_id": "hat-crown"}, follow_redirects=True
    )
    check("cannot buy the same item twice", b"already own" in response.data.lower())
    response = client.post(
        "/me",
        data={"_csrf": csrf, "avatar_emoji": "🐼", "avatar_colour": "grape"},
        follow_redirects=True,
    )
    check("can change the avatar", response.status_code == 200)

    # ------------------------------------------------------------------
    print("\nParent area")
    # ------------------------------------------------------------------
    response = client.get("/parent/", follow_redirects=True)
    check(
        "parent area is unlocked after setup",
        response.status_code == 200 and b"Overview" in response.data,
        response.status_code,
    )

    response = client.post(
        "/parent/login", data={"_csrf": get_csrf(client), "login_name": "parent", "pin": "0000"}, follow_redirects=True
    )
    check("wrong PIN is refused", b"not right" in response.data, response.status_code)

    response = client.post(
        "/parent/login",
        data={"_csrf": get_csrf(client), "login_name": "parent", "pin": app.config["DEFAULT_PARENT_PIN"]},
        follow_redirects=True,
    )
    check(
        "the default PIN no longer works once one was chosen at setup",
        b"not right" in response.data,
        response.status_code,
    )

    response = client.post(
        "/parent/login", data={"_csrf": get_csrf(client), "login_name": "parent", "pin": "4321"}, follow_redirects=True
    )
    check("correct PIN unlocks", b"progress" in response.data.lower(), response.status_code)

    for label, url in [
        ("overview", "/parent/"),
        ("progress: maths", "/parent/progress/maths"),
        ("progress: english", "/parent/progress/english"),
        ("progress: science", "/parent/progress/science"),
        ("activity", "/parent/activity"),
        ("settings", "/parent/settings"),
        ("learners", "/parent/children"),
        ("curriculum", "/parent/curriculum"),
        ("quest review", f"/parent/quest/{quest_id}"),
    ]:
        response = client.get(url)
        check(f"GET {url} ({label})", response.status_code == 200, response.status_code)

    response = client.get("/parent/children")
    check(
        "parent pathway controls are labelled",
        b'for="pathway-' in response.data
        and b'for="new-gcse-tier"' in response.data
        and b"Learning pathway" in response.data,
    )

    # Save settings.
    csrf = get_csrf(client)
    response = client.post(
        "/parent/settings",
        data={
            "_csrf": csrf,
            "quest_length": "6",
            "daily_limit_minutes": "20",
            "daily_quest_goal": "2",
            "break_after_minutes": "10",
            "weekly_quest_goal": "14",
            # 0 to 0 means "any time", keeping the rest of the run independent
            # of the clock. Quiet hours get their own check further down.
            "allowed_from_hour": "0",
            "allowed_to_hour": "0",
            "subjects_enabled": ["maths", "english"],
            "years_enabled": ["2", "3"],
            "year_mix_1": "0",
            "year_mix_2": "40",
            "year_mix_3": "60",
            "difficulty_mode": "challenge",
            "allow_hints": "on",
            "show_explanations": "on",
            "sound_enabled": "on",
            "large_text": "on",
            "focus_skills": ["m3.mult.times-8"],
            "cheer_note": "Great effort today!",
            "reward_note": "Swimming on Saturday",
        },
        follow_redirects=True,
    )
    check("settings save", b"Settings saved" in response.data, response.status_code)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        s = child_row.settings
        check("quest length saved", s.quest_length == 6, s.quest_length)
        check("daily limit saved", s.daily_limit_minutes == 20, s.daily_limit_minutes)
        check("subjects saved", s.subjects_enabled == ["maths", "english"], s.subjects_enabled)
        check("years saved", s.years_enabled == [2, 3], s.years_enabled)
        check("difficulty saved", s.difficulty_mode == "challenge", s.difficulty_mode)
        check("focus skill saved", s.focus_skills == ["m3.mult.times-8"], s.focus_skills)
        check("unchecked box turned off", s.second_chance is False, s.second_chance)
        check("large text turned on", s.large_text is True, s.large_text)
        check("notes saved", s.cheer_note == "Great effort today!", s.cheer_note)

    # A disabled subject must now be refused.
    response = client.post(
        "/api/quest/start", json={"subject": "science"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    check("disabled subject is refused", response.status_code == 403, response.status_code)

    # Quest length setting is honoured.
    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    data = response.get_json()
    detail = client.get(f"/api/quest/{data['quest_id']}").get_json()
    check("quest length setting honoured", detail["total"] == 6, detail["total"])
    check(
        "disabled year 1 excluded",
        all(q["year"] in (2, 3) for q in detail["questions"]),
        {q["year"] for q in detail["questions"]},
    )

    # Focus skills bias selection.
    focus_hits = 0
    for _ in range(8):
        started = client.post(
            "/api/quest/start",
            json={"subject": "maths", "count": 8},
            headers={"X-CSRF-Token": get_csrf(client)},
        ).get_json()
        info = client.get(f"/api/quest/{started['quest_id']}").get_json()
        if any(q["skill_id"] == "m3.mult.times-8" for q in info["questions"]):
            focus_hits += 1
        client.post(
            f"/api/quest/{started['quest_id']}/abandon",
            json={},
            headers={"X-CSRF-Token": get_csrf(client)},
        )
    check("focus skill appears in every quest", focus_hits == 8, f"{focus_hits}/8 quests")

    # Keep a second already-unlocked browser to verify PIN changes revoke it.
    stale_parent = app.test_client()
    stale_parent.get("/parent/login")
    stale_parent.post(
        "/parent/login",
        data={"_csrf": get_csrf(stale_parent), "login_name": "parent", "pin": "4321"},
    )

    # PIN change.
    csrf = get_csrf(client)
    response = client.post(
        "/parent/pin",
        data={"_csrf": csrf, "current_pin": "4321", "new_pin": "9876", "confirm_pin": "9876"},
        follow_redirects=True,
    )
    check("PIN can be changed", b"PIN updated" in response.data)
    response = stale_parent.get("/parent/settings", follow_redirects=False)
    check("parent PIN change invalidates older parent sessions", response.status_code == 302 and "/login" in response.headers.get("Location", ""))

    response = client.post("/parent/logout", data={"_csrf": get_csrf(client)}, follow_redirects=True)
    check("parent area locks", response.status_code == 200)
    response = client.get("/parent/settings", follow_redirects=False)
    check("locked area redirects to login", response.status_code == 302, response.status_code)

    # Add and delete a second learner.
    client.post("/parent/login", data={"_csrf": get_csrf(client), "login_name": "parent", "pin": "9876"})
    csrf = get_csrf(client)
    response = client.post(
        "/parent/children",
        data={"_csrf": csrf, "name": "Second", "year_group": "2",
              "avatar_character": "bear", "avatar_colour": "ocean",
              "login_name": "second", "learner_pin": "5678"},
        follow_redirects=True,
    )
    check("second learner added", b"Second" in response.data)
    with app.app_context():
        second = db.session.execute(db.select(Child).where(Child.name == "Second")).scalar_one()
        first = db.session.execute(db.select(Child).where(Child.name == "Smoke")).scalar_one()
        second_id = second.id
        first_id = first.id

    # Learner sessions are account-bound: B cannot read A's quest, and changing
    # A's credentials invalidates A's older session.
    learner_a = app.test_client()
    learner_a.get("/login")
    learner_a.post(
        "/login",
        data={"_csrf": get_csrf(learner_a), "login_name": "smoke", "pin": "2468"},
    )
    learner_b = app.test_client()
    learner_b.get("/login")
    learner_b.post(
        "/login",
        data={"_csrf": get_csrf(learner_b), "login_name": "second", "pin": "5678"},
    )
    response = learner_b.get(f"/api/quest/{quest_id}")
    check("learner B cannot read learner A's quest", response.status_code == 404, response.status_code)
    response = learner_a.post("/logout", data={"_csrf": get_csrf(learner_a)})
    check("learner logout completes", response.status_code == 302)
    response = learner_a.get(f"/api/quest/{quest_id}")
    check("learner logout invalidates API access", response.status_code == 401, response.status_code)
    learner_a.post(
        "/login",
        data={"_csrf": get_csrf(learner_a), "login_name": "smoke", "pin": "2468"},
    )
    response = client.post(
        f"/parent/children/{first_id}/update",
        data={"_csrf": csrf, "name": "Smoke", "login_name": "smoke", "learner_pin": "2469",
              "gcse_tier": "off", "year_group": "3"},
        follow_redirects=True,
    )
    check("parent can update learner credentials", b"access updated" in response.data)
    response = learner_a.get("/home", follow_redirects=False)
    check("credential update invalidates an older learner session", response.status_code == 302 and "/login" in response.headers.get("Location", ""))
    response = learner_a.get(f"/api/quest/{quest_id}")
    check("credential update invalidates learner API access", response.status_code == 401, response.status_code)

    # A second parent can manage a separate learner, but cannot see or mutate A.
    parent_two = app.test_client()
    parent_two.get("/parent/register")
    response = parent_two.post(
        "/parent/register",
        data={"_csrf": get_csrf(parent_two), "login_name": "parent-two", "pin": "8765", "confirm_pin": "8765"},
        follow_redirects=True,
    )
    check("second parent account can be created", b"Add another learner" in response.data)
    duplicate_parent = app.test_client()
    duplicate_parent.get("/parent/register")
    response = duplicate_parent.post(
        "/parent/register",
        data={"_csrf": get_csrf(duplicate_parent), "login_name": "parent-two", "pin": "9999", "confirm_pin": "9999"},
        follow_redirects=True,
    )
    check("duplicate parent account names are rejected", b"already in use" in response.data)
    response = parent_two.post(
        "/parent/children",
        data={"_csrf": get_csrf(parent_two), "name": "Third", "year_group": "4",
              "avatar_character": "owl", "avatar_colour": "forest", "login_name": "third",
              "learner_pin": "3456"},
        follow_redirects=True,
    )
    check("second parent can add a separate learner", b"Third" in response.data)
    with app.app_context():
        third = db.session.execute(db.select(Child).where(Child.name == "Third")).scalar_one()
        third_id = third.id
        check("second learner is linked to parent two", any(link.parent_id != 1 for link in third.parent_links))

    response = client.get("/parent/children")
    check("parent one cannot list parent two's learner", b"Third" not in response.data)
    response = parent_two.get("/parent/children")
    check("parent two cannot list parent one's learners", b"Smoke" not in response.data and b"Second" not in response.data)
    response = parent_two.post(
        f"/parent/children/{first_id}/update",
        data={"_csrf": get_csrf(parent_two), "name": "Hijacked", "login_name": "hijacked", "learner_pin": "9999"},
        follow_redirects=True,
    )
    check("parent two cannot edit parent one's learner", b"not managed" in response.data)
    response = client.post(
        f"/parent/view/{third_id}",
        data={"_csrf": csrf},
        follow_redirects=True,
    )
    check("parent one cannot view parent two's learner", b"Third" not in response.data and b"Smoke" in response.data)
    response = client.post(
        f"/parent/children/{third_id}/update",
        data={"_csrf": csrf, "name": "Changed", "login_name": "changed", "learner_pin": "9999"},
        follow_redirects=True,
    )
    check("parent one cannot edit parent two's learner", b"not managed" in response.data)
    response = parent_two.post(
        f"/parent/view/{first_id}",
        data={"_csrf": get_csrf(parent_two)},
        follow_redirects=True,
    )
    check("parent two cannot view parent one's learner", b"Third" in response.data and b"Smoke" not in response.data)
    response = parent_two.post(
        f"/parent/view/{second_id}",
        data={"_csrf": get_csrf(parent_two)},
        follow_redirects=True,
    )
    check("parent two cannot select parent one's second learner", b"Third" in response.data and b"Second" not in response.data)
    response = parent_two.post(
        f"/parent/children/{first_id}/delete",
        data={"_csrf": get_csrf(parent_two), "confirm_name": "Smoke"},
        follow_redirects=True,
    )
    check("parent two cannot delete parent one's learner", b"not managed" in response.data, response.status_code)
    with parent_two.session_transaction() as parent_two_session:
        parent_two_session["parent_child_id"] = first_id
    response = parent_two.post(
        "/parent/data/reset-all",
        data={"_csrf": get_csrf(parent_two), "confirm_name": "Smoke", "keep_purchases": "on"},
        follow_redirects=True,
    )
    check("parent two cannot reset parent one's learner", b"Third" in response.data and b"exactly" in response.data)
    with app.app_context():
        first_question_id = db.session.execute(
            db.select(QuestQuestion.id).where(QuestQuestion.quest_id == quest_id)
        ).scalars().first()
    response = parent_two.post(
        f"/parent/quest/{quest_id}/great-review",
        data={"_csrf": get_csrf(parent_two), "question_id": first_question_id, "score_G": "0", "score_R": "0", "score_E": "0", "score_A": "0", "score_T": "0"},
        follow_redirects=True,
    )
    check("parent two cannot review parent one's quest", b"not part of this learner" in response.data)
    response = parent_two.post(
        f"/parent/quest/{quest_id}/assessment-review",
        data={"_csrf": get_csrf(parent_two), "question_id": first_question_id, "score": "0", "feedback": "No"},
        follow_redirects=True,
    )
    check("parent two cannot assess parent one's quest", b"not part of this learner" in response.data)
    response = client.post(
        f"/parent/children/{third_id}/delete",
        data={"_csrf": csrf, "confirm_name": "Third"},
        follow_redirects=True,
    )
    check("parent one cannot delete parent two's learner", b"not managed" in response.data)
    with app.app_context():
        first_row = db.session.get(Child, first_id)
        third_row = db.session.get(Child, third_id)
        check("cross-parent edit left learner A unchanged", first_row is not None and first_row.name == "Smoke")
        check("cross-parent delete left learner C intact", third_row is not None)

    with app.app_context():
        third_before = db.session.get(Child, third_id)
        links_before = sorted(link.parent_id for link in third_before.parent_links)
    restarted_app = create_app()
    with restarted_app.app_context():
        third_after = db.session.get(Child, third_id)
        links_after = sorted(link.parent_id for link in third_after.parent_links)
        check("app restart preserves parent ownership", links_after == links_before, links_after)

    stale_learner = app.test_client()
    stale_learner.get("/login")
    stale_learner.post(
        "/login",
        data={"_csrf": get_csrf(stale_learner), "login_name": "third", "pin": "3456"},
    )
    response = parent_two.post(
        f"/parent/children/{third_id}/delete",
        data={"_csrf": get_csrf(parent_two), "confirm_name": "Third"},
        follow_redirects=True,
    )
    check("owning parent can delete learner C", b"deleted" in response.data)
    response = parent_two.post(
        "/parent/children",
        data={"_csrf": get_csrf(parent_two), "name": "Fourth", "year_group": "4",
              "avatar_character": "owl", "avatar_colour": "forest", "login_name": "fourth",
              "learner_pin": "4567"},
        follow_redirects=True,
    )
    check("parent two can provision a replacement learner", b"Fourth" in response.data)
    response = stale_learner.get("/home", follow_redirects=False)
    check("deleted learner sessions cannot authenticate a replacement", response.status_code == 302 and "/login" in response.headers.get("Location", ""))
    response = stale_learner.get(f"/api/quest/{quest_id}")
    check("deleted learner API sessions cannot authenticate a replacement", response.status_code == 401, response.status_code)
    with app.app_context():
        fourth = db.session.execute(db.select(Child).where(Child.name == "Fourth")).scalar_one()
        check("replacement learner remains parent-two scoped", [link.parent_id for link in fourth.parent_links] == [2])

    response = client.post(
        f"/parent/children/{second_id}/delete",
        data={"_csrf": csrf, "confirm_name": "wrong name"},
        follow_redirects=True,
    )
    check("delete needs the exact name", b"exactly" in response.data)
    response = client.post(
        f"/parent/children/{second_id}/delete",
        data={"_csrf": csrf, "confirm_name": "Second"},
        follow_redirects=True,
    )
    check("learner can be deleted", b"deleted" in response.data)

    client.post(
        "/login",
        data={"_csrf": get_csrf(client), "login_name": "smoke", "pin": "2469"},
    )

    # ------------------------------------------------------------------
    print("\nClearing and resetting data")
    # ------------------------------------------------------------------
    from tutor.services import maintenance

    response = client.get("/parent/data")
    check("GET /parent/data renders", response.status_code == 200, response.status_code)

    # Build a known history: three finished quests, one per subject.
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.settings.subjects_enabled = ["maths", "english", "science"]
        child_row.settings.years_enabled = [1, 2, 3]
        child_row.settings.second_chance = False
        db.session.commit()

    made = {}
    for subject in ("maths", "english", "science"):
        started = client.post(
            "/api/quest/start",
            json={"subject": subject, "count": 4},
            headers={"X-CSRF-Token": get_csrf(client)},
        ).get_json()
        quest_id = started["quest_id"]
        detail = client.get(f"/api/quest/{quest_id}").get_json()
        with app.app_context():
            answers = {
                row.id: row.solution or {}
                for row in db.session.execute(
                    db.select(QuestQuestion).where(QuestQuestion.quest_id == quest_id)
                ).scalars().all()
            }
        for question in detail["questions"]:
            client.post(
                f"/api/quest/{quest_id}/answer",
                json=answer_body(
                    question,
                    answers[question["id"]].get("answer", ""),
                    seconds=5,
                    solution=answers[question["id"]],
                ),
                headers={"X-CSRF-Token": get_csrf(client)},
            )
        client.post(f"/api/quest/{quest_id}/finish", json={}, headers={"X-CSRF-Token": get_csrf(client)})
        made[subject] = quest_id

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        before = maintenance.stored_summary(child_row)
        check("summary counts the quests", before["quests"] >= 3, before["quests"])
        check("summary counts the answers", before["questions"] >= 12, before["questions"])
        check("summary counts tracked skills", before["skills"] >= 3, before["skills"])

        per_subject = {row["id"]: row for row in maintenance.subject_summary(child_row)}
        check(
            "per-subject counts are populated",
            all(per_subject[s]["questions"] >= 4 for s in ("maths", "english", "science")),
            {s: per_subject[s]["questions"] for s in per_subject},
        )

        # Rebuilding is idempotent: running it twice must give the same answer
        # as running it once. (The first run also normalises the coin balance,
        # which this test inflated by hand earlier when checking the shop.)
        maintenance.rebuild_derived(child_row)
        child_row = db.session.execute(db.select(Child)).scalars().first()
        once = maintenance.stored_summary(child_row)
        first = (child_row.xp, child_row.coins, once["skills"], once["questions"], once["badges"])

        maintenance.rebuild_derived(child_row)
        child_row = db.session.execute(db.select(Child)).scalars().first()
        twice = maintenance.stored_summary(child_row)
        second = (child_row.xp, child_row.coins, twice["skills"], twice["questions"], twice["badges"])
        check("rebuilding twice gives the same result", first == second, f"{first} -> {second}")
        check("a rebuild keeps every answer", twice["questions"] == before["questions"],
              f"{before['questions']} -> {twice['questions']}")
        check("a rebuild keeps every skill record", twice["skills"] == before["skills"],
              f"{before['skills']} -> {twice['skills']}")
        check("coins never go negative", child_row.coins >= 0, child_row.coins)
        before = twice

    # -- Deleting one quest recalculates everything ---------------------
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        xp_before = child_row.xp
        science_answers = db.session.execute(
            db.select(func.count(QuestQuestion.id)).where(
                QuestQuestion.quest_id == made["science"]
            )
        ).scalar_one()
        science_before = {
            row["id"]: row for row in maintenance.subject_summary(child_row)
        }["science"]["questions"]

    response = client.post(
        "/data/quests/delete",
        data={"_csrf": get_csrf(client), "quest_ids": [made["science"]]},
        follow_redirects=True,
    )
    check("deleting a quest needs the parent route", response.status_code in (200, 404, 405))

    response = client.post(
        "/parent/data/quests/delete",
        data={"_csrf": get_csrf(client), "quest_ids": [str(made["science"])]},
        follow_redirects=True,
    )
    check("a single quest can be removed", b"Removed 1 quest" in response.data, response.status_code)

    with app.app_context():
        check("the quest is gone", db.session.get(Quest, made["science"]) is None)
        check(
            "its answers went with it",
            db.session.execute(
                db.select(func.count(QuestQuestion.id)).where(
                    QuestQuestion.quest_id == made["science"]
                )
            ).scalar_one() == 0,
        )
        child_row = db.session.execute(db.select(Child)).scalars().first()
        check("XP was recalculated downwards", child_row.xp < xp_before, f"{xp_before} -> {child_row.xp}")
        counts = maintenance.stored_summary(child_row)
        check(
            "the answer count dropped by exactly that quest",
            counts["questions"] == before["questions"] - science_answers,
            f"{before['questions']} - {science_answers} vs {counts['questions']}",
        )
        per_subject = {row["id"]: row for row in maintenance.subject_summary(child_row)}
        check(
            "exactly that quest's science answers went",
            per_subject["science"]["questions"] == science_before - science_answers,
            f"{science_before} - {science_answers} vs {per_subject['science']['questions']}",
        )
        check("maths progress survived", per_subject["maths"]["skills"] > 0, per_subject["maths"])

    response = client.post(
        "/parent/data/quests/delete", data={"_csrf": get_csrf(client)}, follow_redirects=True
    )
    check("removing nothing is rejected", b"Tick at least one" in response.data)

    # -- Subject reset --------------------------------------------------
    response = client.post(
        "/parent/data/subject/english/reset",
        data={"_csrf": get_csrf(client), "confirm_name": "not the name"},
        follow_redirects=True,
    )
    check("a subject reset needs the exact name", b"to confirm" in response.data)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        name = child_row.name

    response = client.post(
        "/parent/data/subject/english/reset",
        data={"_csrf": get_csrf(client), "confirm_name": name},
        follow_redirects=True,
    )
    check("a subject can be reset", b"has been reset" in response.data, response.status_code)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        per_subject = {row["id"]: row for row in maintenance.subject_summary(child_row)}
        check("english progress is cleared", per_subject["english"]["skills"] == 0, per_subject["english"])
        check("maths still untouched", per_subject["maths"]["skills"] > 0, per_subject["maths"])
        check(
            "no maths answers were lost",
            per_subject["maths"]["questions"] >= 4,
            per_subject["maths"]["questions"],
        )

    # -- Coins already spent stay spent ---------------------------------
    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        owned_before = len(child_row.owned_item_ids())
        maintenance.rebuild_derived(child_row)
        child_row = db.session.execute(db.select(Child)).scalars().first()
        check(
            "shop purchases are not refunded by a rebuild",
            len(child_row.owned_item_ids()) == owned_before,
            f"{owned_before} -> {len(child_row.owned_item_ids())}",
        )

    # -- Full reset -----------------------------------------------------
    response = client.post(
        "/parent/data/reset-all",
        data={"_csrf": get_csrf(client), "confirm_name": "wrong"},
        follow_redirects=True,
    )
    check("a full reset needs the exact name", b"to confirm" in response.data)

    response = client.post(
        "/parent/data/reset-all",
        data={"_csrf": get_csrf(client), "confirm_name": name, "keep_purchases": "on"},
        follow_redirects=True,
    )
    check("a full reset runs", b"clean slate" in response.data, response.status_code)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        counts = maintenance.stored_summary(child_row)
        check("all quests cleared", counts["quests"] == 0, counts["quests"])
        check("all answers cleared", counts["questions"] == 0, counts["questions"])
        check("all skill records cleared", counts["skills"] == 0, counts["skills"])
        check("badges cleared", counts["badges"] == 0, counts["badges"])
        check("XP and coins zeroed", (child_row.xp, child_row.coins) == (0, 0),
              (child_row.xp, child_row.coins))
        check("streak cleared", child_row.streak_days == 0, child_row.streak_days)
        check("shop items kept as asked", counts["items"] == owned_before, counts["items"])
        check("the profile itself survives", child_row.name == name)
        check("settings survive a reset", child_row.settings is not None
              and child_row.settings.quest_length == 6, child_row.settings.quest_length)

    # She can still start a fresh quest afterwards.
    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    check("a new quest works after a reset", response.status_code == 200, response.get_json())

    # -- Backups --------------------------------------------------------
    with app.app_context():
        backups = maintenance.list_backups()
        check("backups were taken automatically", len(backups) >= 3, len(backups))
        check(
            "backups sit beside the database in use",
            all("smoke" in str(b.path.parent.parent) or str(tmp) in str(b.path) for b in backups),
            [str(b.path) for b in backups[:2]],
        )
        check("backup reasons are recorded", any("reset" in b.reason for b in backups),
              [b.reason for b in backups])
        check("path traversal is refused", maintenance.delete_backup("../../tutor.sqlite3") is False)
        check("odd names are refused", maintenance.delete_backup("evil.txt") is False)
        first_name = backups[0].name

    response = client.post(
        "/parent/data/backup", data={"_csrf": get_csrf(client)}, follow_redirects=True
    )
    check("a backup can be taken on demand", b"Backup saved" in response.data)

    response = client.post(
        "/parent/data/backups/delete",
        data={"_csrf": get_csrf(client), "name": first_name},
        follow_redirects=True,
    )
    check("a backup can be deleted", b"Deleted backup" in response.data)

    # ------------------------------------------------------------------
    print("\nQuiet hours")
    # ------------------------------------------------------------------
    with app.app_context():
        from datetime import datetime, timedelta

        child_row = db.session.execute(db.select(Child)).scalars().first()
        now = datetime.now()
        # A one-hour window that definitely does not contain right now.
        shut = (now + timedelta(hours=3)).hour
        child_row.settings.allowed_from_hour = shut
        child_row.settings.allowed_to_hour = (shut + 1) % 24
        db.session.commit()
        check("outside the window is detected", not child_row.settings.within_allowed_hours())

    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    body = response.get_json()
    check("quiet hours block a new quest", response.status_code == 403 and body.get("blocked"), body)
    response = client.get("/home")
    check("home explains the quiet hours", b"The app is open between" in response.data)

    with app.app_context():
        child_row = db.session.execute(db.select(Child)).scalars().first()
        child_row.settings.allowed_from_hour = 0
        child_row.settings.allowed_to_hour = 0
        db.session.commit()

    # ------------------------------------------------------------------
    print("\nDaily time limit")
    # ------------------------------------------------------------------
    with app.app_context():
        from tutor.models import DailyActivity, today

        child_row = db.session.execute(db.select(Child)).scalars().first()
        row = db.session.execute(
            db.select(DailyActivity).where(
                DailyActivity.child_id == child_row.id, DailyActivity.on_date == today()
            )
        ).scalar_one_or_none()
        if row is None:
            row = DailyActivity(child_id=child_row.id, on_date=today())
            db.session.add(row)
        row.seconds = 99999
        db.session.commit()

    response = client.post(
        "/api/quest/start", json={"mode": "mixed"}, headers={"X-CSRF-Token": get_csrf(client)}
    )
    body = response.get_json()
    check("daily limit blocks a new quest", response.status_code == 403 and body.get("blocked"), body)

    response = client.get("/home")
    check("home explains the limit", b"minutes for today" in response.data, response.status_code)

    # ------------------------------------------------------------------
    print()
    print("=" * 62)
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} of {CHECKS} checks")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"PASSED: all {CHECKS} checks")
    _ = profiles
    return 0


if __name__ == "__main__":
    sys.exit(main())
