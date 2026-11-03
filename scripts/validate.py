"""Validate registry packages with the pinned app and stock JSON Schema implementation."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

from catalog import Invalid, canonical, check_update, oldest, packages, read_json, revoked
from simulator import Simulator, acquire, toolchains
from releases import immutable


def pointer(parts):
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def schema_agreement(simulator: Simulator, root: Path):
    from jsonschema import Draft202012Validator
    generated = simulator.run("--hud-schema")
    version = simulator.pin["formats"][-1]
    if generated != read_json(root / "schema" / (version + ".json")):
        raise Invalid("registry schema mirror differs from the pinned app's descriptor table")
    validator = Draft202012Validator(generated)
    Draft202012Validator.check_schema(generated)
    # The corpus comes from the pinned APP bundle. A submission cannot weaken this proof by
    # removing the registry's local invalid examples or changing their expected findings.
    corpus = simulator.root / "corpus"
    count = 0
    for path in sorted(corpus.rglob("*.plxhud.json")):
        # Stock JSON parsers cannot see duplicate keys. The app is still required to reject them.
        value = json.loads(path.read_text())
        errors = list(validator.iter_errors(value))
        report = simulator.lint(path)
        findings = report["findings"]
        if not findings and errors:
            raise Invalid(f"schema rejects an app-accepted fixture: {path.name}")
        for error in errors:
            at = pointer(error.absolute_path)
            if not any(f["path"] == at or f["path"].startswith(at + "/") for f in findings):
                raise Invalid(f"schema/parser pointer disagreement: {path.name}: {at}")
        if path.parent.name == "invalid" and not findings:
            raise Invalid(f"app accepted an invalid fixture: {path.name}")
        count += 1
    if count == 0:
        raise Invalid("pinned simulator contains no schema/parser fixture corpus")
    return validator, count


def validate(root: Path, cache: Path, previous: Path | None = None, local: Path | None = None):
    pins = toolchains(root)
    if previous is not None and (previous / "toolchains.json").is_file():
        immutable(toolchains(previous), pins)
    tombstones = {item["sha256"] for item in revoked(root)}
    before = {p.id: p for p in packages(previous)} if previous is not None else {}
    owners = read_json(root / "maintainers.json")
    for package in packages(root):
        contacts = owners.get(package.id, [])
        if not contacts or not all(isinstance(name,str) and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?",name) for name in contacts):
            raise Invalid(f"{package.id}: register a GitHub maintenance contact")
    simulators = {}
    result = []
    for package in packages(root):
        check_update(package, before.get(package.id))
        if package.sha256 in tombstones:
            continue
        pin = oldest(package, pins)
        key = pin["sha256"]
        if key not in simulators:
            directory = local if local is not None else acquire(pin, cache)
            calibration = root / pin["calibration"]
            sim = Simulator(directory, pin, calibration)
            validator, count = schema_agreement(sim, root)
            simulators[key] = sim, validator, count
        sim, validator, count = simulators[key]
        errors = list(validator.iter_errors(package.metadata))
        if errors:
            raise Invalid(f"{package.id}: schema: {errors[0].message}")
        report = sim.lint(package.path)
        result.append({"id": package.id, "sha256": package.sha256, "app_version": pin["app_version"],
                       "source_sha": pin["source_sha"], "corpus_checked": count, "report": report})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path(".cache/simulators"))
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--local-simulator", type=Path)
    parser.add_argument("--out", type=Path, default=Path("out/validation.json"))
    args = parser.parse_args()
    try:
        reports = validate(args.root.resolve(), args.cache, args.previous, args.local_simulator)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(canonical({"format": 1, "packages": reports}))
        for item in reports:
            for finding in item["report"]["findings"]:
                print(f'{item["id"]}: {finding["code"]} {finding["path"]}: {finding["message"]}')
        if any(item["report"]["findings"] for item in reports):
            return 1
        print(f"Validated {len(reports)} packages in every language using their oldest compatible app")
        return 0
    except (Invalid, OSError, KeyError, ValueError) as error:
        print(f"registry: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
