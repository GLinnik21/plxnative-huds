"""Measure per-rung registry headroom from the app's Linux and real-TV text corpus reports."""
from __future__ import annotations
import argparse
import hashlib
import math
from pathlib import Path
from catalog import Invalid, canonical, read_json


def rows(report):
    if report.get("protocol") != 1 or not report.get("font_hashes") or not report.get("metrics"):
        raise Invalid("expected an app text-measurement report")
    result = {}
    for row in report["metrics"]:
        key = tuple(row[field] for field in ("lang", "rung", "bold", "role"))
        width = row["width"]
        if key in result or isinstance(width, bool) or not isinstance(width, (float, int)) or not math.isfinite(width) or width <= 0:
            raise Invalid("duplicate or invalid corpus measurement")
        result[key] = row
    return result


def calibrate(host, television):
    if host["font_hashes"] != television["font_hashes"]:
        raise Invalid("Linux and TV must measure exactly the same font bytes")
    a, b = rows(host), rows(television)
    if a.keys() != b.keys():
        raise Invalid("Linux and TV corpus coverage differs")
    by_rung, maxima, coverage = {}, {}, {}
    for key, row in a.items():
        other = b[key]
        if row["size"] != other["size"] or row["text"] != other["text"] and not row["role"].startswith("clock.max."):
            raise Invalid("Linux and TV measured different text or type sizes")
        rung = row["rung"]
        delta = max(0, other["width"] - row["width"])
        if rung not in maxima or delta > maxima[rung]["delta"]:
            maxima[rung] = {"delta": delta, "lang": row["lang"], "bold": row["bold"], "role": row["role"],
                            "host_width": row["width"], "tv_width": other["width"]}
        by_rung[rung] = max(by_rung.get(rung, 0), math.ceil(delta))
        coverage.setdefault(rung, set()).add((row["lang"], row["bold"]))
    languages = {key[0] for key in a}
    for rung, pairs in coverage.items():
        if pairs != {(lang, bold) for lang in languages for bold in (True, False)}:
            raise Invalid(f"incomplete language/weight coverage: {rung}")
    return {"protocol": 1, "by_rung": by_rung, "font_hashes": host["font_hashes"], "maxima": maxima,
            "languages": sorted(languages), "corpus_rows": len(a),
            "host_source_sha": host["source_sha"], "tv_source_sha": television["source_sha"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--tv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = calibrate(read_json(args.host), read_json(args.tv))
    result["evidence"] = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in (("host", args.host), ("tv", args.tv))}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(result))


if __name__ == "__main__":
    main()
