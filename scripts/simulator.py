"""Download a pinned app-built simulator and invoke its own compiler. No registry validator fork."""
from __future__ import annotations

import fcntl
import hashlib
import math
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit

from catalog import Invalid, Package, Source, read_json, release, supports

CONTRACT_KEYS = ("protocol", "supported_formats", "schemas", "limits")


def validate_contract(value):
    pairs = value.get("supported_formats")
    if type(value.get("protocol")) is not int or value["protocol"] != 1 or not isinstance(pairs, list) or not pairs:
        raise Invalid("simulator needs protocol 1 and supported_formats tuples")
    schemas, profiles = value.get("schemas"), value.get("limits")
    if (not isinstance(schemas, dict) or not isinstance(profiles, dict)
        or any(not isinstance(schemas.get(kind), dict) for kind in ("manifest", "hud"))
        or any(not isinstance(profiles.get(axis), dict) for axis in ("package", "hud"))):
        raise Invalid("simulator needs profile-keyed schemas and limits")
    seen = set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"package", "hud"}:
            raise Invalid("supported_formats entries need package and hud")
        versions = (pair["package"], pair["hud"])
        if any(not isinstance(v, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)", v) for v in versions) or versions in seen:
            raise Invalid("unsupported or duplicate supported_formats tuple")
        seen.add(versions)
        for axis, kind in (("package", "manifest"), ("hud", "hud")):
            version = pair[axis]
            schema = schemas[kind].get(version)
            if schema != f"https://plxnative.com/hud/schema/{kind}/{version}.json":
                raise Invalid("simulator needs an exact schema identity for each profile")
            limits = profiles[axis].get(version)
            if not isinstance(limits, dict) or not limits or any(type(n) is not int or n <= 0 for n in limits.values()):
                raise Invalid("simulator needs positive integer limits for each profile")
        if "artifact_bytes" not in profiles["package"][pair["package"]]:
            raise Invalid("package profile omits artifact_bytes")


class SecureRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        # GitHub release assets legitimately redirect onto its content CDN; no credential is
        # ever sent by this downloader, and the expected bytes are pinned independently.
        from urllib.parse import urlsplit
        if urlsplit(newurl).scheme != "https":
            raise Invalid("simulator download attempted an insecure redirect")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def validate_pin(pin: dict):
    release(pin["app_version"])
    for name, length in (("source_sha", 40), ("sha256", 64), ("manifest_sha256", 64)):
        if not isinstance(pin.get(name), str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", pin[name]):
            raise Invalid(f"simulator pin needs exact {name}")
    validate_contract(pin)
    if type(pin.get("bytes")) is not int or pin["bytes"] <= 0:
        raise Invalid("simulator pin needs archive byte count")
    if not isinstance(pin.get("development",False),bool):
        raise Invalid("development provenance must be a boolean")
    calibration = Path(pin.get("calibration", ""))
    if not calibration.parts or calibration.is_absolute() or ".." in calibration.parts:
        raise Invalid("calibration must be a registry-relative path")
    url = urlsplit(pin.get("url", ""))
    parts = url.path.split("/")
    if (url.scheme != "https" or url.netloc != "github.com" or url.query or url.fragment
        or len(parts) != 7 or parts[:5] != ["","GLinnik21","plx-native","releases","download"]
        or not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*",part) for part in parts[5:])
        or not parts[-1].endswith(".tar.gz")):
        # A textual prefix alone accepts /../ and encoded traversal into another repository.
        # Only the app repository's actual release-asset path may supply executable bytes.
        raise Invalid("simulator must come from a canonical app GitHub release-asset URL")


def toolchains(root: Path) -> list[dict]:
    config = read_json(root / "toolchains.json")
    if config.get("format") != 1 or not isinstance(config.get("simulators"), list):
        raise Invalid("toolchains.json must use format 1 and contain simulators")
    seen = set()
    for pin in config["simulators"]:
        validate_pin(pin)
        if pin["app_version"] in seen:
            raise Invalid("each app version needs exactly one immutable simulator pin")
        seen.add(pin["app_version"])
    if not seen:
        raise Invalid("at least one pinned app simulator is required")
    return config["simulators"]


def extract(archive: Path, destination: Path):
    with tarfile.open(archive, "r:*") as bundle:
        names = set()
        for member in bundle.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or member.name in names:
                raise Invalid("unsafe or duplicate simulator archive member")
            if not member.isfile() and not member.isdir():
                raise Invalid("simulator archive must contain only regular files and directories")
            names.add(member.name)
        # Members have been checked without relying on Python-version-specific tar filters.
        bundle.extractall(destination, filter="data")


def verify_bundle(root: Path, pin: dict):
    if hashlib.sha256((root / "bundle.json").read_bytes()).hexdigest() != pin["manifest_sha256"]:
        raise Invalid("simulator manifest does not match the immutable pin")
    manifest = read_json(root / "bundle.json")
    expected_version = pin["app_version"] + ("-dev" if pin.get("development",False) else "")
    if (manifest.get("protocol") != 1 or manifest.get("reported_version") != expected_version
        or manifest.get("development") != pin.get("development",False)):
        raise Invalid("simulator release/development provenance mismatch")
    validate_contract(manifest)
    for key in ("app_version", "source_sha", *CONTRACT_KEYS):
        if manifest.get(key) != pin[key]:
            raise Invalid(f"simulator provenance mismatch: {key}")
    for name, expected in manifest.get("files", {}).items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise Invalid("unsafe bundle manifest path")
        path = root / name
        relative = Path(name)
        if any((root / Path(*relative.parts[:length])).is_symlink() for length in range(1, len(relative.parts) + 1)):
            raise Invalid(f"simulator file path contains a symlink: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise Invalid(f"simulator file hash mismatch: {name}")
    if "bin/plxnative-sim" not in manifest.get("files", {}):
        raise Invalid("simulator manifest does not bind its binary")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(manifest["files"]) | {"bundle.json"}:
        raise Invalid("simulator contains files outside its pinned manifest")
    return manifest


def acquire(pin: dict, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / (pin["sha256"] + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return acquire_locked(pin, cache)


def acquire_locked(pin: dict, cache: Path) -> Path:
    archive = cache / (pin["sha256"] + ".tar.gz")
    if not archive.exists():
        opener = urllib.request.build_opener(SecureRedirect)
        temp = archive.with_suffix(".download")
        try:
            with opener.open(pin["url"], timeout=60) as response, temp.open("wb") as output:
                shutil.copyfileobj(response, output)
            if temp.stat().st_size != pin["bytes"] or hashlib.sha256(temp.read_bytes()).hexdigest() != pin["sha256"]:
                raise Invalid("downloaded simulator archive does not match its pin")
            temp.replace(archive)
        finally:
            temp.unlink(missing_ok=True)
    if archive.stat().st_size != pin["bytes"] or hashlib.sha256(archive.read_bytes()).hexdigest() != pin["sha256"]:
        raise Invalid("cached simulator archive does not match its pin")
    destination = cache / pin["sha256"]
    if destination.exists():
        try:
            verify_bundle(destination, pin)
            return destination
        except (Invalid, OSError):
            shutil.rmtree(destination)
    temp = Path(tempfile.mkdtemp(prefix="extract-", dir=cache))
    try:
        extract(archive, temp)
        verify_bundle(temp, pin)
        temp.rename(destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return destination


class Simulator:
    def __init__(self, root: Path, pin: dict, calibration: Path | None = None):
        self.root = root.resolve()
        self.pin = pin
        self.manifest = verify_bundle(self.root, pin)
        self.binary = self.root / "bin/plxnative-sim"
        self.calibration = calibration
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("PLXNATIVE_")}
        self.env["PLXNATIVE_APP_DIR"] = str(self.root / "pkg")
        # Bundled preview helpers import other SDK modules. Keep the verified SDK immutable.
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        info = self.run("--hud-info")
        if (info.get("protocol") != 1 or not isinstance(info.get("source_sha"), str)
            or not re.fullmatch("[0-9a-f]{7,40}", info["source_sha"])
            or not pin["source_sha"].startswith(info["source_sha"])
            or info.get("app_version") != self.manifest.get("reported_version")) :
            raise Invalid("simulator binary does not report the pinned source/format")
        validate_contract(info)
        if any(info.get(key) != pin[key] for key in CONTRACT_KEYS):
            raise Invalid("simulator binary support/schema/limits differ from its pin")
        self.languages = info["languages"]
        if not self.languages or len(set(self.languages)) != len(self.languages):
            raise Invalid("simulator language list must be nonempty and unique")
        if calibration is not None:
            profile = read_json(calibration)
            if profile.get("protocol") != 1 or not profile.get("evidence") or not profile.get("host_source_sha") or not pin["source_sha"].startswith(profile["host_source_sha"]):
                raise Invalid("text calibration must identify measurements from the pinned simulator")
            if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or v < 0 for v in profile.get("by_rung", {}).values()):
                raise Invalid("text calibration margins must be finite and nonnegative")
            if profile.get("font_hashes") != self.manifest.get("font_hashes"):
                raise Invalid("text calibration uses different font bytes")
            if profile.get("renderer_hashes"):
                from calibrate import renderer_hashes
                if profile["renderer_hashes"] != renderer_hashes(self.manifest):
                    raise Invalid("text calibration uses different renderer libraries")
            if set(profile.get("by_rung", {})) != set(info["rungs"]):
                raise Invalid("text calibration omits a supported type rung")
        self.info = info

    def run(self, *args, findings=False):
        process = subprocess.run([str(self.binary), *map(str, args)], env=self.env,
                                 capture_output=True, text=True, timeout=300)
        if process.returncode not in ((0, 1) if findings else (0,)):
            raise Invalid(f"simulator failed ({process.returncode}): {process.stderr.strip()}")
        try:
            output = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise Invalid("simulator did not return a JSON report") from exc
        if not isinstance(output, dict):
            raise Invalid("simulator report must be a JSON object")
        if findings and bool(output.get("findings")) != bool(process.returncode):
            raise Invalid("simulator exit status and lint report disagree")
        if findings:
            if output.get("protocol") != 1 or not isinstance(output.get("findings"), list):
                raise Invalid("simulator did not return a protocol 1 findings report")
            for finding in output["findings"]:
                if ("file" not in finding or finding["file"] is not None and not isinstance(finding["file"], str)
                    or not isinstance(finding.get("path"), str) or finding["path"] and not finding["path"].startswith("/")):
                    raise Invalid("simulator finding needs a member file and JSON pointer")
        return output

    def lint(self, path: Path, language="all"):
        args = ["--hud-lint", path, "--format", "json", "--lang", language]
        if self.calibration is not None:
            args += ["--text-skew", self.calibration]
        report = self.run(*args, findings=True)
        if path.is_file():
            maximum = max(profile["artifact_bytes"] for profile in self.pin["limits"]["package"].values())
            if report.get("package_sha256") is None and report["findings"] and path.stat().st_size > maximum:
                return report
            self.bind_report(report, path)
        return report

    @staticmethod
    def bind_report(report, path):
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if report.get("package_sha256") != digest:
            raise Invalid("native report archive hash differs from its input bytes")
        return content, digest

    def pack(self, source: Source, output: Path) -> Package:
        report = self.run("--hud-pack", source.path, "--out", output, "--format", "json", findings=True)
        if report["findings"]:
            raise Invalid(f"{source.id}: native packaging findings: {json.dumps(report['findings'], ensure_ascii=False)}")
        content, digest = self.bind_report(report, output)
        if report.get("bytes") != len(content):
            raise Invalid("native pack report archive bytes differ from its output")
        metadata = report.get("manifest")
        if metadata != source.metadata or not supports(Source(source.path, metadata), self.pin):
            raise Invalid("native packed manifest changed during SDK selection")
        return Package(output, metadata, content, digest, self.pin)

    def read_package(self, path: Path) -> Package:
        report = self.run("--hud-inspect", path, findings=True)
        content, digest = self.bind_report(report, path)
        if report["findings"] or not isinstance(report.get("manifest"), dict):
            raise Invalid("native inspection refused the package")
        return Package(path, report["manifest"], content, digest, self.pin)

    def inspect(self, package: Package):
        actual = self.read_package(package.path)
        if (actual.sha256 != package.sha256 or actual.content != package.content
            or actual.metadata != package.metadata or actual.pin != package.pin):
            raise Invalid("native inspected package differs from its validated snapshot")
        return actual
