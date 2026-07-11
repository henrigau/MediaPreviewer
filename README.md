# Media Preview

Quick Look-style previews for Hyprland on CachyOS.

Current behavior: press `Space` twice on a selected file in a supported file manager to open a floating preview. Press `Space` once while the preview is open to close it. Outside supported file managers, the global `Space` bind passes the key through to the active window.

## Requirements

Already detected on this machine:

- Hyprland: `hyprctl`
- Clipboard: `wl-copy`, `wl-paste`
- Preview/rendering: GTK4, libadwaita, Poppler, GStreamer, LibreOffice, `pdftoppm`, `mpv`

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

The installer creates `~/.local/bin/media-preview` and appends managed Hyprland config blocks under `~/.config/hypr/UserConfigs`.

Reload Hyprland or log out and back in if your config does not auto-reload.

## Usage

```sh
media-preview show ~/Pictures/example.png
media-preview toggle-selected
media-preview smart-space
media-preview close
```

`smart-space` is what Hyprland binds to plain `Space`. Due to Wayland/file-manager clipboard timing, opening from a file manager currently needs two Space presses. Closing an already open preview needs one Space press.

## Preview Features

- PDFs and converted Office documents open as continuous scrollable documents.
- Videos use native GTK/GStreamer playback controls with seeking.
- MP3 and other audio files open in an `mpv`-backed player with play/pause and seeking.
- Images scale to the preview window.
- CSV files open as a scrollable table.
- Text/code files open in a scrollable read-only monospace viewer.
- Unknown file types fall back to a text preview with replacement characters for undecodable bytes.

## Supported File Managers

Preview opening is supported for active windows whose class matches:

- Nemo
- Dolphin
- Thunar
- Nautilus
- PCManFM

Set `MEDIA_PREVIEW_FILE_MANAGERS` to a comma-separated class list to override this.

## Notes

Wayland has no universal API for "the selected file in the active file manager". This implementation uses a practical cross-file-manager strategy: temporarily sends `Ctrl+C` with `ydotool`, reads the copied file URI from the Wayland clipboard, then restores the previous clipboard content. On the tested Nemo/Hyprland setup, the first Space often only primes the file-manager clipboard selection; the second Space opens the preview.

Hyprland's `sendshortcut` dispatcher is used for pass-through Space behavior outside file managers.
