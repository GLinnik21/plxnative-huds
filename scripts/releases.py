"""Accept immutable app release simulators and derive calibration from measured TV evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen
from calibrate import calibrate
from catalog import Invalid, canonical, read_json, release
from simulator import acquire, toolchains, validate_pin

APP = "GLinnik21/plx-native"
ARCHIVE = "plxnative-hud-simulator-linux-x86_64.tar.gz"
PIN_ASSET = "plxnative-hud-simulator-linux-x86_64.tar.pin.json"


def immutable(before, after):
    later = {pin["app_version"]: pin for pin in after}
    for pin in before:
        if not pin.get("development", False) and later.get(pin["app_version"]) != pin:
            raise Invalid("published app simulator pins cannot be changed or removed")


def accept(root, cache, pin):
    pin = dict(pin)
    release(pin["app_version"])
    if pin.get("development"):
        raise Invalid("release notifications cannot replace an app with a development toolchain")
    config = read_json(root / "toolchains.json")
    previous = config["simulators"]
    matching = next((item for item in previous if item["app_version"] == pin["app_version"]), None)
    if matching and not matching.get("development"):
        # A repeated dispatch is idempotent, but changing any immutable identity is an error.
        for key in ("source_sha", "sha256", "manifest_sha256", "bytes", "formats", "url"):
            if matching[key] != pin[key]:
                raise Invalid("app release attempted to replace an immutable simulator")
        return False
    pin["calibration"] = "calibration/" + pin["manifest_sha256"] + ".json"
    validate_pin(pin)
    directory = acquire(pin, cache)
    host = read_json(directory / "text-metrics.json")
    television = read_json(root / "calibration/tv-metrics.json")
    profile = calibrate(host, television)
    import hashlib
    profile["evidence"] = {"host": hashlib.sha256((directory / "text-metrics.json").read_bytes()).hexdigest(),
                           "tv": hashlib.sha256((root / "calibration/tv-metrics.json").read_bytes()).hexdigest()}
    name = "calibration/" + pin["manifest_sha256"] + ".json"
    (root / name).write_bytes(canonical(profile))
    (root / "calibration" / (pin["manifest_sha256"] + ".host.json")).write_bytes(canonical(host))
    pin["calibration"] = name
    config["simulators"] = [item for item in previous if item["app_version"] != pin["app_version"]] + [pin]
    immutable(previous, config["simulators"])
    config["simulators"].sort(key=lambda item: release(item["app_version"]))
    (root / "toolchains.json").write_bytes(canonical(config))
    toolchains(root)
    return True


def discover():
    process = subprocess.run(["gh","api",f"repos/{APP}/releases","--paginate","--slurp"],capture_output=True,text=True,check=True)
    for page in json.loads(process.stdout):
        for item in page:
            if item["draft"] or item["prerelease"] or not item["tag_name"].startswith("v"):
                continue
            assets = {asset["name"]: asset["browser_download_url"] for asset in item["assets"]}
            if ARCHIVE not in assets or PIN_ASSET not in assets:
                continue
            url = assets[PIN_ASSET]
            prefix = f"https://github.com/{APP}/releases/download/"
            if not url.startswith(prefix):
                raise Invalid("release pin asset has an unexpected origin")
            with urlopen(url, timeout=60) as response:
                pin = json.load(response)
            if item["tag_name"] != "v" + pin["app_version"]:
                raise Invalid("release pin version differs from its release tag")
            pin["url"] = assets[ARCHIVE]
            yield pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--event", type=Path)
    args = parser.parse_args()
    incoming = []
    if args.event:
        event = read_json(args.event)
        if event.get("action") == "app-release":
            incoming.append(event["client_payload"]["simulator"])
    incoming.extend(discover())
    for pin in incoming:
        accept(args.root, args.cache, pin)


if __name__ == "__main__":
    main()
