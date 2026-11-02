"""Read back every catalog link, original package hash and preview hash before Pages deploys."""
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


def check(root):
    index = json.loads((root / "index.json").read_text())
    revoked = {item["sha256"] for item in index["revoked"]}
    for entry in index["entries"]:
        assert entry["sha256"] not in revoked, "revoked package remains offered"
        path = root / "p" / (entry["sha256"] + ".plxhud.json")
        data = path.read_bytes()
        assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert urlsplit(entry["url"]).path.endswith("/p/" + path.name)
        for preview in entry["previews"]:
            image = root / "previews" / entry["sha256"] / preview["file"]
            assert hashlib.sha256(image.read_bytes()).hexdigest() == preview["sha256"]
            assert urlsplit(preview["url"]).path.endswith("/previews/" + entry["sha256"] + "/" + image.name)
    assert (root / "CREDITS.md").is_file()
    assert json.loads((root / "revoked.json").read_text()) == index["revoked"]
    return len(index["entries"])


if __name__ == "__main__":
    print(f"Checked {check(Path(sys.argv[1]))} published packages and every preview byte")
