"""Put a backup of the database back in place.

    pixi run restore-backup                  list the backups and choose one
    pixi run restore-backup -- --name FILE   restore a specific one
    pixi run restore-backup -- --list        just list them

Stop the app first (Ctrl+C). Restoring while it is running would leave the
serving process attached to the old file.
"""

from __future__ import annotations

import argparse

from tutor import create_app
from tutor.services import maintenance


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a database backup.")
    parser.add_argument("--name", default=None, help="Backup file name to restore")
    parser.add_argument("--list", action="store_true", help="List backups and exit")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        backups = maintenance.list_backups()

        if not backups:
            print("No backups found in", maintenance.backup_dir())
            print("Backups are taken automatically when you use Parent -> Clear data.")
            return 1

        if args.list or not args.name:
            print(f"Backups in {maintenance.backup_dir()}:")
            print()
            for index, backup in enumerate(backups, start=1):
                print(f"  {index:>2}. {backup.name}")
                print(f"      {backup.made_at:%a %d %b %Y, %H:%M}  ·  "
                      f"{backup.size_kb} kB  ·  {backup.reason}")
            print()
            if args.list:
                return 0

            choice = input("Number to restore (or blank to cancel): ").strip()
            if not choice.isdigit() or not 1 <= int(choice) <= len(backups):
                print("Cancelled. Nothing was changed.")
                return 1
            chosen = backups[int(choice) - 1]
        else:
            chosen = next((b for b in backups if b.name == args.name), None)
            if chosen is None:
                print(f"No backup called {args.name}. Use --list to see what there is.")
                return 1

        print()
        print(f"This will replace {maintenance.live_db_path()}")
        print(f"with {chosen.name} ({chosen.made_at:%d %b %Y, %H:%M}).")
        print("The database being replaced is itself copied into the backups folder first.")
        if input("Type RESTORE to continue: ").strip() != "RESTORE":
            print("Cancelled. Nothing was changed.")
            return 1

        problem = maintenance.restore_backup(chosen.name)
        if problem:
            print("Could not restore:", problem)
            return 1

        print()
        print(f"Restored {chosen.name}.")
        print("Now run:  pixi run serve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
