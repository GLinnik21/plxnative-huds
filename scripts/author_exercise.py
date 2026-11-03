"""Use the public source example and native member/pointer findings in two iterations."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from catalog import Source, oldest, read_json
from simulator import Simulator, acquire, toolchains


def exercise(root, cache):
    with tempfile.TemporaryDirectory(prefix="hud-author-") as temporary:
        directory = Path(temporary) / "author-exercise"
        shutil.copytree(root / "examples/minimal", directory)
        manifest_path = directory / "manifest.json"
        manifest = read_json(manifest_path)
        manifest.update(id="com.example.author-exercise", name="Author exercise", author="Example author", license="CC0-1.0")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        (directory / "README.md").write_text("Author exercise, CC0-1.0, Example author.\n")
        pin = oldest(Source(directory, manifest), toolchains(root))
        sim = Simulator(acquire(pin, cache), pin, root / pin["calibration"])
        hud_path = directory / manifest["hud"]["entry"]
        hud = read_json(hud_path)
        hud["unknown_author_option"] = True
        # Preserve insertion order, including every conditional object in the source.
        hud_path.write_text(json.dumps(hud, ensure_ascii=False, indent=2) + "\n")
        first = sim.lint(directory)
        if not any(f["file"] == manifest["hud"]["entry"] and f["path"] == "/unknown_author_option" for f in first["findings"]):
            raise ValueError("first authoring lint did not identify the member and invalid option")
        del hud["unknown_author_option"]
        hud_path.write_text(json.dumps(hud, ensure_ascii=False, indent=2) + "\n")
        second = sim.lint(directory)
        if second["findings"] or not second.get("package_sha256"):
            raise ValueError("public starter did not pass within two native lint iterations")
    return {"protocol": 1, "iterations": 2, "languages": sim.languages,
            "app_version": pin["app_version"], "source_sha": pin["source_sha"],
            "before": first, "after": second}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    args = parser.parse_args()
    print(json.dumps(exercise(args.root, args.cache), sort_keys=True))
