from __future__ import annotations

import os
from pathlib import Path

APP_ID = "io.github.henri.MediaPreview"
APP_NAME = "Media Preview"

DEFAULT_FILE_MANAGER_CLASSES = {
    "dolphin",
    "nemo",
    "nautilus",
    "org.gnome.nautilus",
    "org.kde.dolphin",
    "pcmanfm",
    "pcmanfm-qt",
    "thunar",
}

PREVIEW_WINDOW_CLASSES = {
    APP_ID.lower(),
    "media-preview",
}


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(base) / "media-preview"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def file_manager_classes() -> set[str]:
    override = os.environ.get("MEDIA_PREVIEW_FILE_MANAGERS", "").strip()
    if not override:
        return set(DEFAULT_FILE_MANAGER_CLASSES)
    return {item.strip().lower() for item in override.split(",") if item.strip()}

