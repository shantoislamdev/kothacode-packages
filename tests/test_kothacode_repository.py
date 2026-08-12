#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
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


class PackageIndexTests(unittest.TestCase):
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

    def test_static_dependency_uses_parent_version(self):
        self.assertEqual(
            resolver.expected_version_for(
                "demo-static", {"demo": "1"}, {"demo": "demo"}
            ),
            "1",
        )

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

    def test_missing_dependency_version_is_detected(self):
        self.assertTrue(
            resolver.package_is_missing(
                "demo", {"demo": "2"}, {"demo": "demo"}, {"demo": {"1"}}
            )
        )

    def test_missing_explicit_subpackage_marks_definition_missing(self):
        expected = {"demo": "1", "demo-extra": "1"}
        parents = {"demo": "demo", "demo-extra": "demo"}
        published = {"demo": {"1"}}
        self.assertTrue(
            resolver.definition_is_missing(
                "packages/demo", expected, parents, published
            )
        )


if __name__ == "__main__":
    unittest.main()
