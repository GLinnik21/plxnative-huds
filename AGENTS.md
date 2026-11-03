# Player HUD registry

Read `AUTHORING.md` and `schema/1.0.json`. Start with an example, not an invented vocabulary.
Packages are data: one `huds/<reverse-DNS id>/hud.plxhud.json` and a README with license/contact.
Do not translate or replace app-owned labels, implement playback, or add focus/key routing.
Use the shared native commands, menus, sections, theme and type rungs defined by the format.

Run `python3 scripts/validate.py`; all shipped languages and all findings are required.
Use the oldest compatible pinned simulator. Never suppress a finding, weaken the fixture corpus,
change a calibration or move an immutable release pin to make a package pass.
Render with `xvfb-run -a python3 scripts/previews.py` and inspect every generated state.
Bump the HUD version for changed bytes. Do not commit generated previews or caches.

Preserve the original JSON bytes in publication. Revocations name a SHA-256 and reason.
Automation and schema-mirror changes require maintainer review; they are not a HUD submission.
Never read or publish developer credentials or real Plex data. Synthetic mocks are mandatory.
