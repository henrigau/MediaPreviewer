#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="/usr/bin/python3"
BIN_DIR="$HOME/.local/bin"
WRAPPER="$BIN_DIR/media-preview"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/media-preview-daemon.service"
HYPR_USER_DIR="$HOME/.config/hypr/UserConfigs"
HYPR_STARTUP="$HYPR_USER_DIR/Startup_Apps.conf"
HYPR_RULES="$HYPR_USER_DIR/WindowRules.conf"
HYPR_KEYBINDS="$HYPR_USER_DIR/UserKeybinds.conf"

mkdir -p "$BIN_DIR" "$SYSTEMD_USER_DIR" "$HYPR_USER_DIR"

cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$PROJECT_DIR:\${PYTHONPATH:-}"
exec "$PYTHON_BIN" -m media_preview "\$@"
EOF
chmod +x "$WRAPPER"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Media Preview Hyprland Space watcher
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$WRAPPER daemon
Restart=on-failure
RestartSec=1

[Install]
WantedBy=default.target
EOF

touch "$HYPR_STARTUP" "$HYPR_RULES" "$HYPR_KEYBINDS"

replace_managed_block() {
  local file="$1"
  local block="$2"
  local tmp
  tmp="$(mktemp)"

  awk '
    /# BEGIN Media Preview/ {skip=1; next}
    /# END Media Preview/ {skip=0; next}
    skip != 1 {print}
  ' "$file" > "$tmp"

  printf "\n%s\n" "$block" >> "$tmp"
  mv "$tmp" "$file"
}

remove_managed_block() {
  local file="$1"
  local tmp
  tmp="$(mktemp)"

  awk '
    /# BEGIN Media Preview/ {skip=1; next}
    /# END Media Preview/ {skip=0; next}
    skip != 1 {print}
  ' "$file" > "$tmp"

  mv "$tmp" "$file"
}

remove_managed_block "$HYPR_STARTUP"

replace_managed_block "$HYPR_KEYBINDS" "# BEGIN Media Preview
bind = , SPACE, exec, $WRAPPER smart-space
# END Media Preview"

replace_managed_block "$HYPR_RULES" '# BEGIN Media Preview
windowrule = match:class ^(io.github.henri.MediaPreview)$, float on, center on, size 70% 75%, pin on
# END Media Preview'

systemctl --user import-environment HYPRLAND_INSTANCE_SIGNATURE WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_RUNTIME_DIR || true
systemctl --user daemon-reload
systemctl --user disable --now media-preview-daemon.service >/dev/null 2>&1 || true

if command -v hyprctl >/dev/null 2>&1; then
  hyprctl reload >/dev/null 2>&1 || true
fi

if ! command -v ydotool >/dev/null 2>&1; then
  cat <<'EOF'

Media Preview installed, but ydotool is missing.
Install it for selected-file capture:

  sudo pacman -S ydotool
  systemctl --user enable --now ydotool.service

EOF
else
  systemctl --user enable --now ydotool.service >/dev/null 2>&1 || true
  echo "Media Preview installed."
fi
