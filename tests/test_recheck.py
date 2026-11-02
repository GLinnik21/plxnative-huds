from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from recheck import verdict, update, notify, issue, recheck
from catalog import Invalid, Package


class ReleaseCheck(unittest.TestCase):
    def test_translation_regression_is_language_specific_and_recovery_is_recorded(self):
        report = {"findings": [{"code": "HUD-E0601", "context": {"lang": "de"}}]}
        languages = ["en", "de"]
        fit = verdict(report, languages)
        self.assertEqual(fit["langs"], ["de"])
        value = update({}, "hash", "0.10.0", verdict({"findings": []}, languages), languages)
        value = update(value, "hash", "0.11.0", fit, languages)
        self.assertNotIn("app_max", value["packages"]["hash"])
        value = update(value, "hash", "0.12.0", verdict({"findings": []}, languages), languages)
        self.assertEqual(value["packages"]["hash"]["unfit"], [{"from": "0.11.0", "langs": ["de"]}, {"from": "0.12.0", "langs": []}])

    def test_nontext_regression_or_every_language_caps_at_last_passed_app(self):
        languages = ["en", "de"]
        good = verdict({"findings": []}, languages)
        for findings in ([{"code": "HUD-E0601"}], [{"code": "HUD-E1001", "context": {"lang": "de"}}]):
            bad = verdict({"findings": findings}, languages)
            value = update({}, "hash", "0.10.0", good, languages)
            value = update(value, "hash", "0.11.0", bad, languages)
            self.assertEqual(value["packages"]["hash"]["app_max"], "0.10.0")
            self.assertEqual(value["packages"]["hash"]["unfit"][0]["langs"], ["de", "en"])

    def test_recovery_removes_the_old_ceiling_and_preserves_the_failure_interval(self):
        languages=["en","de"]
        good=verdict({"findings":[]},languages)
        bad=verdict({"findings":[{"code":"HUD-E1001"}]},languages)
        value=update({},"hash","0.10.0",good,languages)
        value=update(value,"hash","0.11.0",bad,languages)
        value=update(value,"hash","0.12.0",good,languages)
        self.assertNotIn("app_max",value["packages"]["hash"])
        self.assertEqual(value["packages"]["hash"]["unfit"],
                         [{"from":"0.11.0","langs":["de","en"]},{"from":"0.12.0","langs":[]}])

    def test_future_format_is_not_checked_against_older_unsupported_compilers(self):
        package=Package(Path("hud.json"),{"id":"com.example.future","format":"1.1"},b"", "hash")
        pins=[{"app_version":"0.10.0","formats":["1.0"],"calibration":"old.json"},
              {"app_version":"0.11.0","formats":["1.0","1.1"],"calibration":"new.json"}]
        with patch("recheck.toolchains",return_value=pins), patch("recheck.revoked",return_value=[]), \
             patch("recheck.read_json",return_value={package.id:["author"]}), \
             patch("recheck.packages",return_value=[package]), patch("recheck.Simulator") as simulator:
            simulator.return_value.languages=["en"]
            simulator.return_value.lint.return_value={"findings":[]}
            result=recheck(Path("registry"),Path("cache"),{},local=Path("bundle"))
        self.assertEqual(simulator.return_value.lint.call_count,1)
        self.assertEqual(list(result["packages"]["hash"]["checks"]),["0.11.0"])

    def test_unknown_language_is_not_silently_dropped(self):
        with self.assertRaises(Invalid):
            verdict({"findings": [{"code": "HUD-E0601", "context": {"lang": "xx"}}]}, ["en"])

    def test_large_regression_keeps_a_bounded_valid_json_issue_excerpt(self):
        package = Package(Path("x"), {"name":"Demo","version":"1.0.0","author":"Author"}, b"", "hash")
        report = {"findings":[{"code":"HUD-E0601","message":"long diagnostic"*100} for _ in range(200)]}
        _,_,body = issue(package,"0.11.0",{"langs":["de"],"report":report},["author"])
        self.assertLess(len(body.encode()),60000)
        self.assertIn('"truncated": true',body)
        self.assertIn("@author",body)

    def test_closed_author_issue_is_not_duplicated_by_the_weekly_backstop(self):
        package = Package(Path("x"), {"name": "Demo", "version": "1.0.0", "author": "Author"}, b"", "hash")
        result = {"langs": ["de"], "report": {"findings": []}}
        with patch("recheck.subprocess.run") as run:
            run.return_value.stdout = '[{"body":"<!-- plxnative-hud-fit:hash:0.11.0 -->"}]'
            notify("owner/registry", package, "0.11.0", result)
            self.assertEqual(run.call_count, 1)
            self.assertIn("all", run.call_args.args[0])
