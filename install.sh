#!/usr/bin/env bash
# Install ktamine for the current user (or remove it with --uninstall).
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.local/share/ktamine"
installed=(
  "$HOME/.local/bin/ktamine"
  "$HOME/.local/share/applications/ktamine.desktop"
  "$HOME/.local/share/kglobalaccel/ktamine.desktop"
  "$HOME/.local/share/icons/hicolor/scalable/apps/ktamine.svg"
  "$HOME/.local/share/metainfo/io.github.jameslafa.ktamine.metainfo.xml"
)

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -rf "$dest" "${installed[@]}"
  # The autostart entry points at the removed copy.
  rm -f "$HOME/.config/autostart/ktamine.desktop"
  echo "Uninstalled. Settings are kept in ~/.config/ktamine."
  exit 0
fi

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
mkdir -p "$HOME/.local/share/metainfo"
cp "$src/data/io.github.jameslafa.ktamine.metainfo.xml" "$HOME/.local/share/metainfo/"
echo "Installed. Run 'ktamine' or launch it from the app menu."
