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
```

`APT_GPG_PASSPHRASE` may be blank if the key has no passphrase.

Optional:

```text
APT_GPG_PUBLIC_KEY
```

If `APT_GPG_PUBLIC_KEY` is not set, the workflow exports the public key from `APT_GPG_PRIVATE_KEY` and packages it into `termux-keyring`.

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

## First Workflow Run

Run this workflow manually:

```text
.github/workflows/kothacode-termux-repo.yml
```

Use the default package list first. It builds the minimal packages needed for the bootstrap and APT runtime.

The workflow does three things:

```text
build-packages -> publish-repo -> build-bootstraps
```

Expected public files after success:

```text
https://repo.code.amikotha.com/dists/stable/main/binary-aarch64/Packages
https://repo.code.amikotha.com/bootstrap/bootstrap-aarch64.zip
```

The first KothaCode repo profile is `aarch64` only, which targets normal 64-bit Android devices (`arm64-v8a`). Add `arm` or `x86_64` later only if old phones, emulators, Chromebooks, or Android-x86 are required.

## Expanding The Bootstrap

The default bootstrap is agent-focused and includes shell/APT basics plus `git`, `openssh`, `ripgrep`, `jq`, `patch`, and `unzip`. After the minimal bootstrap works, add larger language/toolchain packages through the workflow input:

```text
bootstrap_extra_packages=python,nodejs
```

Those packages must exist in the published KothaCode repo first. Add them to the workflow `packages` input in the same run or a previous run.

## Important

Do not publish official Termux packages into this repo unless they were built for `com.amikotha.code`. Packages built for `com.termux` contain incompatible absolute paths.
