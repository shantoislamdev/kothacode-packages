TERMUX_PKG_HOMEPAGE=https://timewarrior.net/
TERMUX_PKG_DESCRIPTION="Command-line time tracker"
TERMUX_PKG_LICENSE="MIT"
TERMUX_PKG_MAINTAINER="@termux"
TERMUX_PKG_VERSION="1.9.1"
TERMUX_PKG_AUTO_UPDATE=true
TERMUX_PKG_SRCURL=git+https://github.com/GothenburgBitFactory/timewarrior
TERMUX_PKG_DEPENDS="libc++"

# Installation of man pages is broken as of version 1.4.3.
TERMUX_PKG_RM_AFTER_INSTALL="share/man"

termux_step_pre_configure() {
	if [ "$TERMUX_ARCH" = arm ]; then
		# timewarrior/src/src/libshared/src/Datetime.cpp:3793:12: error:
		# non-constant-expression cannot be narrowed from type 'int64_t' (aka 'long long') to 'time_t'
		CPPFLAGS+=" -Wno-c++11-narrowing"
	fi
}
