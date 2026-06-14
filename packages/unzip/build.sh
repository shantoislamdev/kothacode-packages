TERMUX_PKG_HOMEPAGE=https://sourceforge.net/projects/infozip/
TERMUX_PKG_DESCRIPTION="Tools for working with zip files"
TERMUX_PKG_LICENSE="BSD"
TERMUX_PKG_MAINTAINER="@termux"
TERMUX_PKG_VERSION=6.0
TERMUX_PKG_REVISION=10
TERMUX_PKG_SRCURL=https://downloads.sourceforge.net/infozip/unzip${TERMUX_PKG_VERSION/./}.tar.gz
TERMUX_PKG_SHA256=ddf957f66514385df50791bf498e88e09d3087b8a7f5a8f9b53481ed28757c34
TERMUX_PKG_DEPENDS="libbz2"
TERMUX_PKG_BUILD_IN_SRC=true

termux_step_configure() {
	cp unix/Makefile Makefile
}

termux_step_make() {
	CFLAGS+=" $CPPFLAGS"
	CFLAGS+=" -DACORN_FTYPE_NFS"
	CFLAGS+=" -DWILD_STOP_AT_DIR"
	CFLAGS+=" -DLARGE_FILE_SUPPORT"
	CFLAGS+=" -DUNICODE_SUPPORT"
	CFLAGS+=" -DUNICODE_WCHAR"
	CFLAGS+=" -DUTF8_MAYBE_NATIVE"
	CFLAGS+=" -DNO_LCHMOD"
	CFLAGS+=" -DDATE_FORMAT=DF_YMD"
	CFLAGS+=" -DUSE_BZIP2"
	CFLAGS+=" -DNOMEMCPY"
	CFLAGS+=" -DNO_WORKING_ISPRINT"
	CFLAGS+=" -I."

	make -f unix/Makefile prefix=$TERMUX_PREFIX D_USE_BZ2=-DUSE_BZIP2 \
		L_BZ2=-lbz2 LF2="$LDFLAGS" CC="$CC" CF="$CFLAGS" LD="$CC" unzips
}

termux_step_make_install() {
	make -f unix/Makefile prefix=$TERMUX_PREFIX install
}
