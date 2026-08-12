#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
	echo "Usage: scripts/preflight-kothacode-sources.sh PACKAGE..." >&2
	exit 2
fi

declare -a package_dirs=()
mapfile -t enabled_repositories < <(jq --raw-output 'del(.pkg_format) | keys[]' repo.json)
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

for package in "$@"; do
	if [[ ! "$package" =~ ^[a-z0-9][a-z0-9+.-]*$ ]]; then
		echo "Invalid package name: $package" >&2
		exit 1
	fi
	found=""
	for repository in "${enabled_repositories[@]}"; do
		if [[ -f "$repository/$package/build.sh" ]]; then
			found="$repository/$package"
			break
		fi
	done
	if [[ -z "$found" ]]; then
		echo "No enabled package definition found for $package" >&2
		exit 1
	fi
	python3 scripts/buildorder.py -i "$found" "${enabled_repositories[@]}" >> "$tmpfile"
	echo "$found" >> "$tmpfile"
done
mapfile -t package_dirs < <(awk 'NF == 1 { print $1 } NF > 1 { print $2 }' "$tmpfile" | LC_ALL=C sort -u)

failed=0
for directory in "${package_dirs[@]}"; do
	build_script="$directory/build.sh"
	[[ -f "$build_script" ]] || continue
	mapfile -t urls < <(
		set +e +u
		export TERMUX_SCRIPTDIR="$PWD"
		if source scripts/properties.sh >/dev/null 2>&1 && source "$build_script" >/dev/null 2>&1; then
			if [[ -n "${TERMUX_PKG_SRCURL+x}" ]]; then
				for url in "${TERMUX_PKG_SRCURL[@]}"; do
					[[ -n "$url" ]] && printf '%s\n' "$url"
				done
			fi
		else
			echo "__SRCURL_EVALUATION_FAILED__"
		fi
	)
	if [[ "${urls[0]:-}" == "__SRCURL_EVALUATION_FAILED__" ]]; then
		echo "::error::Failed to evaluate TERMUX_PKG_SRCURL for $directory"
		failed=1
		continue
	fi
	if ((${#urls[@]} == 0)); then
		echo "SKIP $directory (no external source URL)"
		continue
	fi
	for url in "${urls[@]}"; do
		case "$url" in
			git+file://*) echo "SKIP $directory <- $url (local git source)"; continue ;;
			git+*://*)
				remote="${url#git+}"
				if timeout 60 git ls-remote --exit-code "$remote" HEAD >/dev/null 2>&1; then
					echo "OK   $directory <- $url (git)"
				else
					echo "::warning::Could not probe git source for $directory; the build will retry it: $url"
				fi
				continue
				;;
			file://*) echo "SKIP $directory <- $url (local source)"; continue ;;
		esac
		rc=0
		code=$(curl --location --silent --show-error \
			--connect-timeout 20 --max-time 60 --retry 2 --retry-delay 3 --retry-max-time 60 \
			--range 0-0 --output /dev/null -w '%{http_code}' "$url" 2>/dev/null) || rc=$?
		if ((rc == 0)) && [[ "$code" =~ ^[23][0-9][0-9]$ ]]; then
			echo "OK   $directory <- $url"
		elif ((rc == 0)) && [[ "$code" == "404" || "$code" == "410" ]]; then
			echo "::error::Source URL for $directory returned definitive HTTP $code: $url"
			failed=1
		elif ((rc == 0)); then
			echo "::warning::Source URL probe for $directory returned HTTP $code; the build downloader will retry it: $url"
		else
			echo "::warning::Could not connect to source URL for $directory (curl exit $rc); the build downloader will retry it: $url"
		fi
	done
done

if ((failed)); then
	echo "::error::One or more package source URLs are definitively unavailable."
	exit 1
fi
echo "Source URL preflight completed without definitive failures."
