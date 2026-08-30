"""Retrieve or rotate the one-time token for initial parent setup.

    pixi run bootstrap-token
    pixi run bootstrap-token -- --rotate
"""

from __future__ import annotations

import argparse
import sys

from tutor import create_app
from tutor.services import profiles


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print or rotate the local token for initial parent setup."
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Replace a lost local token before parent setup is complete.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        try:
            token = profiles.bootstrap_token_for_cli(rotate=args.rotate)
        except (RuntimeError, ValueError) as exc:
            print(f"Cannot retrieve bootstrap token: {exc}", file=sys.stderr)
            return 1
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
