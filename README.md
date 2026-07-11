# Media Preview

Quick Look-style previews for Hyprland on CachyOS.

The app opens a floating preview for the selected file when `Space` is pressed in a supported file manager, then closes it when `Space` is pressed again.

## Requirements

Already detected on this machine:

- Hyprland: `hyprctl`
- Clipboard: `wl-copy`, `wl-paste`
- Preview/rendering: GTK4, libadwaita, Poppler, GStreamer, LibreOffice, `pdftoppm`

Required for best-effort selection capture across file managers:

```sh
sudo pacman -S ydotool
systemctl --user enable --now ydotool.service
```

If `ydotool` reports a socket permission problem, log out and back in so the new `input` group membership is applied to the desktop session.

## Install

```sh
./scripts/install.sh
```

The installer creates `~/.local/bin/media-preview`, installs a user systemd service for the Hyprland watcher, and appends managed Hyprland config blocks under `~/.config/hypr/UserConfigs`.

Reload Hyprland or log out and back in if your config does not auto-reload.

## Usage

```sh
media-preview show ~/Pictures/example.png
media-preview toggle-selected
media-preview close
media-preview daemon
```

`toggle-selected` is what the Hyprland daemon binds to plain `Space` while a supported file manager is active.

## Preview Features

- PDFs and converted Office documents open as continuous scrollable documents.
- Videos and audio use native GTK/GStreamer playback controls with seeking.
- Images scale to the preview window.
- CSV files open as a scrollable table.
- Text/code files open in a scrollable read-only monospace viewer.
- Unknown file types fall back to a text preview with replacement characters for undecodable bytes.

## Supported File Managers

The daemon enables plain `Space` only for active windows whose class matches:

- Nemo
- Dolphin
- Thunar
- Nautilus
- PCManFM

Set `MEDIA_PREVIEW_FILE_MANAGERS` to a comma-separated class list to override this.

## Notes

Wayland has no universal API for "the selected file in the active file manager". This implementation uses a practical cross-file-manager strategy: temporarily sends `Ctrl+C` with `ydotool`, reads the copied file URI from the Wayland clipboard, then restores the previous clipboard content. The capture path retries copy a few times within one `Space` press to handle slower file-manager clipboard updates.
