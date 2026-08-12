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

Run this workflow manually for initial publication or an explicit bounded set of
package roots:

```text
.github/workflows/kothacode-package-repository.yml
```

The weekly schedule checks the curated roots in
`.github/kothacode-package-policy.json` and builds at most four roots whose
versions are absent from the live index. Manual standard builds accept at most
20 roots. Both modes enforce dependency-closure, disk, and memory budgets.

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
