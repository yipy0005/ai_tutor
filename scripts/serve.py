"""Run the app for everyday family use.

    pixi run serve

Binds to 0.0.0.0 so a tablet on the same home wi-fi can reach it. This is
Flask's built-in server, which is fine for one household but is not hardened
for the public internet — do not port-forward it.
"""

from __future__ import annotations

import socket

from tutor import create_app
from tutor.config import Config


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> int:
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
