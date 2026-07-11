from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .notify import notify
from .selection import DependencyError, SelectionError, capture_selected_paths
from .state import close_preview, current_preview_pid, write_preview_pid


def spawn_preview(path: Path) -> int:
    if current_preview_pid() is not None:
        close_preview()

    process = subprocess.Popen(
        [sys.executable, "-m", "media_preview", "show", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    write_preview_pid(process.pid)
    return 0


def toggle_selected() -> int:
    if current_preview_pid() is not None:
        close_preview()
        return 0

    try:
        paths = capture_selected_paths()
    except DependencyError as exc:
        notify("Media Preview setup missing", f"{exc}. Install ydotool and make sure ydotool.service is running.")
        return 2
    except SelectionError as exc:
        notify("Media Preview could not read the selection", str(exc))
        return 1

    if not paths:
        notify("Media Preview", "No selected file found.")
        return 1

    return spawn_preview(paths[0])


def pass_space_to_active_window() -> int:
    from .hyprland import run_hyprctl

    result = run_hyprctl(["dispatch", "sendshortcut", ", SPACE, activewindow"])
    return 0 if result.returncode == 0 else 1


def smart_space() -> int:
    if current_preview_pid() is not None:
        close_preview()
        return 0

    from .config import PREVIEW_WINDOW_CLASSES, file_manager_classes
    from .hyprland import active_window_class

    window_class = active_window_class()
    supported_classes = file_manager_classes() | PREVIEW_WINDOW_CLASSES
    if window_class in supported_classes:
        return toggle_selected()

    return pass_space_to_active_window()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="media-preview")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="open a preview for a path")
    show_parser.add_argument("path")

    subparsers.add_parser("toggle-selected", help="toggle preview for the selected file")
    subparsers.add_parser("smart-space", help="toggle preview in file managers, otherwise pass Space through")
    subparsers.add_parser("close", help="close the active preview")
    subparsers.add_parser("daemon", help="watch Hyprland focus and dynamically bind Space")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "show":
        from .preview import run_preview

        return run_preview(Path(args.path).expanduser().resolve())

    if args.command == "toggle-selected":
        return toggle_selected()

    if args.command == "smart-space":
        return smart_space()

    if args.command == "close":
        return 0 if close_preview() else 1

    if args.command == "daemon":
        from .hyprland import run_daemon

        return run_daemon()

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
