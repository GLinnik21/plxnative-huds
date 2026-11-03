import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from catalog import Invalid, canonical
from test_bundles import FORMATS, SCHEMAS, LIMITS
from releases import immutable
from simulator import Simulator, extract, verify_bundle, toolchains


class Pinning(unittest.TestCase):
    def test_binary_must_report_pinned_schema_and_limits_and_both_formats(self):
        from test_bundles import pin
        value = pin()
        info = {**{key: value[key] for key in ("protocol", "supported_formats", "schemas", "limits")},
                "app_version": value["app_version"], "source_sha": value["source_sha"][:9],
                "languages": ["en"], "rungs": {"BODY": 28}}
        manifest = {"reported_version": value["app_version"]}
        with patch("simulator.verify_bundle", return_value=manifest), patch.object(Simulator, "run", return_value=info):
            sdk = Simulator(Path("fixture-sdk"), value)
            self.assertEqual(sdk.env["PYTHONDONTWRITEBYTECODE"], "1")
        for field, replacement in (("supported_formats", [{"package": "1.1", "hud": "1.0"}]),
                                   ("schemas", {"manifest": {"1.0": "https://example.invalid/schema"}, "hud": SCHEMAS["hud"]}),
                                   ("limits", {**LIMITS, "package": {"1.0": {"artifact_bytes": 17}}})):
            with self.subTest(field=field), patch("simulator.verify_bundle", return_value=manifest), \
                 patch.object(Simulator, "run", return_value={**info, field: replacement}):
                with self.assertRaises(Invalid):
                    Simulator(Path("fixture-sdk"), value)

    def test_native_seven_character_source_prefix_is_bound_to_full_pin(self):
        from test_bundles import pin
        value = pin()
        info = {**{key: value[key] for key in ("protocol", "supported_formats", "schemas", "limits")},
                "app_version": value["app_version"], "source_sha": value["source_sha"][:7],
                "languages": ["en"], "rungs": {"BODY": 28}}
        manifest = {"reported_version": value["app_version"]}
        with patch("simulator.verify_bundle", return_value=manifest), patch.object(Simulator, "run", return_value=info):
            sdk = Simulator(Path("fixture-sdk"), value)
            self.assertEqual(sdk.info["source_sha"], "a" * 7)
        for source in ("a" * 6, "b" * 7):
            with self.subTest(source=source), patch("simulator.verify_bundle", return_value=manifest), \
                 patch.object(Simulator, "run", return_value={**info, "source_sha": source}):
                with self.assertRaises(Invalid):
                    Simulator(Path("fixture-sdk"), value)

    def test_manifest_and_binary_must_both_match_the_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin/plxnative-sim"
            binary.parent.mkdir(); binary.write_bytes(b"binary")
            manifest = {"protocol":1,"reported_version":"0.10.0","development":False,"app_version":"0.10.0", "source_sha":"a"*40, "supported_formats":FORMATS,"schemas":SCHEMAS,"limits":LIMITS,
                        "files":{"bin/plxnative-sim":hashlib.sha256(b"binary").hexdigest()}}
            content = canonical(manifest)
            (root / "bundle.json").write_bytes(content)
            pin = {key:manifest[key] for key in ("protocol","app_version","source_sha","supported_formats","schemas","limits")}
            pin["manifest_sha256"] = hashlib.sha256(content).hexdigest()
            verify_bundle(root,pin)
            (root / "unbound-corpus.json").write_text("{}")
            with self.assertRaisesRegex(Invalid, "outside"):
                verify_bundle(root,pin)
            (root / "unbound-corpus.json").unlink()
            binary.write_bytes(b"tampered")
            with self.assertRaisesRegex(Invalid,"file hash"):
                verify_bundle(root,pin)
            manifest["files"]["bin/plxnative-sim"] = hashlib.sha256(b"tampered").hexdigest()
            (root / "bundle.json").write_bytes(canonical(manifest))
            with self.assertRaisesRegex(Invalid,"manifest"):
                verify_bundle(root,pin)

    def test_release_pins_are_immutable_but_bootstrap_development_pin_can_be_replaced(self):
        old = {"app_version":"0.10.0","sha256":"first"}
        with self.assertRaises(Invalid):
            immutable([old],[{**old,"sha256":"different"}])
        with self.assertRaises(Invalid):
            immutable([old],[])
        immutable([{**old,"development":True}],[{**old,"sha256":"released"}])

    def test_archive_links_traversal_and_duplicate_members_are_rejected(self):
        for name,kind in (("../outside",None),("/outside",None),("link",tarfile.SYMTYPE),("hard",tarfile.LNKTYPE),("duplicate",None)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); path=root / "a.tar.gz"
                with tarfile.open(path,"w:gz") as archive:
                    member=tarfile.TarInfo(name)
                    if kind:
                        member.type=kind; member.linkname="../outside"
                    archive.addfile(member,io.BytesIO())
                    if name=="duplicate":
                        archive.addfile(member,io.BytesIO())
                with self.assertRaises(Invalid):
                    extract(path,root / "out")

    def test_calibration_and_download_origin_cannot_escape_the_registry_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            pin={"protocol":1,"app_version":"0.10.0","source_sha":"a"*40,"sha256":"b"*64,"manifest_sha256":"c"*64,
                 "supported_formats":FORMATS,"schemas":SCHEMAS,"limits":LIMITS,"bytes":1,"url":"https://github.com/GLinnik21/plx-native/releases/download/test/sim.tar.gz",
                 "calibration":"calibration/measured.json"}
            def check(value):
                (root / "toolchains.json").write_bytes(canonical({"format":1,"simulators":[value]}))
                return toolchains(root)
            self.assertEqual(check(pin),[pin])
            for edit in ({"calibration":"../private"},{"url":"http://127.0.0.1/private"},{"sha256":"unpinned"},
                         {"url":"https://github.com/GLinnik21/plx-native/releases/download/../../../../other/repo/releases/download/v1/sim.tar.gz"},
                         {"url":"https://github.com/GLinnik21/plx-native/releases/download/%2e%2e/sim.tar.gz"},
                         {"url":pin["url"]+"?redirect=elsewhere"}):
                with self.assertRaises(Invalid):
                    check({**pin,**edit})
