"""Run the app for everyday family use.

    pixi run serve

Binds to 0.0.0.0 so a tablet on the same home wi-fi can reach it. This is
Flask's built-in server, which is fine for one household but is not hardened
for the public internet — do not port-forward it.
"""

from __future__ import annotations

import socket
import sqlite3

from tutor import create_app
from tutor.config import Config


def check_database(path=None) -> str | None:
    """Confirm the database is present and writable. Returns a problem, or None.

    Worth checking up front because SQLite reports several quite different
    situations as the same unhelpful "attempt to write a readonly database" at
    the moment a child taps Start.
    """
    path = path or Config.DB_PATH
    if not path.exists():
        return (
            f"No database found at {path}.\n"
            "  Run this first:  pixi run setup"
        )
    if not path.parent.is_dir():
        return f"The instance folder {path.parent} is missing."
    try:
        # SQLite needs to write the database *and* create a journal beside it,
        # so the directory has to be writable too, not just the file.
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE IF NOT EXISTS _writecheck (x INTEGER)")
        connection.execute("DROP TABLE _writecheck")
        connection.commit()
        connection.close()
    except sqlite3.OperationalError as exc:
        return (
            f"The database at {path} cannot be written to ({exc}).\n"
            f"  Check that you own {path.parent} and that it is not read-only,\n"
            "  or rebuild from scratch with:  pixi run reset-db"
        )
    return None


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> int:
    problem = check_database()
    if problem:
        print()
        print("  Cannot start: " + problem)
        print()
        return 1

    app = create_app()
    host, port = Config.HOST, Config.PORT

    print()
    print("  Learning Quest is starting up")
    print("  ─────────────────────────────")
    print(f"  On this computer:   http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        print(f"  On the home wi-fi:  http://{local_ip()}:{port}")
    print(f"  Parent area:        http://127.0.0.1:{port}/parent")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
