"""Delete the database and rebuild it empty.

    pixi run reset-db

This destroys all progress. It asks for confirmation first.
"""

from __future__ import annotations

import sys

from tutor import create_app, db
from tutor.config import Config


def main() -> int:
    path = Config.DB_PATH
    if path.exists():
        print(f"This will permanently delete {path}")
        print("All learner progress, quests and badges will be lost.")
        answer = input("Type DELETE to continue: ").strip()
        if answer != "DELETE":
            print("Cancelled. Nothing was changed.")
            return 1
        path.unlink()
        print("Old database removed.")
    else:
        print("No existing database found.")

    app = create_app()
    with app.app_context():
        db.create_all()
    print(f"Fresh database created at {path}")
    print("Now run:  pixi run seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
