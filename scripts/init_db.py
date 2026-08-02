"""Create the SQLite database and all tables.

    pixi run init-db
"""

from __future__ import annotations

from tutor import create_app, db
from tutor.config import Config


def main() -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        print(f"Database ready at {Config.DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
