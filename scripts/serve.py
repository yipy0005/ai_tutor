"""Run the app for everyday family use.

    pixi run serve

Binds to 0.0.0.0 so a tablet on the same home wi-fi can reach it. This is
Flask's built-in server, which is fine for one household but is not hardened
for the public internet — do not port-forward it.
"""

from __future__ import annotations

import errno
import ipaddress
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

from werkzeug.serving import WSGIRequestHandler

from tutor import create_app
from tutor.config import Config

# Errors that just mean "the other end went away". Browsers and tablets open
# speculative connections and drop them constantly, and iOS in particular opens
# several sockets it never uses. None of it affects a real request, but the
# development server prints a full traceback for each one, which buries any
# problem that actually matters in pages of noise.
# EBADF is deliberately absent: a bad file descriptor is more likely to be a
# real defect than a client going away, and hiding it would be a poor trade.
QUIET_ERRNOS = frozenset(
    {
        errno.ENOTCONN,      # 57  socket is not connected
        errno.ECONNRESET,    # 54  connection reset by peer
        errno.ECONNABORTED,  # 53  software caused connection abort
        errno.EPIPE,         # 32  broken pipe
        errno.ESHUTDOWN,     # 58  cannot send after transport shutdown
        errno.ETIMEDOUT,     # 60  operation timed out
    }
)


class QuietRequestHandler(WSGIRequestHandler):
    """A request handler that ignores clients hanging up mid-handshake.

    Only the outer ``handle`` is wrapped, deliberately. Catching the error
    inside ``handle_one_request`` instead would leave ``close_connection``
    false, so the keep-alive loop in ``handle`` would immediately retry the
    failing read and spin at 100% CPU for every dropped connection.
    """

    def handle(self) -> None:
        try:
            super().handle()
        except OSError as exc:
            if exc.errno not in QUIET_ERRNOS:
                raise
            self.close_connection = True

    def connection_dropped(self, error, environ=None) -> None:  # noqa: ANN001
        """Called by werkzeug when a client disappears. Nothing worth saying."""


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


# Interfaces that are never the home network: VPN and tunnel devices. A VPN
# address is worse than useless here — a tablet on the wi-fi cannot reach it,
# and connections over the tunnel get reset before they carry a request, which
# is where the "Socket is not connected" noise comes from.
TUNNEL_PREFIXES = ("utun", "tun", "tap", "ppp", "wg", "ipsec", "gif", "stf", "awdl", "llw")


def _is_private(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_private
    except ValueError:
        return False


def _addresses_from_ifconfig() -> list[str]:
    """Real (non-tunnel) private IPv4 addresses, best effort.

    Parses ``ifconfig``, skipping point-to-point and tunnel interfaces. Any
    failure just means we fall back to the routing-table guess.
    """
    try:
        output = subprocess.run(
            ["ifconfig"], capture_output=True, text=True, timeout=3, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    found: list[tuple[str, str]] = []
    name = ""
    point_to_point = False
    for line in output.splitlines():
        if line and not line[0].isspace():
            name = line.split(":", 1)[0]
            point_to_point = "POINTOPOINT" in line
            continue
        stripped = line.strip()
        if not stripped.startswith("inet "):
            continue
        if point_to_point or name.startswith(TUNNEL_PREFIXES):
            continue
        address = stripped.split()[1]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            continue
        if parsed.is_loopback or parsed.is_link_local or not parsed.is_private:
            continue
        if all(address != existing for _, existing in found):
            found.append((name, address))

    def rank(entry: tuple[str, str]) -> tuple:
        interface, address = entry
        # en0 is the built-in wi-fi on a Mac and by far the likeliest way a
        # tablet will reach this, so offer it before dongles and bridges.
        if interface in ("en0", "en1"):
            interface_rank = 0
        elif interface.startswith(("en", "eth", "wl")):
            interface_rank = 1
        else:
            interface_rank = 2
        return (interface_rank, not address.startswith("192.168."), interface, address)

    found.sort(key=rank)
    return [address for _, address in found]


def _address_from_routing() -> str | None:
    """Whatever address the default route would use. May well be the VPN."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return None


def network_addresses() -> list[str]:
    """Addresses worth offering for another device on the same network."""
    candidates = _addresses_from_ifconfig()
    fallback = _address_from_routing()
    if not candidates and fallback and _is_private(fallback):
        candidates = [fallback]
    return [a for a in candidates if a != "127.0.0.1"]


FIREWALL = "/usr/libexec/ApplicationFirewall/socketfilterfw"


def firewall_warning() -> str | None:
    """Warn if the macOS firewall will stop other devices connecting.

    pixi's Python is only ad-hoc signed, so macOS does not auto-allow it. Until
    it is approved, inbound connections complete the TCP handshake and are then
    killed, which looks like "Empty reply from server" on a tablet and produces
    a stream of "Socket is not connected" errors here. Worth saying plainly,
    because otherwise it looks like the app is broken.
    """
    if sys.platform != "darwin" or not Path(FIREWALL).exists():
        return None

    def ask(*args: str) -> str:
        try:
            return subprocess.run(
                [FIREWALL, *args], capture_output=True, text=True, timeout=5, check=False
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    if "State = 1" not in ask("--getglobalstate"):
        return None  # firewall off, nothing in the way

    listing = ask("--listapps")
    if not listing:
        return None  # cannot tell; say nothing rather than cry wolf

    executable = str(Path(sys.executable).resolve())
    lines = listing.splitlines()
    for index, line in enumerate(lines):
        if executable not in line:
            continue
        # The verdict is on the following line, e.g. "(Allow incoming connections)".
        verdict = lines[index + 1] if index + 1 < len(lines) else ""
        if "Block" in verdict:
            return (
                "Other devices cannot connect: this project's Python is set to\n"
                "  BLOCK incoming connections in the macOS firewall.\n\n"
                "  To allow it:\n"
                f"    sudo {FIREWALL} --unblockapp {executable}"
            )
        return None  # explicitly allowed, all good

    # Our interpreter is not in the list at all.
    return (
        "Other devices may not be able to connect.\n"
        "  The macOS firewall is on, and this project's Python is not approved yet,\n"
        "  so a tablet will connect and then get nothing back.\n\n"
        "  To allow it, run these two commands once (they will ask for your password):\n"
        f"    sudo {FIREWALL} --add {executable}\n"
        f"    sudo {FIREWALL} --unblockapp {executable}\n\n"
        "  Alternatively, accept the pop-up macOS shows the first time, or just use\n"
        "  http://127.0.0.1 on this computer."
    )


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
        addresses = network_addresses()
        if addresses:
            label = "  On another device: "
            for address in addresses:
                print(f"{label} http://{address}:{port}")
                label = "                    "
            if len(addresses) > 1:
                print("                     (try them in order if the first does not work)")
        else:
            print("  On another device:  no home network address found")
    print(f"  Parent area:        http://127.0.0.1:{port}/parent")
    print()

    if host == "0.0.0.0" and (warning := firewall_warning()):
        print("  ⚠️  " + warning)
        print()

    print("  Press Ctrl+C to stop.")
    print()

    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
        request_handler=QuietRequestHandler,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
