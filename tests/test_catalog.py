import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog
from check_site import check
from test_bundles import metadata, pin


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ident = "org.example.hud"
        self.directory = self.root / "huds" / self.ident
        self.directory.mkdir(parents=True)
        self.metadata = metadata(self.ident)
        self.write()
        (self.directory / "README.md").write_text("Example\n")
        (self.root / "revoked.json").write_text("[]\n")

    def write(self):
        (self.directory / "manifest.json").write_bytes(catalog.canonical(self.metadata))

    def package(self):
        source = catalog.sources(self.root)[0]
        content = b"Opaque archive protocol fixture\n" + (source.path / "manifest.json").read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / (digest + ".plxhud")
        path.write_bytes(content)
        return catalog.Package(path, source.metadata, content, digest, pin())

    def preview(self, package):
        out = self.root / "renders" / package.sha256
        out.mkdir(parents=True)
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8k8AAAAASUVORK5CYII=")
        (out / "playing.png").write_bytes(png)
        manifest = {"package_sha256": package.sha256, "scenes": [{"state": "playing", "lang": "en", "file": "playing.png", "sha256": hashlib.sha256(png).hexdigest()}]}
        (out / "manifest.json").write_bytes(catalog.canonical(manifest))
        return self.root / "renders"

    def test_directory_identity_and_symlinks_are_refused(self):
        self.metadata["id"] = "org.example.different"
        self.write()
        with self.assertRaisesRegex(catalog.Invalid, "differs"):
            self.package()
        path = self.directory / "manifest.json"
        path.unlink()
        target = self.root / "elsewhere.json"
        target.write_bytes(catalog.canonical(self.metadata))
        path.symlink_to(target)
        with self.assertRaisesRegex(catalog.Invalid, "symlink"):
            self.package()

    def test_duplicate_keys_and_nonrelease_versions_are_refused(self):
        (self.directory / "manifest.json").write_text('{"id":"one","id":"two"}')
        with self.assertRaisesRegex(catalog.Invalid, "duplicate"):
            self.package()
        for version in ("1.0", "01.0.0", "1.0.0-rc.1", None, True):
            with self.subTest(version=version), self.assertRaises(catalog.Invalid):
                catalog.release(version)

    def test_oldest_compatible_pin_is_used_instead_of_latest(self):
        self.metadata["app"] = {"min": "0.10.0", "max": "0.12.0"}
        self.write()
        pins = [{"app_version": version, "supported_formats": [{"package": "1.0", "hud": value} for value in formats], "source_sha": "a"*40} for version, formats in
                [("0.12.0", ["1.0"]), ("0.9.0", ["1.0"]), ("0.10.0", ["1.1"]), ("0.11.0", ["1.0"])]]
        self.assertEqual(catalog.oldest(self.package(), pins)["app_version"], "0.11.0")
        with self.assertRaisesRegex(catalog.Invalid, "no pinned"):
            catalog.oldest(self.package(), [])

    def test_changed_bytes_require_version_increment(self):
        before = self.package()
        self.metadata["name"] = "Changed"
        self.write()
        with self.assertRaisesRegex(catalog.Invalid, "newer"):
            catalog.check_update(self.package(), before)
        self.metadata["version"] = "1.0.1"
        self.write()
        catalog.check_update(self.package(), before)

    def test_publisher_preserves_exact_bytes_and_is_deterministic(self):
        package = self.package()
        previews = self.preview(package)
        a, b = self.root / "a", self.root / "b"
        first = catalog.generate(self.root, a, previews, "https://example.invalid/huds", {}, [package])
        second = catalog.generate(self.root, b, previews, "https://example.invalid/huds", {}, [package])
        self.assertEqual(first, second)
        self.assertEqual((a / "index.json").read_bytes(), (b / "index.json").read_bytes())
        self.assertEqual((a / "p" / (package.sha256+".plxhud")).read_bytes(), package.content)
        self.assertEqual(first["entries"][0]["sha256"], hashlib.sha256(package.content).hexdigest())
        self.assertEqual(first["entries"][0]["bytes"], len(package.content))
        self.assertEqual(first["entries"][0]["sdk"], package.pin)
        proof = catalog.read_json(a / "previews" / package.sha256 / "manifest.json")
        self.assertEqual(proof["sdk"], package.pin)
        (a / "CREDITS.md").write_text("Protocol fixture\n")
        self.assertEqual(check(a), 1)
        proof["sdk"] = {**package.pin, "sha256": "0" * 64}
        (a / "previews" / package.sha256 / "manifest.json").write_bytes(catalog.canonical(proof))
        with self.assertRaises(AssertionError):
            check(a)

    def test_bad_preview_hash_or_path_never_publishes_an_index(self):
        package = self.package()
        previews = self.preview(package)
        manifest_path = previews / package.sha256 / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for value in ("../../outside.png", "playing.png"):
            manifest["scenes"][0].update(file=value, sha256="0"*64)
            manifest_path.write_bytes(catalog.canonical(manifest))
            output = self.root / "published"
            with self.assertRaises(catalog.Invalid):
                catalog.generate(self.root, output, previews, "https://example.invalid/huds", {}, [package])
            self.assertFalse((output / "index.json").exists())

    def test_revoked_hash_is_removed_but_reason_remains_available(self):
        package = self.package()
        revocation = {"sha256": package.sha256, "reason": "Author withdrew this version"}
        (self.root / "revoked.json").write_bytes(catalog.canonical([revocation]))
        index = catalog.generate(self.root, self.root / "out", self.root / "no-previews", "https://example.invalid", {}, [package])
        self.assertEqual(index["entries"], [])
        self.assertEqual(index["revoked"], [revocation])

    def test_release_compatibility_does_not_rewrite_package_or_widen_authored_max(self):
        self.metadata["app"] = {"max": "0.11.0"}
        self.write()
        package = self.package()
        compatibility = {"packages": {package.sha256: {"app_max": "0.12.0", "unfit": [{"from": "0.12.0", "langs": ["de"]}]}}}
        index = catalog.generate(self.root, self.root / "out", self.preview(package), "https://example.invalid", compatibility, [package])
        self.assertEqual(index["entries"][0]["app"]["max"], "0.11.0")
        self.assertEqual(index["entries"][0]["unfit"], [{"from": "0.12.0", "langs": ["de"]}])
        self.assertEqual(package.path.read_bytes(), package.content)


if __name__ == "__main__":
    unittest.main()
