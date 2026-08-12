# KothaCode Termux Repository

This fork builds KothaCode-targeted Termux packages and bootstraps for:

```text
/data/data/com.amikotha.code/files/usr
```

The public APT repository URL is:

```text
https://repo.code.amikotha.com
```

The Cloudflare R2 bucket is:

```text
kothacode-termux-repo
```

## GitHub Secrets

Add these secrets to the `termux-packages` GitHub repository before running the workflow:

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
APT_GPG_PRIVATE_KEY
APT_GPG_PASSPHRASE
APT_GPG_PUBLIC_KEY
```

`APT_GPG_PASSPHRASE` may be blank if the key has no passphrase.

`APT_GPG_PUBLIC_KEY` must be the armored export of the same signing key. Package
builders and bootstrap jobs receive only this public key. The private key is
confined to the serialized repository publication job.

## Create The Signing Key

Create a dedicated repository signing key locally:

```sh
gpg --quick-generate-key "KothaCode Termux Repo <repo@code.amikotha.com>" rsa4096 sign 2y
```

Export the private key for `APT_GPG_PRIVATE_KEY`:

```sh
gpg --armor --export-secret-keys "KothaCode Termux Repo <repo@code.amikotha.com>"
```

Export the public key if you want to set `APT_GPG_PUBLIC_KEY` explicitly:

```sh
gpg --armor --export "KothaCode Termux Repo <repo@code.amikotha.com>"
```

## Package Publishing

The legacy package workflow is intentionally manual-only. Use it for an explicit
bounded set of package roots or to republish package artifacts from a successful
workflow run:

```text
.github/workflows/kothacode-package-repository.yml
```

Its package input is blank by default. Enter package roots explicitly, or provide
`reuse_run_id` to skip compilation and republish the unexpired `debs-aarch64` or
`kothacode-debs-aarch64` artifact from that successful run.

## Daily Package Queue

The daily workflow is:

```text
.github/workflows/kothacode-package-queue.yml
```

It runs at `02:17 UTC` and reads the ordered roots in
`.github/kothacode-package-queue.txt`. Edit that file to control what should be
built. The standard APT index at
`dists/stable/main/binary-aarch64/Packages` is the authoritative R2 inventory;
roots already present there are skipped.

For scheduled runs, the resolver deduplicates each root's dependency closure and
counts only source definitions whose exact expected package version is absent
from R2. It selects roots until the estimated compile time reaches four hours.
The current conservative estimate is 48 seconds per source definition: the
successful bootstrap baseline compiled 114 unique definitions in roughly 90
minutes. The six-hour job timeout leaves setup, publication, and estimation
error headroom.

Manual queue runs take a package count instead of applying the time estimate.
For example, `package_count=3` selects the next three eligible unpublished roots.
Both scheduled and manual queue builds use `build-package.sh -i`, so exact-version
dependencies already published in the signed KothaCode repository are downloaded
instead of rebuilt. The queue workflow also accepts `reuse_run_id` for artifact
republication without compilation.

Publication is incremental. New package files and content-addressed metadata are
uploaded before `Packages`, `Release`, and signed `InRelease`; existing unrelated
package records and pool objects are preserved. A partial build never uses
`aws s3 sync --delete`.

Large packages from `scripts/big-pkgs.list` require `resource_class=large` and a
repository variable named `KOTHACODE_LARGE_RUNNER_LABEL`. Large scheduled builds
are disabled.

## Bootstrap Release

After the required package set has been published, run:

```text
.github/workflows/kothacode-bootstrap-release.yml
```

The workflow verifies the signed package index, creates an immutable versioned
release, and optionally updates these latest aliases:

```text
https://repo.code.amikotha.com/bootstrap/bootstrap-aarch64.zip
https://repo.code.amikotha.com/bootstrap/bootstrap-aarch64.manifest.json
```

The archive key is published at
`https://repo.code.amikotha.com/kothacode-archive-key.gpg` by the package
workflow.

Supplying `reuse_run_id` preserves the previous CI behavior: it republishes the
package artifacts from that successful run and then generates a fresh bootstrap.
The run ID refers to a package workflow run, not an old bootstrap archive.

The first KothaCode repo profile is `aarch64` only, which targets normal 64-bit Android devices (`arm64-v8a`). Add `arm` or `x86_64` later only if old phones, emulators, Chromebooks, or Android-x86 are required.

## Expanding The Bootstrap

The default bootstrap is agent-focused and includes shell/APT basics plus `git`, `openssh`, `ripgrep`, `jq`, `patch`, and `unzip`. After the minimal bootstrap works, add larger language/toolchain packages through the workflow input:

```text
bootstrap_extra_packages=python,nodejs
```

Those packages must exist in the published KothaCode repo first. Publish them
through the package workflow before generating a bootstrap.

## Important

Do not publish official Termux packages into this repo unless they were built for `com.amikotha.code`. Packages built for `com.termux` contain incompatible absolute paths.
