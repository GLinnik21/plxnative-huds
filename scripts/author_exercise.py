"""A new author starts from the public guide/schema/example and passes within two lint iterations."""
import argparse
import json
from pathlib import Path
import tempfile
from catalog import Package, canonical, oldest, read_json
from simulator import Simulator, acquire, toolchains


def exercise(root, cache):
    # This fixture uses only the public starter's vocabulary: identity and palette edits. It
    # deliberately includes one unknown root key, whose pointer the first lint must explain.
    value = read_json(root / "examples/minimal.plxhud.json")
    value.update(id="com.example.author-exercise", name="Author exercise", author="Example author", license="CC0-1.0")
    value["unknown_author_option"] = True
    package = Package(Path("unused"), value, b"", "unused")
    pin = oldest(package, toolchains(root))
    sim = Simulator(acquire(pin, cache), pin, root / pin["calibration"])
    with tempfile.TemporaryDirectory(prefix="hud-author-") as temporary:
        path = Path(temporary) / "hud.plxhud.json"
        path.write_bytes(canonical(value))
        first = sim.lint(path)
        if not any(f["path"] == "/unknown_author_option" for f in first["findings"]):
            raise ValueError("first authoring lint did not identify the invalid option")
        del value["unknown_author_option"]
        path.write_bytes(canonical(value))
        second = sim.lint(path)
        if second["findings"]:
            raise ValueError("public starter did not pass within two lint iterations")
    return {"iterations": 2, "languages": sim.languages, "app_version": pin["app_version"], "source_sha": pin["source_sha"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    args = parser.parse_args()
    print(json.dumps(exercise(args.root, args.cache), sort_keys=True))
