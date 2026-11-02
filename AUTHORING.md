# Author a Player HUD

A HUD is one declarative UTF-8 JSON file. It changes player layout and appearance. Playback,
translated app labels, focus, captions and native menus remain owned by PlxNative.

1. Copy `examples/minimal.plxhud.json` to `huds/com.yourname.yourhud/hud.plxhud.json`.
2. Set a unique reverse-DNS `id`, a descriptive `name`, `author`, SPDX `license` and `version`.
   The ID must match the directory. Add a README with attribution and your GitHub contact,
   and register that contact in `maintainers.json` for compatibility notifications.
3. Read the pinned [format guide](https://github.com/GLinnik21/plx-native/blob/main/docs/hud-plugins.md)
   and use `schema/1.0.json` for editor completion. Follow the examples' theme and size rungs.
4. On Ubuntu 24.04 x86_64 (including a Linux VM or WSL), install Python 3.12 and
   `python3 -m pip install -r requirements.txt` in a virtual environment.
   Run `python3 scripts/validate.py`. It downloads the hash-pinned Linux simulator, chooses the
   oldest compatible app for each package, and lints **every shipped language**. No Rust build is needed.
5. Address every finding, including `HUD-W0602`. A warning about text headroom fails registry CI.
   A finding includes a JSON pointer, language, state and measured room; fix the indicated layout
   instead of shortening translated app labels. Server titles may elide. Fixed app text must fit.
6. On Ubuntu 24.04 with Mesa, Xvfb, ffmpeg and Pillow installed, run
   `xvfb-run -a python3 scripts/previews.py` (use `venv --system-site-packages` when Pillow comes from apt). Inspect `out/previews/<package hash>/`.
   The matrix includes transport states, episode navigation, section combinations, every menu
   opener, long titles in all languages, failure, large/high captions and bright/dark scenes.
   CI allows 90 minutes per full matrix; an individual scene still fails if it cannot settle
   within 180 seconds. A changed package may render both its preceding and current versions.
7. Submit a PR with the package and README. CI records the lint, previews and visual differences
   from the preceding version. Increment `version` whenever the package bytes change.

Do not submit executable scripts, local credentials, Plex data or screenshots of your own library.
CI renders the openly licensed synthetic demo library. Packages have no network access or code.
The registry accepts files as data; automation changes receive a separate maintainer review.

## Reading findings

- `HUD-E0601`: app text exceeds its room. Increase the containing width or change the layout.
- `HUD-W0602`: it fits on Linux but has insufficient **measured per-size TV headroom**. Increase room.
- `HUD-E0603`: a control is smaller than the supported minimum.
- Other findings cover geometry, safe area, focus travel, menu clearance and rendering cost.
  Follow the report's explanation and hint; do not remove a required command to suppress a finding.

`schema/1.0.json` is a mirror of the app's generated schema. Stock Draft 2020-12 validation is
checked against the pinned app's fixture corpus in CI. The app compiler remains authoritative
for duplicate keys, reachability, focus and geometric invariants that JSON Schema cannot express.

## Compatibility and publication

Optional `app.min`/`app.max` are exact X.Y.Z app-release bounds. Pins identify the exact app
source and archive/manifest hashes. A development simulator is explicitly labelled until the
first supporting app release; it never claims that an older shipped app supports the format.
Stable pins are immutable. CI does not silently update the validator to the newest app.

A release dispatch and the weekly backstop re-lint unchanged HUDs. A language regression creates
an `unfit` transition and a deduplicated author issue with its lint report. An all-language or
non-text failure caps the catalog at the last passing app. These catalog projections preserve
the author's original bytes and content hash; an installed HUD still compiles locally on its TV.

Publication writes `index.json`, `p/<sha256>.plxhud.json`, hashed preview URLs and revocation
reasons. The repository can remain private during staging. Enabling Pages can expose its output
even while the repository is private, depending on the account plan. Main deploys only when the
repository variable `PUBLISH_PAGES` is `true`; a manual run can explicitly request publication.
With publication disabled, the same byte-verified catalog remains available as a CI artifact.

## Authoring exercise

Start with only this guide, `schema/1.0.json` and `examples/minimal.plxhud.json`. Change the ID,
name, author and accent; create the README; run the lint. Correct the reported pointers and run
it once more. The seed exercise in CI must pass within two iterations without private context.
