import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from catalog import Invalid, canonical
from releases import immutable
from simulator import extract, verify_bundle, toolchains


class Pinning(unittest.TestCase):
    def test_manifest_and_binary_must_both_match_the_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin/plxnative-sim"
            binary.parent.mkdir(); binary.write_bytes(b"binary")
            manifest = {"protocol":1,"reported_version":"0.10.0","development":False,"app_version":"0.10.0", "source_sha":"a"*40, "formats":["1.0"],
                        "files":{"bin/plxnative-sim":hashlib.sha256(b"binary").hexdigest()}}
            content = canonical(manifest)
            (root / "bundle.json").write_bytes(content)
            pin = {key:manifest[key] for key in ("app_version","source_sha","formats")}
            pin["manifest_sha256"] = hashlib.sha256(content).hexdigest()
            verify_bundle(root,pin)
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
            pin={"app_version":"0.10.0","source_sha":"a"*40,"sha256":"b"*64,"manifest_sha256":"c"*64,
                 "formats":["1.0"],"bytes":1,"url":"https://github.com/GLinnik21/plx-native/releases/download/test/sim.tar.gz",
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
