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
                 "sha256": digest, "bytes": len(content), "url": origin + "/p/" + digest + ".plxhud"}
        index = catalog.canonical({"format": 1, "entries": [entry]})
        opener = Mock()
        opener.open.side_effect = [io.BytesIO(index), io.BytesIO(content)]
        with patch("recheck.build_opener", return_value=opener), patch("recheck.Simulator") as native:
            result = recheck.published_packages(self.root, self.root / "cache/simulators", [pin()], origin,
                                                local=self.root / "sdk")
        self.assertEqual(result[0].content, content)
        self.assertEqual(result[0].path.read_bytes(), content)
        native.return_value.pack.assert_not_called()
        native.return_value.inspect.assert_called_once_with(result[0])
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


if __name__ == "__main__":
    unittest.main()
