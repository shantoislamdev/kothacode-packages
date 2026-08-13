#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge = load_script("merge-kothacode-packages.py")
resolver = load_script("resolve-kothacode-packages.py")
hash_lookup = load_script("get_hash_from_file.py")


class PackageIndexTests(unittest.TestCase):
    def test_dependency_lookup_handles_upstream_field_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            packages = Path(temporary) / "Packages"
            packages.write_text(
                "Package: demo\nVersion: 1\nFilename: pool/demo.deb\nSHA256: abc123\n\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with mock.patch("sys.stdout", output):
                hash_lookup.get_pkg_hash_from_Packages(packages, "demo", "1")
            self.assertEqual(output.getvalue(), "pool/demo.deb abc123\n")

    def test_parses_multiline_fields(self):
        records = merge.parse_records(
            "Package: demo\nVersion: 1\nArchitecture: aarch64\nDescription: first line\n second line\n\n"
        )
        self.assertEqual(records[0]["Description"], "first line\n second line")

    def test_rejects_same_version_hash_conflict(self):
        selected: dict[str, OrderedDict[str, str]] = {}
        first = OrderedDict(
            Package="demo", Version="1", Architecture="aarch64", SHA256="a"
        )
        second = OrderedDict(
            Package="demo", Version="1", Architecture="aarch64", SHA256="b"
        )
        with mock.patch.object(merge, "compare_versions", side_effect=lambda left, op, right: op == "eq"):
            merge.select_record(selected, first, "first")
            with self.assertRaises(merge.MergeError):
                merge.select_record(selected, second, "second")

    def test_resolver_index_collects_all_versions(self):
        versions = resolver.parse_packages_index(
            "Package: demo\nVersion: 1\n\nPackage: demo\nVersion: 2\n\n"
        )
        self.assertEqual(versions, {"demo": {"1", "2"}})

    def test_new_pool_filename_keeps_pool_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            deb = repository / "pool" / "main" / "aarch64" / "demo_1_aarch64.deb"
            deb.parent.mkdir(parents=True)
            deb.write_bytes(b"deb")
            control = "Package: demo\nVersion: 1\nArchitecture: aarch64\nDescription: demo\n"
            completed = mock.Mock(returncode=0, stdout=control, stderr="")
            installed_size = mock.Mock(returncode=0, stdout="1\n", stderr="")
            with mock.patch.object(
                merge.subprocess, "run", side_effect=[completed, installed_size]
            ):
                record = merge.record_for_deb(deb, repository / "pool" / "main")
            self.assertEqual(record["Filename"], "pool/main/aarch64/demo_1_aarch64.deb")

    def test_queue_parser_supports_comments_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            queue = Path(temporary) / "queue.txt"
            queue.write_text("# tools\nnano # editor\n\ntmux\n", encoding="utf-8")
            self.assertEqual(resolver.load_package_queue(queue), ["nano", "tmux"])
            queue.write_text("nano\nnano\n", encoding="utf-8")
            with self.assertRaises(resolver.PlanError):
                resolver.load_package_queue(queue)

    def test_scheduled_queue_skips_published_and_respects_time_budget(self):
        result = resolver.select_queue_roots(
            ["present", "first", "second"],
            {"present": "packages/present", "first": "packages/first", "second": "packages/second"},
            {
                "first": [("dep", "packages/shared"), ("dep-extra", "packages/shared")],
                "second": [("other", "packages/shared"), ("new", "packages/new")],
            },
            {"present": {"1"}, "other": {"1"}},
            set(),
            "queue-scheduled",
            None,
            96,
            48,
        )
        self.assertEqual(result["selected"], ["first"])
        self.assertEqual(result["skipped_published"], ["present"])
        self.assertEqual(result["deferred"], ["second"])
        self.assertEqual(result["estimated_build_definitions"], ["packages/first", "packages/shared"])

    def test_manual_queue_uses_root_count_without_time_limit(self):
        result = resolver.select_queue_roots(
            ["one", "two", "three"],
            {name: f"packages/{name}" for name in ("one", "two", "three")},
            {name: [] for name in ("one", "two", "three")},
            {},
            set(),
            "queue-manual",
            2,
            1,
            48,
        )
        self.assertEqual(result["selected"], ["one", "two"])
        self.assertEqual(result["deferred"], ["three"])


if __name__ == "__main__":
    unittest.main()
