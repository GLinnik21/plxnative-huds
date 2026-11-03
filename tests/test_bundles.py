"""Bundle transport tests use opaque test bytes, never claim native ZIP validation."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog
import simulator
import recheck


FORMATS = [{"package": "1.0", "hud": "1.0"}]
SCHEMAS = {kind: {"1.0": f"https://plxnative.com/hud/schema/{kind}/1.0.json"}
           for kind in ("manifest", "hud")}
LIMITS = {"package": {"1.0": {"artifact_bytes": 2 * 1024 * 1024}}, "hud": {"1.0": {"json_bytes": 1024 * 1024}}}


def metadata(ident="org.example.hud"):
    return {"package_format": "1.0", "hud": {"format": "1.0", "entry": "hud.json"},
            "id": ident, "version": "1.0.0", "name": "Example", "author": "Author", "license": "CC0-1.0"}


def pin(version="0.10.0"):
    return {"protocol": 1, "app_version": version, "source_sha": "a" * 40,
            "sha256": "b" * 64, "manifest_sha256": "c" * 64, "bytes": 100,
            "url": f"https://github.com/GLinnik21/plx-native/releases/download/v{version}/sim.tar.gz",
            "calibration": "calibration/measured.json", "supported_formats": FORMATS,
            "schemas": SCHEMAS, "limits": LIMITS}


class Bundles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_sources_read_manifest_without_rewriting_order_sensitive_hud(self):
        directory = self.root / "huds/org.example.hud"
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_bytes(catalog.canonical(metadata()))
        (directory / "README.md").write_text("A bundle source\n")
        hud = b'{"layout":{"if":{"paused":1,"chapters.present":2}}}\n'
        (directory / "hud.json").write_bytes(hud)
        source = catalog.sources(self.root)[0]
        self.assertEqual(source.path, directory)
        self.assertEqual(source.metadata, metadata())
        self.assertEqual((directory / "hud.json").read_bytes(), hud)

    def test_flat_format_pin_cannot_claim_bundle_support(self):
        value = pin()
        for key in ("supported_formats", "schemas", "limits"):
            value.pop(key)
        value["formats"] = ["1.0"]
        with self.assertRaisesRegex(catalog.Invalid, "supported_formats"):
            simulator.validate_pin(value)

    def test_oldest_pin_must_support_both_version_axes(self):
        source = catalog.Source(self.root, metadata())
        wrong = {**pin("0.9.0"), "supported_formats": [{"package": "1.1", "hud": "1.0"}]}
        self.assertEqual(catalog.oldest(source, [wrong, pin()])["app_version"], "0.10.0")

    def test_snapshot_retains_exact_archive_and_detects_later_tampering(self):
        content = b"opaque native-packer protocol fixture"
        digest = hashlib.sha256(content).hexdigest()
        archive = self.root / "native.plxhud"
        archive.write_bytes(content)
        package = catalog.Package(archive, metadata(), content, digest, pin())
        snapshot = self.root / "packages"
        catalog.write_packages(snapshot, [package])
        loaded = catalog.packages(snapshot)[0]
        self.assertEqual(loaded.content, content)
        self.assertEqual(loaded.sha256, digest)
        loaded.path.write_bytes(content + b"changed")
        with self.assertRaisesRegex(catalog.Invalid, "hash|bytes"):
            catalog.packages(snapshot)

    def test_native_pack_report_must_bind_its_actual_output_bytes(self):
        sim = object.__new__(simulator.Simulator)
        sim.pin = pin()
        archive = self.root / "package.plxhud"
        archive.write_bytes(b"native output")
        sim.run = Mock(return_value={"protocol": 1, "package_sha256": "0" * 64,
                                     "bytes": 13, "manifest": metadata(), "findings": []})
        with self.assertRaisesRegex(catalog.Invalid, "hash|bytes"):
            sim.pack(catalog.Source(self.root, metadata()), archive)

    def test_published_recheck_downloads_exact_archive_without_packing_source(self):
        source = self.root / "huds/org.example.hud"
        source.mkdir(parents=True)
        (source / "manifest.json").write_bytes(catalog.canonical(metadata()))
        (source / "README.md").write_text("Source documentation\n")
        (self.root / "revoked.json").write_text("[]")
        content = b"Published native archive protocol fixture"
        digest = hashlib.sha256(content).hexdigest()
        origin = "https://example.invalid/registry"
        entry = {"id": "org.example.hud", "version": "1.0.0", "package_format": "1.0", "hud_format": "1.0",
                 "sha256": digest, "bytes": len(content), "url": origin + "/p/" + digest + ".plxhud",
                 "sdk": pin(), "name": "Example", "author": "Author", "license": "CC0-1.0"}
        index = catalog.canonical({"format": 1, "entries": [entry]})
        info = {"source_sha": "a" * 9}
        proof = catalog.canonical({"package_sha256": digest, "complete": True, "simulator": info, "sdk": pin()})
        opener = Mock()
        opener.open.side_effect = [io.BytesIO(index), io.BytesIO(content), io.BytesIO(proof)]
        with patch("recheck.build_opener", return_value=opener), patch("recheck.Simulator") as native:
            native.return_value.pin, native.return_value.info = pin(), info
            native.return_value.read_package.side_effect = lambda path: catalog.Package(path, metadata(), path.read_bytes(), digest, pin())
            result = recheck.published_packages(self.root, self.root / "cache/simulators", origin,
                                                local=self.root / "sdk")
        self.assertEqual(result[0].content, content)
        self.assertEqual(result[0].path.read_bytes(), content)
        native.return_value.pack.assert_not_called()
        native.return_value.read_package.assert_called_once_with(result[0].path)
        self.assertEqual(opener.open.call_args_list[1].args[0], entry["url"])

    def test_lint_requires_exact_hash_even_when_complete_archive_is_rejected(self):
        archive = self.root / "bad.plxhud"
        archive.write_bytes(b"invalid archive")
        sim = object.__new__(simulator.Simulator)
        sim.pin, sim.calibration = pin(), None
        sim.run = Mock(return_value={"protocol": 1, "package_sha256": None,
                                     "findings": [{"file": None, "path": "", "code": "fixture"}]})
        with self.assertRaisesRegex(catalog.Invalid, "hash"):
            sim.lint(archive)
        sim.pin = {**pin(), "limits": {"package": {"1.0": {"artifact_bytes": 4}}}}
        self.assertIsNone(sim.lint(archive)["package_sha256"], "an oversized prefix has no archive identity")


class PublishedRechecks(unittest.TestCase):
    """The published index is the inventory, with opaque archive protocol fixtures."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "revoked.json").write_text("[]")
        (self.root / "maintainers.json").write_text("{}")
        self.meta = metadata()
        self.original_pin = pin()
        self.content = b"published original SDK archive protocol fixture"
        self.digest = hashlib.sha256(self.content).hexdigest()
        self.origin = "https://example.invalid/registry"
        self.entry = {key: self.meta[key] for key in ("id", "version", "name", "author", "license")}
        self.entry.update(package_format="1.0", hud_format="1.0", sha256=self.digest, bytes=len(self.content),
                          sdk=self.original_pin, url=f"{self.origin}/p/{self.digest}.plxhud", app={"max": "0.9.0"})
        self.info = {key: self.original_pin[key] for key in simulator.CONTRACT_KEYS}
        self.info.update(source_sha=self.original_pin["source_sha"][:9], app_version="0.10.0", languages=["en"])
        self.proof = {"package_sha256": self.digest, "complete": True, "simulator": self.info, "sdk": self.original_pin}
        self.native = Mock()
        self.native.pin = self.original_pin
        self.native.info = self.info
        self.native.languages = ["en"]
        self.native.read_package.side_effect = lambda path: catalog.Package(path, self.meta, path.read_bytes(), self.digest, self.original_pin)
        self.native.lint.return_value = {"findings": [{"file": "hud.json", "path": "/layout", "code": "HUD-E1001"}]}

    def fetch(self, url, **kwargs):
        values = {self.origin + "/index.json": catalog.canonical({"format": 1, "entries": [self.entry], "revoked": []}),
                  self.entry["url"]: self.content,
                  f"{self.origin}/previews/{self.digest}/manifest.json": catalog.canonical(self.proof)}
        return io.BytesIO(values[url])

    def load(self):
        opener = Mock()
        opener.open.side_effect = self.fetch
        with patch("recheck.build_opener", return_value=opener), patch("recheck.Simulator", return_value=self.native):
            return recheck.published_packages(self.root, self.root / "cache/simulators", self.origin,
                                              local=self.root / "sdk")

    def test_source_removal_does_not_remove_a_published_package_from_recheck(self):
        packages = self.load()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].metadata, self.meta)
        self.assertEqual(packages[0].pin, self.original_pin)
        self.assertNotIn("app", packages[0].metadata, "catalog ceilings must not cap future rechecks")

    def test_source_version_ahead_of_pages_does_not_abort_recheck(self):
        source = self.root / "huds" / self.meta["id"]
        source.mkdir(parents=True)
        (source / "manifest.json").write_bytes(catalog.canonical({**self.meta, "version": "1.1.0"}))
        (source / "README.md").write_text("Next source version\n")
        self.assertEqual(self.load()[0].metadata["version"], "1.0.0")

    def test_original_preview_provenance_must_match_the_original_sdk(self):
        self.proof["simulator"] = {**self.info, "source_sha": "d" * 9}
        with self.assertRaisesRegex(catalog.Invalid, "provenance"):
            self.load()

    def test_source_removed_package_still_records_later_failure_and_can_notify(self):
        opener = Mock()
        opener.open.side_effect = self.fetch
        with patch("recheck.build_opener", return_value=opener), \
             patch("recheck.Simulator", return_value=self.native), \
             patch("recheck.toolchains", return_value=[pin("0.11.0")]), patch("recheck.notify") as notify:
            result = recheck.recheck(self.root, self.root / "cache/simulators", {}, local=self.root / "sdk",
                                     base_url=self.origin, notify_repo="owner/registry")
        self.assertTrue(result["packages"][self.digest]["checks"]["0.11.0"]["nontext"])
        self.assertEqual(notify.call_args.args[-1], ())


if __name__ == "__main__":
    unittest.main()
