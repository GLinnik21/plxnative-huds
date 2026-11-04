"""Stage a deterministic Pages catalog only after checking each full preview matrix and pinned app."""
import argparse
import os
from pathlib import Path
import shutil
from catalog import Invalid, check_serial, generate, oldest, packages, read_json, require_sources, revoked
from previews import verify
from preview_media import ART
from simulator import Simulator, acquire, toolchains


def serial_text(text):
    try:
        return check_serial(int(text, 10))
    except (ValueError, Invalid) as exc:
        raise argparse.ArgumentTypeError(f"expected UTC epoch seconds as a decimal integer, got {text!r}") from exc


def parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--previews", type=Path, default=Path("out/previews"))
    parser.add_argument("--packages", type=Path, default=Path("out/packages"))
    parser.add_argument("--out", type=Path, default=Path("out/site"))
    parser.add_argument("--base-url", required=True)
    # The workflow fixes the serial once per run in HUD_INDEX_SERIAL; tests and local runs pass --serial.
    parser.add_argument("--serial", type=serial_text, default=os.environ.get("HUD_INDEX_SERIAL"),
                        help="UTC epoch seconds of this publish run (default: $HUD_INDEX_SERIAL)")
    return parser


def arguments(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.serial is None:
        cli.error("pass --serial or set HUD_INDEX_SERIAL; an index without a serial is not publishable")
    return args


def main():
    args = arguments()
    pins = toolchains(args.root)
    rejected = {item["sha256"] for item in revoked(args.root)}
    credits = None
    built = packages(args.packages)
    require_sources(args.root, built)
    for package in built:
        if package.sha256 in rejected:
            continue
        pin = oldest(package, pins)
        if pin != package.pin:
            raise Invalid("publication SDK differs from the package build pin")
        sim = Simulator(acquire(pin, args.cache), pin, args.root / pin["calibration"])
        sim.inspect(package)
        verify(sim, package, args.previews / package.sha256)
        credits = ART / "CREDITS.md"
    if args.out.exists():
        shutil.rmtree(args.out)
    generate(args.root, args.out, args.previews, args.base_url, read_json(args.root / "compatibility.json"), built,
             serial=args.serial)
    if credits:
        shutil.copyfile(credits, args.out / "CREDITS.md")
    else:
        (args.out / "CREDITS.md").write_text("No active preview media.\n")


if __name__ == "__main__":
    main()
