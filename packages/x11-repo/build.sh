TERMUX_PKG_HOMEPAGE=https://github.com/termux/x11-packages
TERMUX_PKG_DESCRIPTION="Package repository containing X11 programs and libraries"
TERMUX_PKG_LICENSE="Apache-2.0"
TERMUX_PKG_MAINTAINER="@termux"
TERMUX_PKG_VERSION=8.4
TERMUX_PKG_REVISION=2
TERMUX_PKG_AUTO_UPDATE=false
TERMUX_PKG_DEPENDS="termux-keyring"
TERMUX_PKG_SKIP_SRC_EXTRACT=true
TERMUX_PKG_PLATFORM_INDEPENDENT=true

termux_step_make_install() {
	mkdir -p $TERMUX_PREFIX/etc/apt/sources.list.d
	{
		echo "# The x11 termux repository"
		echo "Components: main"
		echo "Signed-By: $TERMUX_PREFIX/etc/apt/trusted.gpg.d/termux-packages.gpg"
		echo "Suites: x11"
		echo "Types: deb"
		echo "URIs: https://x11-packages.termux.net/"
	} > $TERMUX_PREFIX/etc/apt/sources.list.d/x11.sources
}

termux_step_create_debscripts() {
	cat <<- EOF > ./postinst
	#!$TERMUX_PREFIX/bin/sh
	apt update
	exit 0
	EOF
}
