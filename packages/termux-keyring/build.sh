TERMUX_PKG_HOMEPAGE=https://github.com/termux
TERMUX_PKG_DESCRIPTION="GPG public keys for the official Termux repositories"
TERMUX_PKG_LICENSE="Apache-2.0"
TERMUX_PKG_MAINTAINER="@termux"
TERMUX_PKG_VERSION=3.15
TERMUX_PKG_AUTO_UPDATE=false
TERMUX_PKG_SKIP_SRC_EXTRACT=true
TERMUX_PKG_PLATFORM_INDEPENDENT=true
TERMUX_PKG_ESSENTIAL=true

termux_step_make_install() {
	local GPG_SHARE_DIR="$TERMUX_PREFIX/share/termux-keyring"

	# Delete all existing termux-keyring keys
	rm -rf "$GPG_SHARE_DIR"
	mkdir -p "$GPG_SHARE_DIR"

	install -Dm600 $TERMUX_PKG_BUILDER_DIR/termux-packages.gpg $GPG_SHARE_DIR

	GPG_DIR="$TERMUX_PREFIX/etc/apt/trusted.gpg.d"
	mkdir -p "$GPG_DIR"
	for GPG_FILE in "$GPG_SHARE_DIR"/*.gpg; do
		ln -s "$GPG_FILE" "$GPG_DIR/$(basename $GPG_FILE)"
	done
}
