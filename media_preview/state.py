from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from .config import runtime_dir

PREVIEW_PID_FILE = "preview.pid"
DAEMON_PID_FILE = "daemon.pid"


def _pid_file(name: str) -> Path:
    return runtime_dir() / name


def _read_pid(name: str) -> int | None:
    try:
        raw = _pid_file(name).read_text(encoding="utf-8").strip()
        return int(raw)
    except (FileNotFoundError, ValueError):
        return None


def _write_pid(name: str, pid: int) -> None:
    _pid_file(name).write_text(f"{pid}\n", encoding="utf-8")


def _clear_pid(name: str) -> None:
    try:
        _pid_file(name).unlink()
    except (FileNotFoundError, OSError):
        pass


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def current_preview_pid() -> int | None:
    pid = _read_pid(PREVIEW_PID_FILE)
    if pid is None:
        return None
    if process_alive(pid):
        return pid
    _clear_pid(PREVIEW_PID_FILE)
    return None


def write_preview_pid(pid: int) -> None:
    _write_pid(PREVIEW_PID_FILE, pid)


def clear_preview_pid(pid: int | None = None) -> None:
    current = _read_pid(PREVIEW_PID_FILE)
    if pid is None or current == pid:
        _clear_pid(PREVIEW_PID_FILE)


def close_preview(timeout: float = 1.5) -> bool:
    pid = current_preview_pid()
    if pid is None:
        return False

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        clear_preview_pid(pid)
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_alive(pid):
            clear_preview_pid(pid)
            return True
        time.sleep(0.05)

    return True


def write_daemon_pid(pid: int) -> None:
    _write_pid(DAEMON_PID_FILE, pid)


def clear_daemon_pid(pid: int | None = None) -> None:
    current = _read_pid(DAEMON_PID_FILE)
    if pid is None or current == pid:
        _clear_pid(DAEMON_PID_FILE)
