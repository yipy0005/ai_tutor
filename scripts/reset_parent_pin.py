"""Reset a parent account's PIN from the server command line.

    pixi run reset-parent-pin -- --login-name NAME
    pixi run reset-parent-pin -- --list

Needs shell access to the server, so it adds no web attack surface. The new PIN
is read from a hidden prompt rather than an argument, so it never lands in shell
history. Changing the PIN bumps the account's auth version, which signs out every
existing session for that parent. Learner accounts are not touched.

It is safe to run while the app is up. Run it as the user that owns the database.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from tutor import create_app, db
from tutor.models import ParentAccount
from tutor.services import profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset a parent account's PIN.")
    parser.add_argument("--login-name", help="Parent sign-in name to reset.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List parent sign-in names and exit.",
    )
    args = parser.parse_args()
    if not args.list and not args.login_name:
        parser.error("provide --login-name NAME (or --list)")

    app = create_app()
    with app.app_context():
        if args.list:
            for account in db.session.execute(
                db.select(ParentAccount).order_by(ParentAccount.id)
            ).scalars():
                state = "ready" if account.setup_complete else "setup not complete"
                print(f"{account.login_name}  ({state})")
            return 0

        account = profiles.find_parent_account(args.login_name)
        if account is None:
            print(
                f"No parent account named {profiles.normalize_login(args.login_name)!r}. "
                "Use --list to see the available names.",
                file=sys.stderr,
            )
            return 1
        if not account.setup_complete:
            print(
                "That account has not finished first-run setup; complete setup in "
                "the browser instead (see bootstrap-token).",
                file=sys.stderr,
            )
            return 1

        try:
            pin = profiles.validate_pin(
                getpass.getpass("New parent PIN (4 to 8 digits): "),
                required=True,
                label="parent",
            )
            if getpass.getpass("Confirm new parent PIN: ").strip() != pin:
                print("The two PINs did not match. Nothing was changed.", file=sys.stderr)
                return 1
        except ValueError as exc:
            print(f"{exc} Nothing was changed.", file=sys.stderr)
            return 1

        account.set_pin(pin)
        db.session.commit()
        print(f"PIN reset for {account.login_name}. Existing parent sessions are signed out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
