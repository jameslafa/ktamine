# Build and install from this checkout with: makepkg -si
# The package is built from the latest commit (HEAD), not uncommitted changes.
pkgname=ktamine
pkgver=0.1.0
pkgrel=1
pkgdesc='Keep-awake tray app for KDE Plasma, inspired by Amphetamine'
url='https://github.com/jameslafa/ktamine'
arch=('any')
license=('MIT')
depends=('python' 'python-pyqt6')
makedepends=('git')
optdepends=('systemsettings: "Change shortcut…" menu item')
source=("ktamine.git::git+file://${startdir}")
sha256sums=('SKIP')

pkgver() {
  cd ktamine.git
  # v0.1.0 tag + 3 commits -> 0.1.0.r3.g<hash>
  git describe --long --tags | sed 's/^v//;s/-/.r/;s/-/./'
}

package() {
  cd ktamine.git
  local share="$pkgdir/usr/share"

  install -d "$share/ktamine"
  cp -r ktamine bin "$share/ktamine/"
  python -m compileall -q -d /usr/share/ktamine/ktamine "$share/ktamine/ktamine"

  install -d "$pkgdir/usr/bin"
  ln -s /usr/share/ktamine/bin/ktamine "$pkgdir/usr/bin/ktamine"

  install -Dm644 ktamine.desktop "$share/applications/ktamine.desktop"
  # Registers the "Toggle keep-awake" global shortcut (System Settings > Shortcuts).
  install -d "$share/kglobalaccel"
  ln -s /usr/share/applications/ktamine.desktop "$share/kglobalaccel/ktamine.desktop"
  install -Dm644 ktamine/icons/active.svg "$share/icons/hicolor/scalable/apps/ktamine.svg"
  install -Dm644 data/io.github.jameslafa.ktamine.metainfo.xml -t "$share/metainfo"
  install -Dm644 README.md "$share/doc/ktamine/README.md"
  install -Dm644 LICENSE "$share/licenses/ktamine/LICENSE"
}
