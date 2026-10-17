#!/usr/bin/env bash
# Install ktamine for the current user.
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.local/share/ktamine"

rm -rf "$dest"
mkdir -p "$dest" "$HOME/.local/bin" "$HOME/.local/share/applications"
cp -r "$src/ktamine" "$src/bin" "$dest/"
ln -sf "$dest/bin/ktamine" "$HOME/.local/bin/ktamine"
# Use an absolute Exec path: ~/.local/bin is often not on the desktop session's PATH.
sed "s|^Exec=ktamine|Exec=\"$dest/bin/ktamine\"|" "$src/ktamine.desktop" \
  > "$HOME/.local/share/applications/ktamine.desktop"
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
cp "$src/ktamine/icons/active.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/ktamine.svg"
# Register the "Toggle keep-awake" global shortcut (System Settings > Shortcuts).
mkdir -p "$HOME/.local/share/kglobalaccel"
ln -sf "$HOME/.local/share/applications/ktamine.desktop" "$HOME/.local/share/kglobalaccel/ktamine.desktop"
echo "Installed. Run 'ktamine' or launch it from the app menu."
