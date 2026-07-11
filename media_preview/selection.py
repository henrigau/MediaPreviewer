from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


class SelectionError(RuntimeError):
    pass


class DependencyError(SelectionError):
    pass


URI_TYPES = (
    "x-special/gnome-copied-files",
    "text/uri-list",
)

TEXT_TYPES = (
    "text/plain;charset=utf-8",
    "text/plain",
    "UTF8_STRING",
    "STRING",
)

SNAPSHOT_TYPES = (
    "x-special/gnome-copied-files",
    "text/uri-list",
    "text/plain;charset=utf-8",
    "text/plain",
    "UTF8_STRING",
    "image/png",
)


@dataclass
class ClipboardSnapshot:
    mime_type: str | None
    payload: bytes | None

    @classmethod
    def capture(cls) -> "ClipboardSnapshot":
        for mime_type in list_clipboard_types():
            if mime_type not in SNAPSHOT_TYPES:
                continue
            payload = read_clipboard_type(mime_type)
            if payload is not None:
                return cls(mime_type, payload)
        return cls(None, None)

    def restore(self) -> None:
        if self.mime_type is None or self.payload is None:
            return
        run_quiet(["wl-copy", "--type", self.mime_type], input_data=self.payload)


def run_quiet(args: list[str], input_data: bytes | None = None, timeout: float = 2.0) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def list_clipboard_types() -> list[str]:
    if not shutil.which("wl-paste"):
        raise DependencyError("wl-paste is required")
    result = run_quiet(["wl-paste", "--list-types"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.decode("utf-8", "replace").splitlines() if line.strip()]


def read_clipboard_type(mime_type: str) -> bytes | None:
    result = run_quiet(["wl-paste", "--no-newline", "--type", mime_type])
    if result.returncode != 0:
        return None
    return result.stdout


def write_clipboard_text(text: str) -> None:
    if not shutil.which("wl-copy"):
        raise DependencyError("wl-copy is required")
    result = run_quiet(["wl-copy", "--type", "text/plain"], input_data=text.encode("utf-8"))
    if result.returncode != 0:
        raise SelectionError(result.stderr.decode("utf-8", "replace").strip() or "failed to write clipboard")


def trigger_copy_with_ydotool() -> None:
    if not shutil.which("ydotool"):
        raise DependencyError("ydotool is required")

    # Linux input codes: KEY_LEFTCTRL=29, KEY_C=46.
    result = run_quiet(["ydotool", "key", "29:1", "46:1", "46:0", "29:0"], timeout=3.0)
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", "replace").strip()
        raise SelectionError(error or "ydotool failed to send Ctrl+C")


def path_from_uri(uri: str) -> Path | None:
    uri = uri.strip()
    if not uri:
        return None

    parsed = urlparse(uri)
    if parsed.scheme == "file":
        if parsed.netloc not in ("", "localhost"):
            return None
        return Path(unquote(parsed.path))

    if parsed.scheme:
        return None

    return Path(os.path.expanduser(unquote(uri)))


def parse_uri_list(payload: str) -> list[Path]:
    paths: list[Path] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        path = path_from_uri(line)
        if path is not None:
            paths.append(path)
    return paths


def parse_gnome_copied_files(payload: str) -> list[Path]:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if lines and lines[0].lower() in {"copy", "cut"}:
        lines = lines[1:]
    return [path for path in (path_from_uri(line) for line in lines) if path is not None]


def parse_plain_paths(payload: str) -> list[Path]:
    paths: list[Path] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        path = path_from_uri(line)
        if path is not None:
            paths.append(path)
    return paths


def parse_clipboard_payload(mime_type: str, payload: bytes, sentinel: str | None = None) -> list[Path]:
    text = payload.decode("utf-8", "replace")
    if sentinel is not None and text.strip() == sentinel:
        return []

    if mime_type == "x-special/gnome-copied-files":
        return parse_gnome_copied_files(text)
    if mime_type == "text/uri-list":
        return parse_uri_list(text)
    if mime_type in TEXT_TYPES:
        return parse_plain_paths(text)
    return []


def _read_selected_paths_once(sentinel: str) -> list[Path]:
    types = list_clipboard_types()
    for mime_type in URI_TYPES + TEXT_TYPES:
        if mime_type not in types:
            continue
        payload = read_clipboard_type(mime_type)
        if payload is None:
            continue
        paths = parse_clipboard_payload(mime_type, payload, sentinel)
        existing_paths = [path for path in paths if path.exists()]
        if existing_paths:
            return existing_paths
    return []


def capture_selected_paths(timeout: float = 3.0) -> list[Path]:
    snapshot = ClipboardSnapshot.capture()
    sentinel = f"media-preview-sentinel-{uuid.uuid4()}"

    try:
        write_clipboard_text(sentinel)
        time.sleep(0.12)

        copy_attempts = 0
        next_copy_at = 0.0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            now = time.monotonic()
            if copy_attempts < 3 and now >= next_copy_at:
                trigger_copy_with_ydotool()
                copy_attempts += 1
                next_copy_at = now + 0.45
                time.sleep(0.08)

            paths = _read_selected_paths_once(sentinel)
            if paths:
                return paths
            time.sleep(0.06)
        return []
    finally:
        snapshot.restore()
