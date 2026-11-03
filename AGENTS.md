# Player HUD registry

Read `AUTHORING.md`, both generated schemas under `schema/manifest/` and `schema/hud/`, and an
example source directory. A submission is `huds/<reverse-DNS id>/manifest.json`, `hud.json`, declared
SVG resources and notices, plus a source-only README with license and contact information.
The native SDK packs that directory into one `.plxhud` archive. Preserve authored JSON member
order because state-keyed conditions use it. `catalog.canonical` is for registry reports and indexes.

Use the app-owned commands, labels, menus, focus, captions, theme and type rungs.
Run `python3 scripts/validate.py` for native packaging, stock-schema agreement and all-language lint.
Every finding requires correction. The oldest compatible pinned SDK must support both the package
and HUD format, and its schemas, limits, source and binary must agree with its immutable artifact.
Keep the SDK fixture corpus and measured text calibration authoritative.

Validation writes exact archives and their provenance to `out/packages/`. Render with
`xvfb-run -a python3 scripts/previews.py` and inspect every state. Render and publication consume
that same snapshot. Release rechecks download the published archives. The native Rust packer is
the production archive writer.

Package and HUD formats independently begin at 1.0. Seed plugin versions begin at 1.0.0.
After the initial bundle baseline, changed published bytes require a newer plugin version.
Preserve full-archive hashes through install, lint, previews, publication and revocation.
Generated previews, SDK caches and packed archives stay ignored.

Automation and schema-mirror changes require maintainer review. Import schema mirrors from the
real pinned SDK output. Keep native acceptance evidence pending until those commands and captures
have run. Protocol-fixture tests establish transport behavior only.
Never read or publish developer credentials or real Plex data. Synthetic mocks are mandatory.
