"""Re-lint unchanged registry entries on app releases and the weekly backstop."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import build_opener
from catalog import Invalid, canonical, format_pair, packages, public_origin, read_json, release, revoked, supports, unique_object
from previews import verify_provenance
from simulator import SecureRedirect, Simulator, acquire, toolchains, validate_pin

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


def original_sdk(pin, cache, local=None):
    """Authenticate the package's recorded SDK independently of today's active pins."""
    if not isinstance(pin, dict):
        raise Invalid("package omits its original SDK provenance")
    validate_pin(pin)
    return Simulator(local or acquire(pin, cache), pin)


def published_packages(root, cache, base_url, local=None):
    """Read the published artifacts verbatim. A release recheck never rebuilds a HUD."""
    public_origin(base_url)
    origin = base_url.rstrip("/")
    opener = build_opener(SecureRedirect)

    def fetch(url, maximum):
        with opener.open(url, timeout=60) as response:
            content = response.read(maximum + 1)
        if len(content) > maximum:
            raise Invalid("published catalog/package exceeds its byte bound")
        return content

    index = json.loads(fetch(origin + "/index.json", 2 * 1024 * 1024), object_pairs_hook=unique_object)
    if index.get("format") != 1 or not isinstance(index.get("entries"), list):
        raise Invalid("published registry needs a format 1 catalog")
    entries = {entry["id"]: entry for entry in index["entries"]}
    if len(entries) != len(index["entries"]):
        raise Invalid("published catalog has duplicate package IDs")
    tombstones = {item["sha256"] for item in revoked(root)}
    tombstones.update(item["sha256"] for item in index.get("revoked", []))
    by_id = {}
    for entry in entries.values():
        digest = entry.get("sha256", "")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise Invalid("published catalog has an invalid package hash")
        if digest in tombstones:
            continue
        sim = original_sdk(entry.get("sdk"), cache, local)
        declared = {"package": entry.get("package_format"), "hud": entry.get("hud_format")}
        if declared not in sim.pin["supported_formats"]:
            raise Invalid("published package format differs from its original SDK provenance")
        maximum = sim.pin["limits"]["package"][declared["package"]]["artifact_bytes"]
        size = entry.get("bytes")
        if type(size) is not int or not 0 < size <= maximum:
            raise Invalid("published package size is outside its declared profile")
        url = origin + "/p/" + digest + ".plxhud"
        if entry.get("url") != url:
            raise Invalid("published package URL differs from its content-addressed path")
        path = cache.parent / "published-packages" / (digest + ".plxhud")
        path.parent.mkdir(parents=True, exist_ok=True)
        content = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            content = fetch(url, size)
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            raise Invalid("published package bytes/hash mismatch")
        if path.is_symlink():
            raise Invalid("published package cache cannot contain a symlink")
        path.write_bytes(content)
        package = sim.read_package(path)
        if (package.sha256 != digest or package.content != content
            or format_pair(package.metadata) != declared or not supports(package, sim.pin)
            or any(package.metadata.get(key) != entry.get(key) for key in ("id", "version", "name", "author", "license"))):
            raise Invalid("published catalog metadata differs from its authenticated archive")
        proof = json.loads(fetch(origin + "/previews/" + digest + "/manifest.json", 2 * 1024 * 1024),
                           object_pairs_hook=unique_object)
        verify_provenance(sim, package, proof, published=True)
        by_id[package.id] = package
    return list(by_id.values())


def recheck(root, cache, previous, local=None, notify_repo=None, snapshot=None,
            base_url="https://glinnik21.github.io/plxnative-huds"):
    result = copy.deepcopy(previous)
    tombstones = {item["sha256"] for item in revoked(root)}
    owners = read_json(root / "maintainers.json")
    pins = sorted(toolchains(root), key=lambda pin: release(pin["app_version"]))
    candidates = packages(snapshot) if snapshot else published_packages(root, cache, base_url, local)
    if snapshot:
        for package in candidates:
            if package.sha256 in tombstones:
                continue
            sim = original_sdk(package.pin, cache, local)
            sim.inspect(package)
            if not supports(package, sim.pin):
                raise Invalid("package is outside its original SDK's supported format or app range")
    for pin in pins:
        directory = local if local else acquire(pin, cache)
        sim = Simulator(directory, pin, root / pin["calibration"])
        for package in candidates:
            if package.sha256 in tombstones or not supports(package, pin):
                continue
            report = sim.lint(package.path)
            fit = verdict(report, sim.languages)
            result = update(result, package.sha256, pin["app_version"], fit, sim.languages)
            if fit["langs"] and notify_repo:
                notify(notify_repo, package, pin["app_version"], fit, owners.get(package.id, ()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--local-simulator", type=Path)
    parser.add_argument("--notify-repo")
    parser.add_argument("--packages", type=Path, help="Use a previously built archive snapshot for an offline check")
    parser.add_argument("--base-url", default="https://glinnik21.github.io/plxnative-huds")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    path = args.out or args.root / "compatibility.json"
    result = recheck(args.root, args.cache, read_json(args.root / "compatibility.json"), args.local_simulator, args.notify_repo,
                     args.packages, args.base_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(result))


if __name__ == "__main__":
    main()
