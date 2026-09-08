"""Add another learner profile.

The parent account is marked configured by this adult-run command. If learner
credentials are omitted, the generated sign-in name must be activated from
Parent → Learners before the learner can sign in.

    pixi run add-child --name Emma --year 2
"""

from __future__ import annotations

import argparse

from tutor import create_app, db
from tutor.services import profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a learner profile to the parent account.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--year", type=int, default=3)
    parser.add_argument("--emoji", default="bear")
    parser.add_argument("--colour", default="ocean")
    parser.add_argument("--learner-login", default=None, help="Learner sign-in name")
    parser.add_argument("--learner-pin", default=None, help="Learner PIN (4 to 8 digits)")
    parser.add_argument(
        "--gcse-subject",
        choices=tuple(profiles.GCSE_SUBJECT_OPTIONS),
        default="gcse_maths",
        help="GCSE subject when used with --gcse-tier",
    )
    parser.add_argument(
        "--gcse-tier",
        choices=tuple(profiles.GCSE_TIER_OPTIONS),
        default="off",
        help="Primary, Foundation, or Higher pathway",
    )
    args = parser.parse_args()

    if args.learner_pin and not args.learner_login:
        parser.error("--learner-pin requires --learner-login")

    app = create_app()
    with app.app_context():
        db.create_all()
        existing = {c.name.lower() for c in profiles.all_children()}
        if args.name.lower() in existing:
            print(f"A profile called {args.name} already exists.")
            return 1
        child = profiles.create_child(
            args.name,
            args.year,
            args.emoji,
            args.colour,
            gcse_tier=args.gcse_tier,
            gcse_subject=args.gcse_subject,
            learner_login=args.learner_login,
            learner_pin=args.learner_pin,
        )
        parent = profiles.ensure_parent_account()
        profiles.mark_parent_setup_complete(parent)
        profiles.link_parent_child(parent.id, child.id)
        db.session.commit()
        print(f"Added {child.name} (Year {child.year_group}).")
        print(f"Learner sign-in name: {child.learner_account.login_name}")
        if child.learner_account.needs_activation:
            print("Set the learner PIN from Parent → Learners before signing in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
