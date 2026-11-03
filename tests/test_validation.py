"""Synthetic SDK responses test orchestration and document locations, without native claims."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from catalog import Invalid, Package, canonical, packages, sources
from test_bundles import metadata, pin
from validate import build_packages, schema_agreement, stock_package


class Validation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "huds/org.example.hud"
        self.source.mkdir(parents=True)
        (self.source / "manifest.json").write_bytes(canonical(metadata()))
        (self.source / "README.md").write_text("Protocol fixture\n")
        self.hud = b'{"layout":{"value":1,"if":{"paused":2,"chapters.present":3}}}\n'
        (self.source / "hud.json").write_bytes(self.hud)

    def test_pack_once_snapshot_survives_source_edits_and_temporary_cleanup(self):
        sdk = Mock()

        def native_protocol_fixture(source, output):
            # Opaque fixture bytes deliberately do not implement the native archive writer.
            content = b"protocol fixture\0" + (source.path / "hud.json").read_bytes()
            output.write_bytes(content)
            return Package(output, source.metadata, content, hashlib.sha256(content).hexdigest(), pin())

        sdk.pack.side_effect = native_protocol_fixture
        snapshot = self.root / "built"
        with patch("validate.toolchains", return_value=[pin()]), patch("validate.Simulator", return_value=sdk):
            built = build_packages(self.root, self.root / "cache", snapshot, local=self.root / "sdk")
        self.assertEqual(sdk.pack.call_count, 1)
        self.assertIn(self.hud, built[0].content)
        self.assertTrue(built[0].path.is_file())
        (self.source / "hud.json").write_text('{"layout":"edited after validation"}')
        self.assertEqual(packages(snapshot)[0].content, built[0].content)
        self.assertEqual(packages(snapshot)[0].sha256, built[0].sha256)

    def test_first_bundle_baseline_does_not_parse_preceding_source_format(self):
        (self.source / "manifest.json").unlink()
        (self.source / "hud.plxhud.json").write_bytes(b"not even readable JSON")
        with patch("validate.Simulator") as simulator, patch("validate.toolchains") as pins:
            self.assertEqual(build_packages(self.root, self.root / "cache", self.root / "before",
                                            initial_baseline=True), [])
        simulator.assert_not_called()
        pins.assert_not_called()
        with self.assertRaises(FileNotFoundError):
            sources(self.root)

    def corpus(self, wrong_file=False):
        sdk_root = self.root / "sdk"
        corpus = sdk_root / "corpus"
        corpus.mkdir(parents=True)
        schemas = {"manifest": {"type": "object", "properties": {"package_format": {"type": "string"}},
                                "additionalProperties": False},
                   "hud": {"type": "object", "properties": {"layout": {"type": "object"}},
                           "additionalProperties": False}}
        for kind, schema in schemas.items():
            mirror = self.root / "schema" / kind / "1.0.json"
            mirror.parent.mkdir(parents=True)
            mirror.write_bytes(canonical(schema))
        (corpus / "manifest.json.fixture").write_text('{"extra":true}')
        (corpus / "hud.json.fixture").write_text('{"layout":{}}')
        cases = [
            {"input": "bad-source", "invalid": True, "documents": [
                {"kind": "manifest", "version": "1.0", "file": "manifest.json", "path": "manifest.json.fixture"},
                {"kind": "hud", "version": "1.0", "file": "hud.json", "path": "hud.json.fixture"}]},
            {"input": "bad-archive.plxhud", "invalid": True, "documents": []},
        ]
        (corpus / "manifest.json").write_bytes(canonical({"protocol": 1, "cases": cases}))
        sim = SimpleNamespace(root=sdk_root, pin=pin())
        sim.run = lambda _, kind, *args: schemas[kind]
        sim.lint = lambda path: {"findings": [{"file": "hud.json" if wrong_file else "manifest.json", "path": "/extra"}]
                                if path.name == "bad-source" else [{"file": None, "path": ""}]}
        return sim

    def test_schema_agreement_compares_document_and_pointer_and_checks_archives(self):
        validators, count = schema_agreement(self.corpus(), self.root)
        self.assertEqual(count, 2)
        self.assertEqual(set(validators), {("manifest", "1.0"), ("hud", "1.0")})

    def test_matching_pointer_in_wrong_document_is_not_schema_agreement(self):
        with self.assertRaisesRegex(Invalid, "location disagreement"):
            schema_agreement(self.corpus(wrong_file=True), self.root)

    def test_stock_validation_reads_documents_from_archive_snapshot(self):
        from jsonschema import Draft202012Validator
        buffer = io.BytesIO()
        # A test-only ZIP supplies already-admitted document bytes to the stock-schema layer.
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", json.dumps(metadata()))
            archive.writestr("hud.json", '{"layout":{"correct":true}}')
        validators = {("manifest", "1.0"): Draft202012Validator({"type": "object"}),
                      ("hud", "1.0"): Draft202012Validator({"properties": {"layout": {"required": ["correct"]}}})}
        content = buffer.getvalue()
        package = Package(self.root / "fixture.plxhud", metadata(), content, hashlib.sha256(content).hexdigest())
        (self.source / "hud.json").write_text('{"layout":{"wrong":true}}')
        stock_package(package, validators)


if __name__ == "__main__":
    unittest.main()
