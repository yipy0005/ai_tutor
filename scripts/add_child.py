"""Add another learner profile.

    pixi run add-child --name Emma --year 2
"""

from __future__ import annotations

import argparse

from tutor import create_app, db
from tutor.services import profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a learner profile.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--year", type=int, default=3)
    parser.add_argument("--emoji", default="🐨")
    parser.add_argument("--colour", default="ocean")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        db.create_all()
        existing = {c.name.lower() for c in profiles.all_children()}
        if args.name.lower() in existing:
            print(f"A profile called {args.name} already exists.")
            return 1
        child = profiles.create_child(args.name, args.year, args.emoji, args.colour)
        profiles.ensure_parent_account()
        db.session.commit()
        print(f"Added {child.name} (Year {child.year_group}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
