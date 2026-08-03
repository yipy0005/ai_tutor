"""Delete the database and rebuild it empty.

    pixi run reset-db

This destroys all progress. It asks for confirmation first, and offers to take a
backup so the decision is recoverable.
"""

from __future__ import annotations

import sys

from tutor import create_app, db
from tutor.services import maintenance


def main() -> int:
    app = create_app()
    with app.app_context():
        # Resolve the database in use before touching anything: with
        # DATABASE_URL set, the default path would be the wrong file entirely.
        path = maintenance.live_db_path()

        if path.exists():
            print(f"This will permanently delete {path}")
            print("All learner progress, quests and badges will be lost.")
            answer = input("Type DELETE to continue: ").strip()
            if answer != "DELETE":
                print("Cancelled. Nothing was changed.")
                return 1

            if input("Take a backup first? [Y/n] ").strip().lower() not in {"n", "no"}:
                backup = maintenance.backup_database("before reset-db")
                if backup:
                    print(f"Backup saved to {backup}")
                    print("Restore it later with:  pixi run restore-backup")

            db.session.remove()
            db.engine.dispose()
            for suffix in ("", "-wal", "-shm"):
                path.with_name(path.name + suffix).unlink(missing_ok=True)
            print("Old database removed.")
        else:
            print(f"No existing database found at {path}.")

        db.create_all()
        print(f"Fresh database created at {path}")
        print("Now run:  pixi run seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
