#!/usr/bin/env python3
"""Resolve a bounded KothaCode package build plan."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PACKAGE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
RUNNER_LABEL_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class PlanError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("manual", "scheduled", "queue-scheduled", "queue-manual"),
        required=True,
    )
    parser.add_argument("--packages", default="")
    parser.add_argument("--policy", default=".github/kothacode-package-policy.json")
    parser.add_argument("--queue-file")
    parser.add_argument("--package-count", type=int)
    parser.add_argument("--resource-class", choices=("standard", "large"), default="standard")
    parser.add_argument("--packages-index-url", required=True)
    parser.add_argument("--large-runner-label", default="")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PlanError(f"Cannot read {path}: {error}") from error


def split_packages(value: str) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for package in re.split(r"[\s,]+", value.strip()):
        if not package:
            continue
        if not PACKAGE_NAME_RE.fullmatch(package):
            raise PlanError(f"Invalid package name: {package!r}")
        if package not in seen:
            seen.add(package)
            packages.append(package)
    return packages


def load_package_queue(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PlanError(f"Cannot read package queue {path}: {error}") from error
    packages: list[str] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, 1):
        package = line.split("#", 1)[0].strip()
        if not package:
            continue
        if not PACKAGE_NAME_RE.fullmatch(package):
            raise PlanError(f"Invalid package name in {path}:{line_number}: {package!r}")
        if package in seen:
            raise PlanError(f"Duplicate package in {path}:{line_number}: {package}")
        seen.add(package)
        packages.append(package)
    return packages


def parse_packages_index(contents: str) -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for paragraph in re.split(r"\n\s*\n", contents.strip()):
        fields: dict[str, str] = {}
        current = ""
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")) and current:
                fields[current] += "\n" + line
                continue
            if ":" not in line:
                continue
            current, value = line.split(":", 1)
            fields[current] = value.strip()
        package = fields.get("Package")
        version = fields.get("Version")
        if package and version:
            versions.setdefault(package, set()).add(version)
    return versions


def download_packages_index(url: str) -> dict[str, set[str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "KothaCode-Package-Resolver/1"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return parse_packages_index(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                print(f"Repository index does not exist yet: {url}", file=sys.stderr)
                return {}
            if error.code not in (408, 429) and error.code < 500:
                raise PlanError(f"Repository index returned HTTP {error.code}: {url}") from error
            last_error: Exception = error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
        if attempt < 3:
            time.sleep(attempt * 3)
    raise PlanError(f"Cannot download repository index after 3 attempts: {last_error}")


def resolve_root_paths(root: Path, package_dirs: list[str], packages: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for package in packages:
        matches = [directory for directory in package_dirs if (root / directory / package / "build.sh").is_file()]
        if not matches:
            raise PlanError(f"No enabled package definition found for {package}")
        if len(matches) > 1:
            raise PlanError(f"Package {package} exists in multiple enabled repositories: {', '.join(matches)}")
        result[package] = f"{matches[0]}/{package}"
    return result


def dependency_entries(root: Path, package_path: str, package_dirs: list[str]) -> list[tuple[str, str]]:
    command = [sys.executable, "scripts/buildorder.py", "-i", package_path, *package_dirs]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PlanError(f"Cannot resolve dependencies for {package_path}: {detail}")
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) != 2:
            raise PlanError(f"Unexpected buildorder output for {package_path}: {line!r}")
        entries.append((columns[0], columns[1]))
    return entries


def load_big_packages(root: Path, relative_path: str) -> set[str]:
    path = root / relative_path
    try:
        return {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError as error:
        raise PlanError(f"Cannot read big package list {path}: {error}") from error


def select_queue_roots(
    queue: list[str],
    root_paths: dict[str, str],
    dependency_cache: dict[str, list[tuple[str, str]]],
    published_versions: dict[str, set[str]],
    big_packages: set[str],
    mode: str,
    package_count: int | None,
    target_seconds: int,
    seconds_per_definition: int,
) -> dict:
    selected: list[str] = []
    skipped_published: list[str] = []
    blocked_large: list[str] = []
    deferred: list[str] = []
    estimated_paths: set[str] = set()

    for index, package in enumerate(queue):
        if published_versions.get(package):
            skipped_published.append(package)
            continue

        dependencies = dependency_cache[package]
        closure_paths = {root_paths[package], *(path for _, path in dependencies)}
        large_definitions = sorted({Path(path).name for path in closure_paths} & big_packages)
        if large_definitions:
            blocked_large.append(package)
            continue

        candidate_paths = {root_paths[package]}
        for dependency, dependency_path in dependencies:
            if not published_versions.get(dependency):
                candidate_paths.add(dependency_path)

        combined_paths = estimated_paths | candidate_paths
        if mode == "queue-scheduled" and len(combined_paths) * seconds_per_definition > target_seconds:
            deferred = queue[index:]
            break
        if mode == "queue-manual" and package_count is not None and len(selected) >= package_count:
            deferred = queue[index:]
            break

        selected.append(package)
        estimated_paths = combined_paths

    return {
        "selected": selected,
        "skipped_published": skipped_published,
        "blocked_large": blocked_large,
        "deferred": deferred,
        "estimated_build_definitions": sorted(estimated_paths),
        "estimated_seconds": len(estimated_paths) * seconds_per_definition,
    }


def main() -> int:
    args = parse_args()
    root = Path.cwd().resolve()
    policy = load_json(root / args.policy)
    if policy.get("schema") != 1:
        raise PlanError("Unsupported package policy schema")

    architecture = policy.get("architecture")
    package_dirs = policy.get("package_directories")
    resource_policy = policy.get("resource_classes", {}).get(args.resource_class)
    if not isinstance(architecture, str) or not isinstance(package_dirs, list) or not resource_policy:
        raise PlanError("Package policy is missing architecture, package directories, or resource class")

    queue_mode = args.mode.startswith("queue-")
    if (args.mode == "scheduled" or queue_mode) and args.resource_class != "standard":
        raise PlanError("Scheduled and queue builds may only use the standard resource class")

    if queue_mode:
        queue_file = args.queue_file or policy.get("queue_file")
        if not isinstance(queue_file, str) or not queue_file:
            raise PlanError("Package policy does not define queue_file")
        requested = load_package_queue(root / queue_file)
        if args.mode == "queue-manual":
            if args.package_count is None or args.package_count < 1:
                raise PlanError("Manual queue builds require a positive --package-count")
            max_count = int(policy.get("queue_manual_max_roots", 20))
            if args.package_count > max_count:
                raise PlanError(f"Requested {args.package_count} queue roots; limit is {max_count}")
    elif args.mode == "manual":
        requested = split_packages(args.packages)
    else:
        requested = split_packages(" ".join(policy.get("scheduled_roots", [])))
    if args.mode == "manual" and not requested:
        raise PlanError("Manual builds require at least one package")

    try:
        published_versions = download_packages_index(args.packages_index_url)
    except PlanError:
        if args.mode != "manual":
            raise
        print(
            "WARNING: The live repository index is unavailable; manual mode will use a conservative full-closure estimate.",
            file=sys.stderr,
        )
        published_versions = {}
    root_paths = resolve_root_paths(root, package_dirs, requested)

    dependency_cache = {
        package: dependency_entries(root, root_paths[package], package_dirs)
        for package in requested
        if not queue_mode or not published_versions.get(package)
    }

    queue_result: dict | None = None
    if queue_mode:
        seconds_per_definition = int(policy.get("queue_estimated_seconds_per_definition", 48))
        target_seconds = int(policy.get("queue_scheduled_target_seconds", 14400))
        if seconds_per_definition < 1 or target_seconds < 1:
            raise PlanError("Queue timing policy values must be positive")
        queue_result = select_queue_roots(
            requested,
            root_paths,
            dependency_cache,
            published_versions,
            load_big_packages(root, policy["big_packages_file"]),
            args.mode,
            args.package_count,
            target_seconds,
            seconds_per_definition,
        )
        requested = queue_result["selected"]
        root_paths = {package: root_paths[package] for package in requested}

    if args.mode == "scheduled":
        requested = [
            package
            for package in requested
            if not published_versions.get(package)
            or any(
                not published_versions.get(dependency)
                for dependency, _ in dependency_cache[package]
            )
        ]
        root_paths = {package: root_paths[package] for package in requested}

    if not queue_mode:
        max_roots_key = "manual_max_roots" if args.mode == "manual" else "scheduled_max_roots"
        max_roots = int(resource_policy[max_roots_key])
        if args.mode == "scheduled":
            requested = requested[:max_roots]
            root_paths = {package: root_paths[package] for package in requested}
        elif len(requested) > max_roots:
            raise PlanError(f"Requested {len(requested)} roots; {args.resource_class} limit is {max_roots}")

    if not requested:
        plan = {
            "schema": 1,
            "mode": args.mode,
            "architecture": architecture,
            "resource_class": args.resource_class,
            "should_build": False,
            "roots": [],
            "reason": (
                "No eligible unpublished package roots remain in the queue"
                if queue_mode
                else "All scheduled package roots already match the live repository"
            ),
            "runner_label": resource_policy["runner"],
            "min_disk_gb": resource_policy["min_disk_gb"],
            "min_memory_gb": resource_policy["min_memory_gb"],
        }
        if queue_result is not None:
            plan["queue"] = queue_result
        Path(args.output).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        return 0

    closure_paths = set(root_paths.values())
    missing_dependency_paths: set[str] = set()
    dependency_packages: set[str] = set()
    for package in requested:
        for dependency, dependency_path in dependency_cache[package]:
            dependency_packages.add(dependency)
            closure_paths.add(dependency_path)
            if not published_versions.get(dependency):
                missing_dependency_paths.add(dependency_path)

    if not queue_mode:
        max_closure = int(resource_policy["max_closure_definitions"])
        if len(closure_paths) > max_closure:
            raise PlanError(f"Dependency closure has {len(closure_paths)} definitions; limit is {max_closure}")

    estimated_build_paths = set(root_paths.values()) | missing_dependency_paths
    if not queue_mode:
        max_estimated = int(resource_policy["max_estimated_build_definitions"])
        if len(estimated_build_paths) > max_estimated:
            raise PlanError(
                f"Estimated local build set has {len(estimated_build_paths)} definitions; limit is {max_estimated}"
            )

    big_packages = load_big_packages(root, policy["big_packages_file"])
    large_definitions = sorted({Path(path).name for path in closure_paths} & big_packages)
    if args.mode != "manual" and args.resource_class == "standard" and large_definitions:
        raise PlanError(
            "Standard build closure contains large packages: " + ", ".join(large_definitions)
        )

    if args.resource_class == "large":
        runner_label = args.large_runner_label.strip()
        if not runner_label:
            variable = resource_policy.get("runner_variable", "KOTHACODE_LARGE_RUNNER_LABEL")
            raise PlanError(f"Large builds require repository variable {variable}")
        if not RUNNER_LABEL_RE.fullmatch(runner_label):
            raise PlanError(f"Unsafe large runner label: {runner_label!r}")
    else:
        runner_label = resource_policy["runner"]

    plan = {
        "schema": 1,
        "mode": args.mode,
        "architecture": architecture,
        "resource_class": args.resource_class,
        "should_build": True,
        "roots": requested,
        "dependency_packages": sorted(dependency_packages),
        "closure_definitions": sorted(closure_paths),
        "missing_dependency_definitions": sorted(missing_dependency_paths),
        "estimated_build_definitions": sorted(estimated_build_paths),
        "replacement_packages": [],
        "large_definitions": large_definitions,
        "counts": {
            "roots": len(requested),
            "closure_definitions": len(closure_paths),
            "missing_dependency_definitions": len(missing_dependency_paths),
            "estimated_build_definitions": len(estimated_build_paths),
        },
        "runner_label": runner_label,
        "min_disk_gb": resource_policy["min_disk_gb"],
        "min_memory_gb": resource_policy["min_memory_gb"],
    }
    if queue_result is not None:
        plan["queue"] = queue_result
    Path(args.output).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(
        f"Resolved {len(requested)} roots, {len(closure_paths)} closure definitions, "
        f"and {len(estimated_build_paths)} estimated local builds.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlanError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
