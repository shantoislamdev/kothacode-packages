TERMUX_PKG_HOMEPAGE=https://github.com/termux/libandroid-support
TERMUX_PKG_DESCRIPTION="Symlink to libc for compatibility"
TERMUX_PKG_LICENSE="Apache-2.0"
TERMUX_PKG_VERSION=28
TERMUX_PKG_MAINTAINER="@termux"
TERMUX_PKG_SKIP_SRC_EXTRACT=true

termux_step_make() {
	cd "$TERMUX_PREFIX/lib"
	ln -f -s "/system/lib${TERMUX_ARCH_BITS}/libc.so" libandroid-support.so
}
