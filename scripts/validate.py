"""Build each source once with the pinned app, then validate those exact archives."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile

from catalog import Invalid, canonical, check_update, oldest, read_json, revoked, sources, write_packages
from simulator import Simulator, acquire, toolchains
from releases import immutable


def pointer(parts):
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def corpus_path(base, name):
    path = Path(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise Invalid("unsafe app corpus path")
    return base / path


def schema_agreement(simulator: Simulator, root: Path):
    from jsonschema import Draft202012Validator
    validators = {}
    for kind, versions in simulator.pin["schemas"].items():
        for version in versions:
            generated = simulator.run("--hud-schema", kind, "--version", version)
            if generated != read_json(root / "schema" / kind / (version + ".json")):
                raise Invalid(f"registry {kind} schema mirror differs from the pinned app")
            Draft202012Validator.check_schema(generated)
            validators[kind, version] = Draft202012Validator(generated)
    corpus = simulator.root / "corpus"
    index = read_json(corpus / "manifest.json")
    if index.get("protocol") != 1 or not isinstance(index.get("cases"), list):
        raise Invalid("pinned simulator needs an indexed protocol 1 fixture corpus")
    kinds = set()
    archives = 0
    for case in index["cases"]:
        report = simulator.lint(corpus_path(corpus, case["input"]))
        findings = report["findings"]
        if type(case.get("invalid")) is not bool or not isinstance(case.get("documents"), list):
            raise Invalid("invalid app corpus case declaration")
        if not case["documents"]:
            archives += 1
            if not case["invalid"] or not case["input"].endswith(".plxhud"):
                raise Invalid("archive corpus case must name an invalid .plxhud")
        for document in case["documents"]:
            key = document["kind"], document["version"]
            kinds.add(key[0])
            validator = validators[key]
            # Stock readers cannot retain duplicate keys. The native parser judges those.
            try:
                value = json.loads(corpus_path(corpus, document["path"]).read_text())
            except (UnicodeError, json.JSONDecodeError):
                if not any(f["file"] == document["file"] for f in findings):
                    raise Invalid("native parser accepted malformed corpus JSON")
                continue
            for error in validator.iter_errors(value):
                at = pointer(error.absolute_path)
                if not any(f["file"] == document["file"] and (f["path"] == at or f["path"].startswith(at + "/")) for f in findings):
                    raise Invalid(f"schema/parser location disagreement: {document['file']}: {at}")
        if bool(findings) != case["invalid"]:
            raise Invalid(f"native corpus verdict disagrees with its declaration: {case['input']}")
    if kinds != {"manifest", "hud"} or not archives:
        raise Invalid("app corpus must exercise both document schemas and invalid archives")
    return validators, len(index["cases"])


def stock_package(package, validators):
    """Check both documents from the already native-validated archive, with stock JSON Schema."""
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        documents = (("manifest", package.metadata["package_format"], "manifest.json"),
                     ("hud", package.metadata["hud"]["format"], package.metadata["hud"]["entry"]))
        for kind, version, member in documents:
            value = json.loads(archive.read(member))
            errors = list(validators[kind, version].iter_errors(value))
            if errors:
                error = errors[0]
                raise Invalid(f"{package.id}: schema: {member}{pointer(error.absolute_path)}: {error.message}")


def build_packages(root, cache, output, local=None, *, initial_baseline=False):
    candidates = sources(root, initial_baseline=initial_baseline)
    if not candidates:
        write_packages(output, [])
        return []
    pins = toolchains(root)
    simulators = {}
    built = []
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-pack-", dir=output) as temporary:
        for source in candidates:
            pin = oldest(source, pins)
            key = pin["sha256"]
            if key not in simulators:
                simulators[key] = Simulator(local or acquire(pin, cache), pin, root / pin["calibration"])
            package = simulators[key].pack(source, Path(temporary) / (source.id + ".plxhud"))
            built.append(package)
        write_packages(output, built)
    # All later stages read the persisted snapshot, whose paths survive the temporary builder.
    from catalog import packages
    return packages(output)


def validate(root: Path, cache: Path, previous: Path | None = None, local: Path | None = None,
             output=Path("out/packages"), previous_output=Path("out/previous-packages")):
    pins = toolchains(root)
    before = []
    if previous is not None and (previous / "huds").is_dir():
        prior_sources = sources(previous, initial_baseline=True)
        if prior_sources:
            immutable(toolchains(previous), pins)
        before = build_packages(previous, cache, previous_output, local, initial_baseline=True)
    prior = {package.id: package for package in before}
    owners = read_json(root / "maintainers.json")
    for source in sources(root):
        contacts = owners.get(source.id, [])
        if not contacts or not all(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", name) for name in contacts):
            raise Invalid(f"{source.id}: register a GitHub maintenance contact")
    tombstones = {item["sha256"] for item in revoked(root)}
    simulators = {}
    result = []
    for package in build_packages(root, cache, output, local):
        check_update(package, prior.get(package.id))
        if package.sha256 in tombstones:
            continue
        pin = oldest(package, pins)
        key = pin["sha256"]
        if key not in simulators:
            sim = Simulator(local or acquire(pin, cache), pin, root / pin["calibration"])
            validators, count = schema_agreement(sim, root)
            simulators[key] = sim, validators, count
        sim, validators, count = simulators[key]
        sim.inspect(package)
        stock_package(package, validators)
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
    parser.add_argument("--packages", type=Path, default=Path("out/packages"))
    parser.add_argument("--previous-packages", type=Path, default=Path("out/previous-packages"))
    parser.add_argument("--out", type=Path, default=Path("out/validation.json"))
    args = parser.parse_args()
    try:
        reports = validate(args.root.resolve(), args.cache, args.previous, args.local_simulator, args.packages, args.previous_packages)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(canonical({"format": 1, "packages": reports}))
        for item in reports:
            for finding in item["report"]["findings"]:
                print(f'{item["id"]}: {finding["code"]} {finding["file"] or "archive"}{finding["path"]}: {finding["message"]}')
        if any(item["report"]["findings"] for item in reports):
            return 1
        print(f"Validated {len(reports)} native-built bundles in every language using their oldest compatible app")
        return 0
    except (Invalid, OSError, KeyError, ValueError) as error:
        print(f"registry: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
