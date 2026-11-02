"""Registry data contract and deterministic publication. No network or process execution."""
from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class Invalid(ValueError):
    pass


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise Invalid(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def read_json(path: Path):
    if path.is_symlink():
        raise Invalid(f"symlink is not registry data: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Invalid(f"invalid UTF-8 JSON: {path.name}: {exc}") from exc


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def release(version: str) -> tuple[int, int, int]:
    # The HUD format's semver is exactly X.Y.Z; pre-release app tools retain their provenance
    # separately and compare using their target release, never PEP-440 ordering.
    if not isinstance(version, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise Invalid(f"expected X.Y.Z release, got {version!r}")
    return tuple(int(part) for part in version.split("."))


def inside(version: str, bounds: dict) -> bool:
    value = release(version)
    return ("min" not in bounds or value >= release(bounds["min"])) and ("max" not in bounds or value <= release(bounds["max"]))


@dataclass(frozen=True)
class Package:
    path: Path
    metadata: dict
    content: bytes
    sha256: str

    @property
    def id(self):
        return self.metadata["id"]


def packages(root: Path) -> list[Package]:
    base = root / "huds"
    found = []
    if not base.is_dir() or base.is_symlink():
        raise Invalid("huds/ must be a real directory")
    for directory in sorted(base.iterdir()):
        if directory.is_symlink() or not directory.is_dir():
            raise Invalid(f"unexpected HUD entry: {directory.name}")
        path = directory / "hud.plxhud.json"
        metadata = read_json(path)
        ident = metadata.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+", ident):
            raise Invalid(f"registry ID must be reverse DNS: {directory.name}")
        if ident != directory.name:
            raise Invalid(f"package ID differs from its directory: {directory.name}")
        if not (directory / "README.md").is_file():
            raise Invalid(f"missing README: {ident}")
        release(metadata.get("version"))
        bounds = metadata.get("app", {})
        if not isinstance(bounds, dict):
            raise Invalid(f"app bounds must be an object: {ident}")
        for key in ("min", "max"):
            if key in bounds:
                release(bounds[key])
        if "min" in bounds and "max" in bounds and release(bounds["min"]) > release(bounds["max"]):
            raise Invalid(f"inverted app range: {ident}")
        content = path.read_bytes()
        found.append(Package(path, metadata, content, hashlib.sha256(content).hexdigest()))
    if not found:
        raise Invalid("registry must contain at least one HUD")
    return found


def oldest(package: Package, pins: list[dict]) -> dict:
    compatible = [pin for pin in pins if inside(pin["app_version"], package.metadata.get("app", {}))
                  and package.metadata["format"] in pin["formats"]]
    if not compatible:
        raise Invalid(f"no pinned simulator supports {package.id}")
    return min(compatible, key=lambda pin: (release(pin["app_version"]), pin["source_sha"]))


def check_update(current: Package, previous: Package | None):
    if previous is not None and current.sha256 != previous.sha256:
        if release(current.metadata["version"]) <= release(previous.metadata["version"]):
            raise Invalid(f"changed bytes require a newer package version: {current.id}")


def revoked(root: Path) -> list[dict]:
    values = read_json(root / "revoked.json")
    if not isinstance(values, list):
        raise Invalid("revoked.json must contain a list")
    seen = set()
    for item in values:
        if not isinstance(item, dict) or set(item) != {"sha256", "reason"}:
            raise Invalid("revocation needs exactly sha256 and reason")
        digest, reason = item["sha256"], item["reason"]
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest) or digest in seen:
            raise Invalid("invalid or duplicated revocation hash")
        if not isinstance(reason, str) or not reason.strip():
            raise Invalid("revocation needs a nonempty reason")
        seen.add(digest)
    return sorted(values, key=lambda item: item["sha256"])


def public_origin(url: str):
    split = urlsplit(url)
    if split.scheme != "https" or not split.hostname or split.username or split.password or split.query or split.fragment:
        raise Invalid("catalog base URL must be an HTTPS origin/path without credentials, query or fragment")


def generate(root: Path, output: Path, previews: Path, base_url: str, compatibility: dict) -> dict:
    """Copy original pack bytes and verified previews. Call only after lint and rendering succeed."""
    public_origin(base_url)
    base_url = base_url.rstrip("/")
    tombstones = revoked(root)
    rejected = {item["sha256"] for item in tombstones}
    entries = []
    output.mkdir(parents=True, exist_ok=True)
    for package in packages(root):
        if package.sha256 in rejected:
            continue
        manifest_path = previews / package.sha256 / "manifest.json"
        manifest = read_json(manifest_path)
        if manifest.get("package_sha256") != package.sha256 or not manifest.get("scenes"):
            raise Invalid(f"missing or mismatched preview proof: {package.id}")
        art = []
        for scene in manifest["scenes"]:
            relative = scene["file"]
            if Path(relative).name != relative or not relative.endswith(".png"):
                raise Invalid("preview must be one PNG basename")
            source = manifest_path.parent / relative
            if source.is_symlink():
                raise Invalid("preview cannot be a symlink")
            content = source.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != scene["sha256"]:
                raise Invalid(f"preview hash mismatch: {package.id}/{relative}")
            published_name = digest + ".png"
            target = output / "previews" / package.sha256 / published_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            art.append({**scene, "file": published_name, "url": f"{base_url}/previews/{package.sha256}/{published_name}"})
        # Preserve the renderer's complete proof for hash-checked reuse of unchanged entries.
        proof = {**manifest, "scenes": art}
        proof_path = output / "previews" / package.sha256 / "manifest.json"
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_bytes(canonical(proof))
        target = output / "p" / (package.sha256 + ".plxhud.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(package.content)
        m = package.metadata
        fit = compatibility.get("packages", {}).get(package.sha256, {})
        bounds = dict(m.get("app", {}))
        if fit.get("app_max"):
            ceiling = fit["app_max"]
            release(ceiling)
            if "max" not in bounds or release(ceiling) < release(bounds["max"]):
                bounds["max"] = ceiling
        entries.append({"id": package.id, "version": m["version"], "format": m["format"],
                        "name": m["name"], "author": m["author"], "license": m["license"],
                        "app": bounds, "sha256": package.sha256, "bytes": len(package.content),
                        "url": f"{base_url}/p/{package.sha256}.plxhud.json", "previews": art,
                        "unfit": fit.get("unfit", [])})
    index = {"format": 1, "entries": entries, "revoked": tombstones}
    (output / "index.json").write_bytes(canonical(index))
    (output / "revoked.json").write_bytes(canonical(tombstones))
    cards = []
    for entry in entries:
        preview = entry["previews"][0]
        options = ''.join('<option value="' + html.escape(scene["url"],quote=True) + '">'
                          + html.escape(scene["state"].replace("-"," ") + " · " + scene["lang"]) + '</option>'
                          for scene in entry["previews"])
        select = '<label>Preview state <select onchange="const card=this.closest(\'article\');card.querySelector(\'img\').src=this.value;card.querySelector(\'a.preview\').href=this.value">' + options + '</select></label>'
        cards.append(f'<article><h2>{html.escape(entry["name"])}</h2><p>{html.escape(entry["id"])} · {html.escape(entry["version"])}</p>'
                     + select + f'<a class="preview" href="{html.escape(preview["url"], quote=True)}">'
                     f'<img width="1920" height="1080" loading="lazy" alt="Player HUD preview" src="{html.escape(preview["url"], quote=True)}"></a>'
                     f'<p><a href="{html.escape(entry["url"], quote=True)}">Download HUD</a></p></article>')
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PlxNative HUD registry</title><style>body{max-width:1100px;margin:40px auto;padding:20px;background:#111;color:#eee;font:18px/1.5 system-ui}img{width:100%;height:auto;margin-top:16px}a{color:#9cf}select{margin-left:8px;padding:8px;max-width:100%;background:#222;color:#eee;border:1px solid #777}article{margin:40px 0}</style><h1>PlxNative HUD registry</h1><p>Reviewed, declarative player HUD packages.</p>' + ''.join(cards) + '<p><a href="CREDITS.md">Preview media credits</a> · <a href="index.json">Catalog JSON</a></p></html>'
    (output / "index.html").write_text(page, encoding="utf-8")
    return index
