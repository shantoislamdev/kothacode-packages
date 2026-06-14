#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: scripts/generate-kothacode-apt-repo.sh --input-dir DIR --output-dir DIR

Build a minimal Debian/Termux APT repository from .deb files.

Environment:
  APT_REPO_ORIGIN        Release Origin field. Default: KothaCode
  APT_REPO_LABEL         Release Label field. Default: KothaCode Termux
  APT_REPO_SUITE         Release Suite/Codename. Default: stable
  APT_REPO_COMPONENT     Release component. Default: main
  APT_REPO_ARCHES        Space-separated arch list. Default: aarch64
  APT_SIGN_REPO          true/false. Default: true
  APT_GPG_SIGNING_KEY    Optional gpg key id/fingerprint for signing.
  APT_GPG_PASSPHRASE     Optional passphrase for the signing key.
EOF
}

input_dir=""
output_dir=""

while (($# > 0)); do
	case "$1" in
		--input-dir)
			input_dir="${2:-}"
			shift 2
			;;
		--output-dir)
			output_dir="${2:-}"
			shift 2
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Unknown argument: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

if [[ -z "$input_dir" || -z "$output_dir" ]]; then
	usage >&2
	exit 2
fi

if [[ ! -d "$input_dir" ]]; then
	echo "Input directory does not exist: $input_dir" >&2
	exit 1
fi

input_dir="$(realpath "$input_dir")"
output_dir="$(realpath -m "$output_dir")"

if [[ -z "$output_dir" || "$output_dir" == "/" ]]; then
	echo "Refusing unsafe output directory: $output_dir" >&2
	exit 1
fi

for cmd in dpkg-deb find gzip md5sum realpath sha1sum sha256sum sort stat xz; do
	if ! command -v "$cmd" >/dev/null 2>&1; then
		echo "Required command not found: $cmd" >&2
		exit 1
	fi
done

repo_origin="${APT_REPO_ORIGIN:-KothaCode}"
repo_label="${APT_REPO_LABEL:-KothaCode Termux}"
suite="${APT_REPO_SUITE:-stable}"
component="${APT_REPO_COMPONENT:-main}"
architectures="${APT_REPO_ARCHES:-aarch64}"
sign_repo="${APT_SIGN_REPO:-true}"

mapfile -t debs < <(find "$input_dir" -type f -name '*.deb' | sort)
if [[ "${#debs[@]}" -eq 0 ]]; then
	echo "No .deb files found in $input_dir" >&2
	exit 1
fi

rm -rf "$output_dir"
mkdir -p "$output_dir/pool/main"

echo "[*] Copying ${#debs[@]} .deb files into pool/"
for deb in "${debs[@]}"; do
	arch="$(dpkg-deb -f "$deb" Architecture)"
	package="$(dpkg-deb -f "$deb" Package)"
	if [[ -z "$arch" || -z "$package" ]]; then
		echo "Invalid .deb metadata: $deb" >&2
		exit 1
	fi
	mkdir -p "$output_dir/pool/main/$arch"
	cp -f "$deb" "$output_dir/pool/main/$arch/$(basename "$deb")"
done

emit_packages_file() {
	local arch="$1"
	local binary_dir="$output_dir/dists/$suite/$component/binary-$arch"
	local packages_file="$binary_dir/Packages"

	mkdir -p "$binary_dir"
	: > "$packages_file"

	while IFS= read -r deb; do
		local package_arch rel_path size md5 sha1 sha256
		package_arch="$(dpkg-deb -f "$deb" Architecture)"
		if [[ "$package_arch" != "$arch" && "$package_arch" != "all" ]]; then
			continue
		fi

		rel_path="${deb#"$output_dir/"}"
		size="$(stat -c '%s' "$deb")"
		md5="$(md5sum "$deb" | awk '{ print $1 }')"
		sha1="$(sha1sum "$deb" | awk '{ print $1 }')"
		sha256="$(sha256sum "$deb" | awk '{ print $1 }')"

		{
			dpkg-deb -f "$deb"
			echo "Filename: $rel_path"
			echo "Size: $size"
			echo "MD5sum: $md5"
			echo "SHA1: $sha1"
			echo "SHA256: $sha256"
			echo
		} >> "$packages_file"
	done < <(find "$output_dir/pool/main" -type f -name '*.deb' | sort)

	if [[ ! -s "$packages_file" ]]; then
		echo "No packages found for architecture: $arch" >&2
		exit 1
	fi

	gzip -n -9 -c "$packages_file" > "$packages_file.gz"
	xz -T0 -9 -c "$packages_file" > "$packages_file.xz"
}

echo "[*] Generating Packages metadata"
for arch in $architectures; do
	emit_packages_file "$arch"
done

suite_dir="$output_dir/dists/$suite"
release_file="$suite_dir/Release"

mapfile -t release_files < <(
	find "$suite_dir" -type f \
		! -name Release \
		! -name InRelease \
		! -name Release.gpg \
		| sort
)

write_hash_block() {
	local label="$1"
	local command_name="$2"

	echo "$label:" >> "$release_file"
	for file in "${release_files[@]}"; do
		local rel_path hash size
		rel_path="${file#"$suite_dir/"}"
		hash="$($command_name "$file" | awk '{ print $1 }')"
		size="$(stat -c '%s' "$file")"
		printf ' %s %16s %s\n' "$hash" "$size" "$rel_path" >> "$release_file"
	done
}

echo "[*] Generating Release metadata"
cat > "$release_file" <<EOF
Origin: $repo_origin
Label: $repo_label
Suite: $suite
Codename: $suite
Date: $(date -Ru)
Architectures: $architectures
Components: $component
Description: KothaCode Termux package repository
EOF

write_hash_block "MD5Sum" md5sum
write_hash_block "SHA1" sha1sum
write_hash_block "SHA256" sha256sum

if [[ "$sign_repo" == "true" ]]; then
	if ! command -v gpg >/dev/null 2>&1; then
		echo "APT_SIGN_REPO=true but gpg is not installed" >&2
		exit 1
	fi

	gpg_args=(--batch --yes --pinentry-mode loopback)
	if [[ -n "${APT_GPG_PASSPHRASE:-}" ]]; then
		gpg_args+=(--passphrase "$APT_GPG_PASSPHRASE")
	fi
	if [[ -n "${APT_GPG_SIGNING_KEY:-}" ]]; then
		gpg_args+=(--local-user "$APT_GPG_SIGNING_KEY")
	fi

	echo "[*] Signing Release metadata"
	gpg "${gpg_args[@]}" --clearsign \
		--output "$suite_dir/InRelease" \
		"$release_file"
	gpg "${gpg_args[@]}" --armor --detach-sign \
		--output "$suite_dir/Release.gpg" \
		"$release_file"
else
	echo "[!] APT_SIGN_REPO=false; generated repository is unsigned"
fi

echo "[*] Repository generated at $output_dir"
