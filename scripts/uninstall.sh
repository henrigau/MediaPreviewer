#!/usr/bin/env bash
set -euo pipefail

WRAPPER="$HOME/.local/bin/media-preview"
SERVICE_FILE="$HOME/.config/systemd/user/media-preview-daemon.service"
HYPR_STARTUP="$HOME/.config/hypr/UserConfigs/Startup_Apps.conf"
HYPR_RULES="$HOME/.config/hypr/UserConfigs/WindowRules.conf"

systemctl --user disable --now media-preview-daemon.service >/dev/null 2>&1 || true
rm -f "$SERVICE_FILE" "$WRAPPER"
systemctl --user daemon-reload

remove_block() {
  local file="$1"
  if [[ -f "$file" ]]; then
    awk '
      /# BEGIN Media Preview/ {skip=1; next}
      /# END Media Preview/ {skip=0; next}
      skip != 1 {print}
    ' "$file" > "$file.tmp"
    mv "$file.tmp" "$file"
  fi
}

remove_block "$HYPR_STARTUP"
remove_block "$HYPR_RULES"

if command -v hyprctl >/dev/null 2>&1; then
  hyprctl keyword unbind ", SPACE" >/dev/null 2>&1 || true
  hyprctl reload >/dev/null 2>&1 || true
fi

echo "Media Preview uninstalled."

