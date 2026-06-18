TERMUX_PKG_HOMEPAGE=https://github.com/XiaomiMiMo/MiMo-Code
TERMUX_PKG_DESCRIPTION="MiMo Code: Where Models and Agents Co-Evolve"
TERMUX_PKG_LICENSE="MIT"
TERMUX_PKG_MAINTAINER="@kothacode"
TERMUX_PKG_VERSION=0.1.1
TERMUX_PKG_SRCURL=https://github.com/XiaomiMiMo/MiMo-Code/releases/download/v${TERMUX_PKG_VERSION}/mimocode-linux-arm64-musl.tar.gz
TERMUX_PKG_SHA256=280cc1069450981fb9bfc2c2ec0216bb6e40afb125eb7b68e7b99c89ceba36e9
TERMUX_PKG_SKIP_SRC_EXTRACT=true

termux_step_make_install() {
    # Extract the tarball directly into the Termux bin directory
    tar xf $TERMUX_PKG_CACHEDIR/mimocode-linux-arm64-musl.tar.gz -C $TERMUX_PREFIX/bin/
    # Ensure it is executable
    chmod +x $TERMUX_PREFIX/bin/mimo
}
