"""Stage a deterministic Pages catalog only after checking each full preview matrix and pinned app."""
import argparse
from pathlib import Path
import shutil
from catalog import generate, oldest, packages, read_json, revoked
from previews import verify
from simulator import Simulator, acquire, toolchains


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--previews", type=Path, default=Path("out/previews"))
    parser.add_argument("--out", type=Path, default=Path("out/site"))
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    pins = toolchains(args.root)
    rejected = {item["sha256"] for item in revoked(args.root)}
    credits = None
    for package in packages(args.root):
        if package.sha256 in rejected:
            continue
        pin = oldest(package, pins)
        sim = Simulator(acquire(pin, args.cache), pin, args.root / pin["calibration"])
        verify(sim, package, args.previews / package.sha256)
        credits = sim.root / "docs/screenshots/CREDITS.md"
    if args.out.exists():
        shutil.rmtree(args.out)
    generate(args.root, args.out, args.previews, args.base_url, read_json(args.root / "compatibility.json"))
    if credits:
        shutil.copyfile(credits, args.out / "CREDITS.md")
    else:
        (args.out / "CREDITS.md").write_text("No active preview media.\n")


if __name__ == "__main__":
    main()
