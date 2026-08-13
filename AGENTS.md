# KothaCode Package CI/CD Rules

These rules apply to package builds, APT publication, queue automation, artifact replay, and bootstrap releases in this repository.

## Scope And Sources

- Build only for Android package `com.amikotha.code`, prefix `/data/data/com.amikotha.code/files/usr`, and architecture `aarch64` (`arm64-v8a`). Never publish ordinary `com.termux` artifacts here.
- `KOTHACODE_REPO.md` is the operator guide for secrets, workflows, and release procedures.
- `.github/kothacode-package-policy.json` owns queue and resource limits.
- `.github/kothacode-package-queue.txt` owns queue order.
- The signed live `dists/stable/main/binary-aarch64/Packages` index is the authoritative published inventory.
- The KothaCode app's `gradle.properties` owns the currently selected immutable bootstrap release, digest, and size pins. Do not copy current pin values into this file.

## Workflow Map

| File | Responsibility |
|---|---|
| `.github/workflows/_kothacode-build-publish.yml` | Resolve, build, replay, and incrementally publish packages |
| `.github/workflows/kothacode-package-repository.yml` | Manual package entry point |
| `.github/workflows/kothacode-package-queue.yml` | Scheduled and manually bounded queue entry point |
| `.github/workflows/kothacode-bootstrap-release.yml` | Generate and publish immutable bootstrap releases |
| `scripts/resolve-kothacode-packages.py` | Produce bounded build plans |
| `scripts/merge-kothacode-packages.py` | Merge package metadata while enforcing repository immutability |
| `scripts/generate-kothacode-apt-repo.sh` | Generate by-hash and signed APT metadata |
| `scripts/generate-bootstraps.sh` | Generate verified prefix-root bootstrap archives |

Keep entry-point workflows thin. Shared behavior belongs in the reusable workflow or its scripts.

## Package Pipeline

- Build through the pinned package-builder image and `scripts/run-docker.sh`; do not silently fall back to the host toolchain.
- Package builds must use `build-package.sh -i`. Reuse a repository dependency only when its exact required version is available and its downloaded file passes metadata verification.
- Package-name presence is only a queue estimate. It must not replace exact-version checks in the builder.
- Queue planning must remain bounded and deterministic. Resolve dependencies with `scripts/buildorder.py` without sourcing or executing package recipes.
- Manual queue counts must be positive and respect policy limits. The reusable `package_count` input remains a string because GitHub can pass dispatch values to reusable workflows as strings; validate it before use.
- Explicit manual builds may attempt large packages on standard runners. Scheduled and queue automation must not route them there; use `resource_class=large` with `KOTHACODE_LARGE_RUNNER_LABEL` when standard resources are insufficient.
- Replay requires a completed source run with a recognized, unexpired aarch64 `.deb` artifact. Replay skips compilation but never skips artifact, architecture, merge, or integrity validation.
- Never replay artifacts known to contain rebuilt same-version packages whose hashes differ from the published repository.
- Preserve source preflight, toolchain checks, runner limits, explicit secret checks, and fail-closed behavior.

## Publication Safety

- Publication is incremental. Read and merge the existing repository state while preserving unrelated package records and pool objects.
- Never use `aws s3 sync --delete`, replace the bucket, or otherwise delete unrelated repository content.
- Only a confirmed not-found response may initialize an empty repository. Other repository read failures must stop publication.
- Never weaken rejection of downgrades, same-version content changes, conflicting hashes, pool filename collisions, or immutable pool-object overwrites. Changed package content requires a package revision bump.
- Upload immutable `pool/` and `by-hash/` objects before mutable indexes and signatures.
- Publish `Packages`, `Release`, `Release.gpg`, and `InRelease` last. Do not expose metadata that references objects not yet uploaded.
- Keep immutable objects on immutable cache headers and mutable metadata on `no-cache` semantics.
- Keep the APT private key confined to the serialized publication job. Builders and bootstrap generation receive only the public key.
- Preserve least-privilege workflow permissions and the shared `kothacode-aarch64-package-pipeline` concurrency group with `cancel-in-progress: false`.

## Bootstrap Contract

Bootstrap locations have different purposes:

```text
CI output:
bootstrap-aarch64.zip
bootstrap-aarch64.manifest.json

GitHub artifact:
kothacode-bootstrap-aarch64

Immutable public release:
https://repo.code.amikotha.com/bootstrap/releases/<source-sha>-<run-id>/bootstrap-aarch64.zip
https://repo.code.amikotha.com/bootstrap/releases/<source-sha>-<run-id>/bootstrap-aarch64.manifest.json

Optional mutable aliases:
https://repo.code.amikotha.com/bootstrap/bootstrap-aarch64.zip
https://repo.code.amikotha.com/bootstrap/bootstrap-aarch64.manifest.json

APK asset:
embedded/bootstrap-aarch64.zip

Installed prefix:
/data/data/com.amikotha.code/files/usr
```

- The release directory identifier is `<source-sha>-<run-id>`, not the archive SHA-256.
- Production app builds consume immutable release URLs only. Mutable aliases are convenience endpoints and are not trusted release pins.
- A new bootstrap does not update the app automatically. Update `kothacode.bootstrap.releaseVersion`, `version`, `sha256`, and `sizeBytes` together from the immutable release.
- The manifest schema contains `schema`, `version`, `architecture`, `source_revision`, `expected_prefix`, `sha256`, and `size_bytes`. It is a consistency document; the app's reviewed digest and size pins remain authoritative.
- The ZIP is rooted at the runtime prefix. It contains `bin/`, `etc/`, `lib/`, and `SYMLINKS.txt` directly and must not contain a top-level `usr/`; the app extracts it into `/data/data/com.amikotha.code/files/usr`.
- Required archive entries include `bin/bash`, `bin/setsid`, `bin/dpkg`, `etc/profile.d/init-termux-properties.sh`, `lib/libtermux-exec.so`, `var/lib/dpkg/status`, and `SYMLINKS.txt`.
- Store symlinks in `SYMLINKS.txt`. Targets must stay inside the runtime prefix except for explicitly approved Android platform links.
- Remote generation requires the pinned public key and verifies signed `InRelease`, the `Packages` digest and size, and every downloaded package digest and size.
- `apt` must configure `etc/apt/sources.list.d/kothacode.sources` for `https://repo.code.amikotha.com`; the trusted key remains reachable through `etc/apt/trusted.gpg.d/termux-packages.gpg`.
- Publish immutable release objects first, optional aliases second, then verify all expected R2 objects.

The baseline bootstrap roots are:

```text
apt, bash, ca-certificates, curl, dash, findutils, git, gawk, jq,
openssh, patch, procps, psmisc, ripgrep, tar, termux-exec,
termux-tools, unzip, util-linux
```

Dependencies are recursively included from the signed repository. Optional roots must already be published there before bootstrap generation.

## Validation

Before committing CI/CD changes, run:

```sh
actionlint .github/workflows/_kothacode-build-publish.yml \
  .github/workflows/kothacode-package-repository.yml \
  .github/workflows/kothacode-package-queue.yml \
  .github/workflows/kothacode-bootstrap-release.yml
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_kothacode_repository
git diff --check
```

Also run `bash -n` on changed shell scripts and add focused tests for changed resolver, metadata, merge, replay, or integrity behavior.

For bootstrap contract changes, run a bounded bootstrap workflow and verify the manifest, archive hash and size, archive structure, and published R2 objects. When the app checkout is available, also run its `verifyEmbeddedBootstrap` task and packaged-bootstrap compatibility tests.

Use a live GitHub dispatch when Actions expression typing, reusable workflow evaluation, replay, or publication behavior cannot be verified locally. Use the smallest bounded request and record the run URL. Never publish unsafe artifacts to make a run pass.

Update `KOTHACODE_REPO.md` whenever operator-visible secrets, inputs, queue behavior, replay semantics, repository layout, or bootstrap release behavior changes.
