"""Render HUDs with their oldest compatible pinned app, retaining full-matrix proof and preview diffs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from catalog import Invalid, canonical, oldest, packages, read_json, revoked
from simulator import Simulator, acquire, toolchains


def expected(sim, package):
    command = [sys.executable, str(sim.root / "tools/hud_preview.py"), "--bin", str(sim.binary),
               "--hud", str(package.path.resolve()), "--out", "unused", "--plan"]
    process = subprocess.run(command, env=sim.env, text=True, capture_output=True, check=True, timeout=300)
    return [scene["name"] for scene in json.loads(process.stdout)]


def verify(sim, package, directory):
    manifest = read_json(directory / "manifest.json")
    names = expected(sim, package)
    actual = [scene["state"] for scene in manifest.get("scenes", [])]
    if (manifest.get("package_sha256") != package.sha256 or not manifest.get("complete")
        or manifest.get("required") != names or sorted(actual) != sorted(names) or len(set(actual)) != len(actual)):
        raise Invalid(f"incomplete preview state matrix: {package.id}")
    provenance = manifest.get("simulator", {})
    if provenance != sim.info:
        raise Invalid("preview was rendered with a different simulator than the oldest compatible pin")
    for scene in manifest["scenes"]:
        name = scene["file"]
        if Path(name).name != name or not name.endswith(".png"):
            raise Invalid("unsafe preview filename")
        path = directory / name
        data = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(data).hexdigest() != scene["sha256"]:
            raise Invalid("preview bytes do not match their provenance")
        if data[:8] != b"\x89PNG\r\n\x1a\n" or tuple(int.from_bytes(data[i:i+4], "big") for i in (16,20)) != (1920,1080):
            raise Invalid("registry previews must be native 1920x1080 PNGs")
    return manifest


def differences(current, previous, output):
    """Keep the previous image and an amplified absolute-difference image beside changed captures."""
    result = []
    for image in sorted(current.glob("*.png")):
        before = previous / image.name
        if not before.is_file():
            result.append({"file": image.name, "status": "new"}); continue
        same = hashlib.sha256(image.read_bytes()).digest() == hashlib.sha256(before.read_bytes()).digest()
        item = {"file": image.name, "status": "identical" if same else "changed"}
        if not same:
            output.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(before, output / (image.stem + ".before.png"))
            target = output / (image.stem + ".diff.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(before), "-i", str(image),
                            "-filter_complex", "blend=all_mode=difference,lutrgb=r=val*4:g=val*4:b=val*4",
                            "-frames:v", "1", str(target)], check=True)
            item["diff"] = target.name
        result.append(item)
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_bytes(canonical({"format":1,"scenes":result}))
    return result


def render(root, cache, output, previous_root=None, previous_previews=None, local=None):
    pins = toolchains(root)
    rejected = {item["sha256"] for item in revoked(root)}
    before = {p.id: p for p in packages(previous_root)} if previous_root else {}
    prepared = set()
    for package in packages(root):
        if package.sha256 in rejected:
            continue
        pin = oldest(package, pins)
        sim = Simulator(local or acquire(pin, cache), pin, root / pin["calibration"])
        env = dict(sim.env)
        env["PLXNATIVE_DEMO_CACHE"] = str((cache.parent / "demo-library").resolve())
        if pin["sha256"] not in prepared:
            for action in ("fetch", "derive"):
                subprocess.run([sys.executable, str(sim.root / "tools/demo_library.py"), action], env=env, check=True, timeout=1200)
            prepared.add(pin["sha256"])
        directory = output / package.sha256
        if directory.exists():
            shutil.rmtree(directory)
        subprocess.run([sys.executable, str(sim.root / "tools/hud_preview.py"), "--bin", str(sim.binary),
                        "--hud", str(package.path.resolve()), "--out", str(directory.resolve())],
                       env=env, check=True, timeout=3600)
        verify(sim, package, directory)
        earlier = before.get(package.id)
        if earlier and previous_previews:
            differences(directory, previous_previews / earlier.sha256, output / "diffs" / package.id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--out", type=Path, default=Path("out/previews"))
    parser.add_argument("--previous-root", type=Path)
    parser.add_argument("--previous-previews", type=Path)
    parser.add_argument("--local-simulator", type=Path)
    args = parser.parse_args()
    render(args.root, args.cache, args.out, args.previous_root, args.previous_previews, args.local_simulator)


if __name__ == "__main__":
    main()
