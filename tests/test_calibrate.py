import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from calibrate import calibrate
from catalog import Invalid


def report():
    return {"protocol": 1, "source_sha": "abc", "font_hashes": {"face": "sha"}, "metrics": [
        {"lang": lang, "rung": rung, "bold": bold, "role": "label", "text": "text", "size": size, "width": 100}
        for lang in ("en", "be") for rung, size in (("BODY", 28), ("CAPTION", 24)) for bold in (False, True)]}


class Calibration(unittest.TestCase):
    def test_each_rung_uses_its_own_worst_positive_delta_rounded_up(self):
        host, tv = report(), report()
        tv["metrics"][0]["width"] = 102.2
        tv["metrics"][3]["width"] = 101.1
        tv["metrics"][4]["width"] = 99
        value = calibrate(host, tv)
        self.assertEqual(value["by_rung"], {"BODY": 3, "CAPTION": 2})
        self.assertEqual(value["corpus_rows"], 8)

    def test_different_fonts_incomplete_corpus_and_nonfinite_measurement_are_refused(self):
        for edit in (lambda r: r["font_hashes"].update(face="other"), lambda r: r["metrics"].pop(),
                     lambda r: r["metrics"][0].update(width=float("nan")), lambda r: r["metrics"][0].update(text="other")):
            tv = report(); edit(tv)
            with self.assertRaises(Invalid):
                calibrate(report(), tv)

    def test_clock_envelopes_can_choose_different_widest_digits(self):
        host, tv = report(), report()
        for row in host["metrics"] + tv["metrics"]:
            row["role"] = "clock.max.true"
        tv["metrics"][0]["text"] = "88:88:88"
        self.assertEqual(calibrate(host, tv)["by_rung"]["BODY"], 0)
