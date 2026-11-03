"""Render HUDs with their oldest compatible pinned app, retaining full-matrix proof and preview diffs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.request import build_opener
from urllib.error import URLError
import sys
from catalog import Invalid, canonical, oldest, packages, public_origin, read_json, require_sources, revoked
from simulator import SecureRedirect, Simulator, acquire, toolchains


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
    current_manifest = read_json(current / "manifest.json")
    before_manifest = read_json(previous / "manifest.json") if (previous / "manifest.json").is_file() else {"scenes":[]}
    before_states = {scene["state"]:scene["file"] for scene in before_manifest["scenes"]}
    for scene in current_manifest["scenes"]:
        image = current / scene["file"]
        before_name = before_states.get(scene["state"])
        before = previous / before_name if before_name else None
        if before is None or not before.is_file():
            result.append({"file": image.name, "state":scene["state"], "status": "new"}); continue
        same = hashlib.sha256(image.read_bytes()).digest() == hashlib.sha256(before.read_bytes()).digest()
        item = {"file": image.name, "state":scene["state"], "status": "identical" if same else "changed"}
        if not same:
            output.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(before, output / (scene["state"] + ".before.png"))
            target = output / (scene["state"] + ".diff.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(before), "-i", str(image),
                            "-filter_complex", "blend=all_mode=difference,lutrgb=r=val*4:g=val*4:b=val*4",
                            "-frames:v", "1", str(target)], check=True)
            item["diff"] = target.name
        result.append(item)
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_bytes(canonical({"format":1,"scenes":result}))
    return result


def published(sim, package, directory, base_url):
    """Reuse only a complete, byte-verified matrix from the identical pinned compiler."""
    public_origin(base_url)
    prefix = base_url.rstrip("/") + "/previews/" + package.sha256 + "/"
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="preview-reuse-",dir=directory.parent) as temporary:
        stage = Path(temporary)
        def fetch(name, maximum):
            with build_opener(SecureRedirect).open(prefix + name,timeout=30) as response:
                content = response.read(maximum + 1)
            if len(content) > maximum:
                raise Invalid("published preview exceeds its byte bound")
            (stage / name).write_bytes(content)
        try:
            fetch("manifest.json",2*1024*1024)
            manifest = read_json(stage / "manifest.json")
            for scene in manifest["scenes"]:
                name = scene["file"]
                if Path(name).name != name or not name.endswith(".png"):
                    raise Invalid("unsafe published preview filename")
                fetch(name,32*1024*1024)
            verify(sim,package,stage)
        except (Invalid,OSError,ValueError,KeyError,URLError):
            return False
        if directory.exists():
            shutil.rmtree(directory)
        shutil.copytree(stage,directory)
        return True


def render(root, cache, output, snapshot=Path("out/packages"), previous_snapshot=None, previous_previews=None, local=None, only=None, reuse_url=None):
    pins = toolchains(root)
    rejected = {item["sha256"] for item in revoked(root)}
    before = {p.id: p for p in packages(previous_snapshot)} if previous_snapshot else {}
    prepared = set()
    candidates = packages(snapshot)
    require_sources(root, candidates)
    if only is not None:
        candidates = [package for package in candidates if package.id == only]
        if not candidates:
            raise Invalid("requested package does not exist")
    for package in candidates:
        if package.sha256 in rejected:
            continue
        pin = oldest(package, pins)
        if package.pin != pin:
            raise Invalid("package was built with a different SDK than the selected pin")
        sim = Simulator(local or acquire(pin, cache), pin, root / pin["calibration"])
        sim.inspect(package)
        directory = output / package.sha256
        reused = reuse_url is not None and published(sim,package,directory,reuse_url)
        if reused:
            print("Reused complete pinned previews:",package.id,flush=True)
        else:
            env = dict(sim.env)
            env["PLXNATIVE_DEMO_CACHE"] = str((cache.parent / "demo-library").resolve())
            if pin["sha256"] not in prepared:
                for action in ("fetch", "derive"):
                    subprocess.run([sys.executable, str(sim.root / "tools/demo_library.py"), action], env=env, check=True, timeout=1200)
                prepared.add(pin["sha256"])
            if directory.exists():
                shutil.rmtree(directory)
            subprocess.run([sys.executable, str(sim.root / "tools/hud_preview.py"), "--bin", str(sim.binary),
                            "--hud", str(package.path.resolve()), "--out", str(directory.resolve())],
                           # A full matrix has its own budget; each scene still has the
                           # app tool's independent 180-second settle deadline.
                           env=env, check=True, timeout=90 * 60)
            verify(sim, package, directory)
        earlier = before.get(package.id)
        if earlier and previous_previews:
            differences(directory, previous_previews / earlier.sha256, output / "diffs" / package.id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--out", type=Path, default=Path("out/previews"))
    parser.add_argument("--packages", type=Path, default=Path("out/packages"))
    parser.add_argument("--previous-packages", type=Path)
    parser.add_argument("--previous-previews", type=Path)
    parser.add_argument("--local-simulator", type=Path)
    parser.add_argument("--package")
    parser.add_argument("--reuse-url")
    args = parser.parse_args()
    render(args.root, args.cache, args.out, args.packages, args.previous_packages, args.previous_previews, args.local_simulator, args.package, args.reuse_url)


if __name__ == "__main__":
    main()
