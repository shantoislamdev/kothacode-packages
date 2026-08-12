#!/usr/bin/env python3
"""Merge new deb metadata into an existing APT Packages index."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path


PACKAGE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
COMPUTED_FIELDS = {"filename", "size", "md5sum", "sha1", "sha256", "installed-size"}


class MergeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--new-pool-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-packages")
    parser.add_argument("--replacement-packages")
    parser.add_argument("--rebuildable-packages")
    return parser.parse_args()


def parse_records(contents: str) -> list[OrderedDict[str, str]]:
    records: list[OrderedDict[str, str]] = []
    for paragraph in re.split(r"\n\s*\n", contents.strip()):
        if not paragraph.strip():
            continue
        record: OrderedDict[str, str] = OrderedDict()
        current = ""
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")):
                if not current:
                    raise MergeError("Continuation line without a field in Packages metadata")
                record[current] += "\n" + line
                continue
            if ":" not in line:
                raise MergeError(f"Malformed Packages metadata line: {line!r}")
            current, value = line.split(":", 1)
            record[current] = value.lstrip()
        records.append(record)
    return records


def serialize_record(record: OrderedDict[str, str]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in record.items()) + "\n"


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_versions(left: str, operator: str, right: str) -> bool:
    result = subprocess.run(
        ["dpkg", "--compare-versions", left, operator, right],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise MergeError(result.stderr.strip() or f"dpkg could not compare {left!r} and {right!r}")
    return result.returncode == 0


def validate_record(record: OrderedDict[str, str], source: str) -> None:
    for field in ("Package", "Version", "Architecture"):
        if not record.get(field):
            raise MergeError(f"{source} is missing required field {field}")
    if not PACKAGE_NAME_RE.fullmatch(record["Package"]):
        raise MergeError(f"{source} has invalid package name {record['Package']!r}")


def select_record(
    selected: dict[str, OrderedDict[str, str]],
    candidate: OrderedDict[str, str],
    source: str,
) -> None:
    validate_record(candidate, source)
    package = candidate["Package"]
    current = selected.get(package)
    if not current:
        selected[package] = candidate
        return
    if compare_versions(candidate["Version"], "gt", current["Version"]):
        selected[package] = candidate
        return
    if compare_versions(candidate["Version"], "lt", current["Version"]):
        return
    if candidate.get("SHA256") != current.get("SHA256"):
        raise MergeError(f"Conflicting hashes for {package} version {candidate['Version']}")


def record_for_deb(deb: Path, pool_root: Path) -> OrderedDict[str, str]:
    result = subprocess.run(
        ["dpkg-deb", "--field", str(deb)],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise MergeError(f"Cannot read {deb}: {result.stderr.strip()}")
    records = parse_records(result.stdout)
    if len(records) != 1:
        raise MergeError(f"Unexpected control metadata in {deb}")
    control = OrderedDict(
        (key, value) for key, value in records[0].items() if key.lower() not in COMPUTED_FIELDS
    )
    validate_record(control, str(deb))
    size = deb.stat().st_size
    installed_size_result = subprocess.run(
        ["dpkg-deb", "--field", str(deb), "Installed-Size"],
        check=False,
        text=True,
        capture_output=True,
    )
    installed_size = installed_size_result.stdout.strip()
    if installed_size_result.returncode != 0 or not installed_size:
        raise MergeError(f"Cannot read Installed-Size for {deb}: {installed_size_result.stderr.strip()}")
    control["Installed-Size"] = installed_size
    control["Filename"] = deb.relative_to(pool_root.parent.parent).as_posix()
    control["Size"] = str(size)
    control["MD5sum"] = hash_file(deb, "md5")
    control["SHA1"] = hash_file(deb, "sha1")
    control["SHA256"] = hash_file(deb, "sha256")
    return control


def main() -> int:
    args = parse_args()
    pool_root = Path(args.new_pool_dir).resolve()
    selected: dict[str, OrderedDict[str, str]] = {}

    if args.base_packages:
        base_path = Path(args.base_packages)
        if base_path.is_file():
            for record in parse_records(base_path.read_text(encoding="utf-8")):
                architecture = record.get("Architecture")
                if architecture not in (args.architecture, "all"):
                    raise MergeError(
                        f"Base index contains {record.get('Package', '<unknown>')} for unexpected architecture {architecture}"
                    )
                select_record(selected, record, str(base_path))

    new_records: dict[str, OrderedDict[str, str]] = {}
    for deb in sorted(pool_root.rglob("*.deb")):
        record = record_for_deb(deb, pool_root)
        if record["Architecture"] not in (args.architecture, "all"):
            continue
        select_record(new_records, record, str(deb))

    if not new_records:
        raise MergeError(f"No new packages found for architecture {args.architecture}")

    replacement_packages: set[str] = set()
    if args.replacement_packages:
        replacement_path = Path(args.replacement_packages)
        if not replacement_path.is_file():
            raise MergeError(f"Replacement package list does not exist: {replacement_path}")
        for line in replacement_path.read_text(encoding="utf-8").splitlines():
            package = line.strip()
            if not package:
                continue
            if not PACKAGE_NAME_RE.fullmatch(package):
                raise MergeError(f"Invalid replacement package name: {package!r}")
            replacement_packages.add(package)

    rebuildable_packages: set[str] = set()
    if args.rebuildable_packages:
        rebuildable_path = Path(args.rebuildable_packages)
        if not rebuildable_path.is_file():
            raise MergeError(f"Rebuildable package list does not exist: {rebuildable_path}")
        for line in rebuildable_path.read_text(encoding="utf-8").splitlines():
            package = line.strip()
            if not package:
                continue
            if not PACKAGE_NAME_RE.fullmatch(package):
                raise MergeError(f"Invalid rebuildable package name: {package!r}")
            rebuildable_packages.add(package)

    existing_filenames = {
        record.get("Filename"): (record["Package"], record.get("SHA256"))
        for record in selected.values()
        if record.get("Filename")
    }
    for package, record in new_records.items():
        current = selected.get(package)
        if current:
            if compare_versions(record["Version"], "lt", current["Version"]):
                if package in rebuildable_packages and package not in replacement_packages:
                    continue
                raise MergeError(f"Refusing downgrade of {package}: {current['Version']} -> {record['Version']}")
            if compare_versions(record["Version"], "eq", current["Version"]):
                if record["SHA256"] != current.get("SHA256"):
                    raise MergeError(
                        f"Refusing same-version content change for {package} {record['Version']}; bump the package revision"
                    )
                continue
        filename_owner = existing_filenames.get(record["Filename"])
        if filename_owner and filename_owner != (package, record["SHA256"]):
            raise MergeError(f"Pool filename collision: {record['Filename']}")
        if current and current.get("Filename") == record["Filename"] and current.get("SHA256") != record["SHA256"]:
            raise MergeError(
                f"Refusing pool object overwrite for {package} {record['Version']}; bump the package revision"
            )
        selected[package] = record

    for package in replacement_packages - new_records.keys():
        selected.pop(package, None)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as destination:
        for package in sorted(selected):
            destination.write(serialize_record(selected[package]))
            destination.write("\n")
    if not selected:
        raise MergeError("Merged Packages index is empty")
    print(f"Merged {len(new_records)} new records into {len(selected)} indexed packages.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MergeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
