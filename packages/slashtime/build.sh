TERMUX_PKG_HOMEPAGE=https://github.com/istathar/slashtime
TERMUX_PKG_DESCRIPTION="A small program which displays the time in various places"
TERMUX_PKG_LICENSE="MIT"
TERMUX_PKG_MAINTAINER="@termux"
_COMMIT=ee7de6fdc7d05d5078de8551822ce61cc7548bd6
TERMUX_PKG_VERSION=2023.12.11
TERMUX_PKG_SRCURL=git+https://github.com/istathar/slashtime
TERMUX_PKG_SHA256=9efab8326e3e04dc52433e8c0c80c8477857b5e165a2be8ff453c6b4f1ee85f8
TERMUX_PKG_AUTO_UPDATE=false
TERMUX_PKG_GIT_BRANCH=main
TERMUX_PKG_DEPENDS="perl"
TERMUX_PKG_PLATFORM_INDEPENDENT=true
TERMUX_PKG_BUILD_IN_SRC=true

termux_step_post_get_source() {
	git fetch --unshallow
	git checkout $_COMMIT

	local version="$(git log -1 --format=%cs | sed 's/-/./g')"
	if [ "$version" != "$TERMUX_PKG_VERSION" ]; then
		echo -n "ERROR: The specified version \"$TERMUX_PKG_VERSION\""
		echo " is different from what is expected to be: \"$version\""
		return 1
	fi

	local s=$(find . -type f ! -path '*/.git/*' -print0 | xargs -0 sha256sum | LC_ALL=C sort | sha256sum)
	if [[ "${s}" != "${TERMUX_PKG_SHA256}  "* ]]; then
		termux_error_exit "Checksum mismatch for source files: ${s}"
	fi
}

termux_step_configure() {
	:
}

termux_step_make() {
	:
}

termux_step_make_install() {
	install -Dm700 -T slashtime.pl $TERMUX_PREFIX/bin/slashtime
}
