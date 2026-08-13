# KothaCode Embedded Runtime

This repository builds the Termux packages and bootstrap used by KothaCode's
embedded local development environment. It is based on the
[Termux packages for Google Play](https://github.com/termux-play-store/termux-packages)
fork and tracks its package definitions while applying the changes required for
KothaCode's application prefix and runtime.

Packages in this repository target the app-private prefix:

```text
/data/data/com.amikotha.code/files/usr
```

They are currently built for `aarch64` (`arm64-v8a`) Android devices and are
published through KothaCode's signed APT repository:

```text
https://repo.code.amikotha.com
```

## Relationship To Termux

KothaCode's direct upstream is
[termux-play-store/termux-packages](https://github.com/termux-play-store/termux-packages),
which adapts the mature package recipes and build infrastructure created by the
[Termux project](https://github.com/termux/termux-packages) for Google Play
requirements. Changes that are generally useful to Termux should be contributed
to [termux/termux-packages](https://github.com/termux/termux-packages), not its
Play Store fork, whenever possible.

This fork is not an official Termux package repository. Standard Termux packages
are built for `/data/data/com.termux/files/usr` and contain absolute paths for
that prefix. They cannot be installed safely into KothaCode. Likewise,
KothaCode packages are built specifically for `com.amikotha.code` and should not
be published as official Termux packages.

## Repository And Bootstrap

KothaCode uses this repository for two related artifacts:

- A signed APT repository containing development tools selected for the embedded
  environment.
- An immutable bootstrap archive containing the minimal shell and package
  management foundation bundled with KothaCode releases.

The ordered package queue is maintained in
`.github/kothacode-package-queue.txt`. Scheduled CI skips package roots already
present in the published repository, builds the next eligible set and publishes
new artifacts without deleting unrelated packages.

See [KOTHACODE_REPO.md](KOTHACODE_REPO.md) for signing, CI, queue, publication
and bootstrap release procedures.

## Building A Package

Use the Termux Docker build environment to obtain the expected toolchain and an
isolated build workspace:

```sh
./scripts/run-docker.sh
```

Build a package and its missing dependencies with:

```sh
./build-package.sh -i <package-name>
```

`<package-name>` corresponds to a directory under `packages/`, such as `bash`
or `vim`. Built Debian packages are written to `output/`.

## Developing Package Definitions

A package normally consists of:

- `packages/<package-name>/build.sh`, which defines its source, dependencies and
  build steps.
- Optional `packages/<package-name>/*.patch` files applied during the build.

Iterate by editing the package definition or patches and rerunning
`./build-package.sh -i <package-name>`. Keep broadly applicable package fixes
compatible with upstream Termux whenever possible; keep KothaCode-specific
changes limited to its application prefix, runtime contract and publication
infrastructure.

## Licensing And Attribution

Termux package definitions and build tooling retain their upstream licenses and
copyright notices. Individual packages retain their own licenses. KothaCode's
repository, bootstrap and release process do not change the licensing terms of
the software being packaged.
