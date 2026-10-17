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
sed "s|^Exec=.*|Exec=\"$dest/bin/ktamine\"|" "$src/ktamine.desktop" \
  > "$HOME/.local/share/applications/ktamine.desktop"
echo "Installed. Run 'ktamine' or launch it from the app menu."
