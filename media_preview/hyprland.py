from __future__ import annotations

import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import PREVIEW_WINDOW_CLASSES, file_manager_classes
from .state import clear_daemon_pid, write_daemon_pid


def hyprland_socket2() -> Path | None:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not runtime:
        return None

    hypr_dir = Path(runtime) / "hypr"
    if signature:
        socket_path = hypr_dir / signature / ".socket2.sock"
        if socket_path.exists():
            return socket_path

    candidates = sorted(
        hypr_dir.glob("*/.socket2.sock"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def toggle_command() -> str:
    override = os.environ.get("MEDIA_PREVIEW_COMMAND", "").strip()
    if override:
        return override

    installed = Path.home() / ".local" / "bin" / "media-preview"
    if installed.exists():
        return shlex.join([str(installed), "toggle-selected"])

    return shlex.join([sys.executable, "-m", "media_preview", "toggle-selected"])


def run_hyprctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hyprctl", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=2.0,
        check=False,
    )


def active_window_class() -> str:
    result = run_hyprctl(["activewindow", "-j"])
    if result.returncode != 0:
        return ""
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    return str(payload.get("class") or "").lower()


class SpaceBinder:
    def __init__(self) -> None:
        self.command = toggle_command()
        self.bound = False
        self.file_managers = file_manager_classes()

    def should_bind_for_class(self, window_class: str) -> bool:
        normalized = window_class.strip().lower()
        if not normalized:
            return False
        if normalized in PREVIEW_WINDOW_CLASSES:
            return True
        return normalized in self.file_managers

    def update_for_class(self, window_class: str) -> None:
        self.set_bound(self.should_bind_for_class(window_class))

    def set_bound(self, should_bind: bool) -> None:
        if should_bind == self.bound:
            return

        if should_bind:
            expression = f", SPACE, exec, {self.command}"
            result = run_hyprctl(["keyword", "bind", expression])
        else:
            result = run_hyprctl(["keyword", "unbind", ", SPACE"])

        if result.returncode == 0:
            self.bound = should_bind

    def cleanup(self) -> None:
        if self.bound:
            run_hyprctl(["keyword", "unbind", ", SPACE"])
            self.bound = False


def _class_from_event(line: str) -> str | None:
    if line.startswith("activewindow>>"):
        payload = line.split(">>", 1)[1]
        return payload.split(",", 1)[0].strip().lower()
    return None


def run_daemon() -> int:
    binder = SpaceBinder()
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        binder.cleanup()
        clear_daemon_pid(os.getpid())

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    write_daemon_pid(os.getpid())

    try:
        binder.update_for_class(active_window_class())
        while not stopping:
            sock_path = hyprland_socket2()
            if sock_path is None or not sock_path.exists():
                time.sleep(1.0)
                continue

            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.connect(str(sock_path))
                    sock.settimeout(0.075)
                    buffer = ""
                    next_poll = 0.0

                    while not stopping:
                        now = time.monotonic()
                        if now >= next_poll:
                            binder.update_for_class(active_window_class())
                            next_poll = now + 0.075

                        try:
                            chunk = sock.recv(4096)
                        except TimeoutError:
                            continue
                        except socket.timeout:
                            continue

                        if not chunk:
                            break

                        buffer += chunk.decode("utf-8", "replace")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            event_class = _class_from_event(line.strip())
                            if event_class is not None:
                                binder.update_for_class(event_class)
            except (OSError, TimeoutError):
                time.sleep(0.5)
    finally:
        binder.cleanup()
        clear_daemon_pid(os.getpid())

    return 0
