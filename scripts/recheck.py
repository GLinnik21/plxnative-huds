"""Re-lint unchanged registry entries on app releases and the weekly backstop."""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from catalog import Invalid, canonical, inside, packages, read_json, release, revoked
from simulator import Simulator, acquire, toolchains

TEXT_CODES = {"HUD-E0601", "HUD-W0602"}


def verdict(report, languages):
    failures = {lang: [] for lang in languages}
    nontext = False
    for finding in report["findings"]:
        nontext |= finding["code"] not in TEXT_CODES
        lang = finding.get("context", {}).get("lang")
        if lang is not None and lang not in failures:
            raise Invalid(f"lint returned an unknown language: {lang}")
        for tag in languages if lang is None else [lang]:
            failures[tag].append(finding)
    failed = sorted(lang for lang, items in failures.items() if items)
    if nontext:
        failed = sorted(languages)
    return {"langs": failed, "nontext": nontext, "all_failed": set(failed) == set(languages), "report": report}


def update(previous, digest, version, result, languages):
    """Derive the compatibility projection from immutable per-release verdicts."""
    release(version)
    value = copy.deepcopy(previous)
    value.setdefault("format", 1)
    entry = value.setdefault("packages", {}).setdefault(digest, {})
    entry.setdefault("checks", {})[version] = result
    checks = sorted(entry["checks"].items(), key=lambda item: release(item[0]))
    # Keep successful transitions too: a later app can repair a translation regression.
    unfit = []
    last = []
    for at, check in checks:
        if check["langs"] != last:
            unfit.append({"from": at, "langs": check["langs"]})
            last = check["langs"]
    entry["unfit"] = unfit
    entry.pop("app_max", None)
    def fatal(check):
        return check["nontext"] or check.get("all_failed",set(check["langs"]) == set(languages))
    if checks and fatal(checks[-1][1]):
        passed = [at for at, check in checks[:-1] if not fatal(check)]
        if passed:
            entry["app_max"] = passed[-1]
    return value


def issue(package, version, result, contacts=()):
    marker = f'<!-- plxnative-hud-fit:{package.sha256}:{version} -->'
    author = package.metadata["author"]
    mention = f'@{author["github"]}' if isinstance(author, dict) and author.get("github") else str(author)
    if contacts:
        mention = ", ".join("@" + name for name in contacts)
    report = {"findings": result["report"]["findings"]}
    full_count = len(report["findings"])
    # Cost lines are not failure evidence. Bound issue text by encoded bytes; the complete lint
    # stays in compatibility.json and the workflow artifact even for a large regression.
    while len(json.dumps(report,ensure_ascii=False,indent=2).encode()) > 48000 and report["findings"]:
        report["findings"] = report["findings"][:len(report["findings"])//2]
        report.update(total_findings=full_count, truncated=True)
    body = (f'{marker}\n{mention}, **{package.metadata["name"]} {package.metadata["version"]}** fails '
            f'fit checks on PlxNative **{version}** in: {", ".join(result["langs"])}.\n\n'
            'The package bytes have not changed. Please submit a newer HUD version after addressing the findings.\n\n'
            '```json\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n')
    if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY"):
        url = "https://github.com/" + os.environ["GITHUB_REPOSITORY"] + "/actions/runs/" + os.environ["GITHUB_RUN_ID"]
        body += f'\n[Complete per-language lint evidence]({url}) is retained in the workflow artifact and compatibility projection.\n'
    body += "\nCompatibility key: `" + marker.removeprefix("<!-- ").removesuffix(" -->") + "`\n"
    return marker, f'{package.metadata["name"]}: compatibility with PlxNative {version}', body


def notify(repo, package, version, result, contacts=()):
    marker, title, body = issue(package, version, result, contacts)
    # Search both open and closed issues. Closing the author's issue must not cause a weekly duplicate.
    query = '"' + marker.removeprefix("<!-- ").removesuffix(" -->") + '" in:body'
    process = subprocess.run(["gh", "issue", "list", "--repo", repo, "--state", "all", "--search", query,
                              "--json", "body", "--limit", "100"], capture_output=True, text=True, check=True)
    if any(marker in item["body"] for item in json.loads(process.stdout)):
        return
    # Literal newlines and JSON stay in stdin; no shell interpolation or command substitutions.
    subprocess.run(["gh", "issue", "create", "--repo", repo, "--title", title, "--body-file", "-"], input=body, text=True, check=True)


def recheck(root, cache, previous, local=None, notify_repo=None):
    result = copy.deepcopy(previous)
    tombstones = {item["sha256"] for item in revoked(root)}
    owners = read_json(root / "maintainers.json")
    pins = sorted(toolchains(root), key=lambda pin: release(pin["app_version"]))
    for pin in pins:
        directory = local if local else acquire(pin, cache)
        sim = Simulator(directory, pin, root / pin["calibration"])
        for package in packages(root):
            if (package.sha256 in tombstones or package.metadata["format"] not in pin["formats"]
                or not inside(pin["app_version"], package.metadata.get("app", {}))):
                continue
            report = sim.lint(package.path)
            fit = verdict(report, sim.languages)
            result = update(result, package.sha256, pin["app_version"], fit, sim.languages)
            if fit["langs"] and notify_repo:
                notify(notify_repo, package, pin["app_version"], fit, owners[package.id])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--local-simulator", type=Path)
    parser.add_argument("--notify-repo")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    path = args.out or args.root / "compatibility.json"
    result = recheck(args.root, args.cache, read_json(args.root / "compatibility.json"), args.local_simulator, args.notify_repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(result))


if __name__ == "__main__":
    main()
