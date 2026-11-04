"""Read back every catalog link, original package hash and preview hash before Pages deploys.

A staged `index.signed` is verified against `keys.json` too; `--require-signed` (the deploy path)
fails a catalog that has none.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from catalog import check_serial
from sign_index import KEYS, Refused, load_keys, verify_signed
from simulator import validate_pin


def check_signature(root, keys=KEYS, required=False):
    """The serial of the verified `index.signed`, or None when the catalog is unsigned and may be."""
    path = root / "index.signed"
    if not path.exists() and not required:
        return None
    assert path.is_file() and not path.is_symlink(), "index.signed is missing from a catalog that must be signed"
    signed = path.read_bytes()
    try:
        _, serial = verify_signed(signed, load_keys(keys))
    except Refused as exc:
        raise AssertionError(f"index.signed is not acceptable: {exc}") from exc
    assert signed.partition(b"\n")[2] == (root / "index.json").read_bytes(), "index.signed does not carry the published index.json bytes"
    return serial


def check(root, require_signed=False, keys=KEYS):
    index = json.loads((root / "index.json").read_text())
    revoked = {item["sha256"] for item in index["revoked"]}
    for entry in index["entries"]:
        assert entry["sha256"] not in revoked, "revoked package remains offered"
        path = root / "p" / (entry["sha256"] + ".plxhud")
        data = path.read_bytes()
        assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert urlsplit(entry["url"]).path.endswith("/p/" + path.name)
        validate_pin(entry["sdk"])
        proof = json.loads((root / "previews" / entry["sha256"] / "manifest.json").read_text())
        assert proof["package_sha256"] == entry["sha256"] and proof["sdk"] == entry["sdk"]
        for preview in entry["previews"]:
            image = root / "previews" / entry["sha256"] / preview["file"]
            assert hashlib.sha256(image.read_bytes()).hexdigest() == preview["sha256"]
            assert urlsplit(preview["url"]).path.endswith("/previews/" + entry["sha256"] + "/" + image.name)
    assert (root / "CREDITS.md").is_file()
    assert json.loads((root / "revoked.json").read_text()) == index["revoked"]
    check_serial(index.get("serial"))
    check_signature(root, keys, require_signed)
    return len(index["entries"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("site", type=Path)
    parser.add_argument("--require-signed", action="store_true", help="fail unless index.signed is present and verifies")
    args = parser.parse_args()
    print(f"Checked {check(args.site, args.require_signed)} published packages and every preview byte"
          + (" and the signed index" if args.require_signed else ""))
