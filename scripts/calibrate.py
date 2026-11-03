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


# These are the native text stack shipped by the app bundle, including its caption renderer.
RENDERER_FILES = ("lib/libSDL2_ttf-2.0.so.0", "lib/libfreetype.so.6",
                  "lib/libharfbuzz.so.0", "pkg/libass-plx-host.so.0")


def renderer_hashes(manifest):
    files = manifest["files"]
    if any(name not in files for name in RENDERER_FILES):
        raise Invalid("simulator manifest omits a text renderer library")
    return {name: files[name] for name in RENDERER_FILES}


def type_sizes(report):
    result = {}
    for row in rows(report).values():
        rung, size = row["rung"], row["size"]
        if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0:
            raise Invalid("invalid text corpus type size")
        if rung in result and result[rung] != size:
            raise Invalid("a type rung has inconsistent sizes")
        result[rung] = size
    return result


def release_profile(host, television, manifest, previous):
    renderers = renderer_hashes(manifest)
    sizes = type_sizes(host)
    try:
        profile = calibrate(host, television)
    except Invalid as mismatch:
        # The measured margin is empirical headroom for a renderer and type scale. New
        # translations must reach lint, even though the TV evidence predates those strings.
        # Never describe a carried margin as a new native measurement.
        basis = next((p for p in reversed(previous)
                      if p.get("font_hashes") == host["font_hashes"]
                      and p.get("renderer_hashes") == renderers
                      and p.get("type_sizes") == sizes), None)
        if basis is None:
            raise Invalid("changed corpus requires a matching measured renderer/font/type-scale baseline or fresh TV measurements") from mismatch
        profile = {**basis, "host_source_sha": host["source_sha"],
                   "measured_host_source_sha": basis.get("measured_host_source_sha", basis["host_source_sha"]),
                   "carried_from": basis["host_source_sha"],
                   "current_languages": sorted({r["lang"] for r in rows(host).values()}),
                   "current_corpus_rows": len(rows(host))}
        # Keep the original measured-host hash when rebinding current-host evidence below.
        profile["measured_host_evidence"] = basis.get("measured_host_evidence", basis["evidence"]["host"])
    profile["renderer_hashes"] = renderers
    profile["type_sizes"] = sizes
    return profile


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
