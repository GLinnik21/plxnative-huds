# Author a Player HUD

A HUD is an editable directory distributed as a `.plxhud` bundle. It controls player layout and
appearance through PlxNative's shared widgets. Playback, translated app labels, focus, captions
and native menus are app-owned.

## Source layout

```text
huds/com.yourname.yourhud/
  manifest.json
  hud.json
  assets/gear.svg
  licenses/attribution.txt
  README.md
```

The manifest owns `package_format`, `id`, `version`, `name`, `author`, `license`, optional app
release bounds, and `hud` with its own `format` and `entry`. Both initial format versions are
`"1.0"`. The plugin's initial release is `"1.0.0"`. `resources` maps logical IDs to relative files,
and optional `notices` lists attribution text files. The HUD document owns `layout` and optional
`palette`. Each document can carry its matching `$schema` URL.

Reference an SVG resource by its logical ID from an icon or control face. Every resource must
have a valid use and pass the native SVG-mask validator. SVGs remain white masks tinted by the
HUD's inks. Keep each mask within 16 KiB and eight paths. Native packaging includes the manifest,
HUD entry, resource files and declared notices. README and other authoring files stay in the source
repository. The packer retains payload bytes and JSON member order exactly.

Use lower-case portable paths such as `assets/gear.svg`. Path segments contain letters, digits,
underscores, hyphens and dots, start with a letter or digit and end with a non-dot character.
The package rejects symlinks, parent traversal, device names, aliases and unlisted archive members.
The SDK advertises the complete versioned limits, including the initial 2 MiB artifact limit,
1 MiB combined member limit, 64 KiB manifest limit and 128-member limit.

## Author and validate

1. Copy `examples/minimal/` to `huds/com.yourname.yourhud/`.
2. Edit the manifest identity, display name, author and SPDX license. Match the ID to the
   directory, add a README with attribution/contact, and register a GitHub contact in
   `maintainers.json` for compatibility notifications.
3. Use the manifest and HUD schema mirrors for editor completion. Follow the public format
   guide and the examples' shared theme and type rungs. [Format guide](https://github.com/GLinnik21/plx-native/blob/main/docs/hud-plugins.md)
4. On Ubuntu 24.04 x86_64, including a Linux VM or WSL, install Python 3.12 and the pinned
   `requirements.txt` in a virtual environment. Run `python3 scripts/validate.py`.
5. Correct every native finding, including `HUD-W0602`. Findings identify a package member in
   `file` and its RFC 6901 JSON pointer in `path`, followed by language, state and measured room
   when relevant. Archive-level findings have a null `file`. A complete archive's SHA-256 is
   included in the report. Early source failures have a null digest.
6. Install Mesa, Xvfb, ffmpeg and Pillow. Run `xvfb-run -a python3 scripts/previews.py` and inspect
   every image under `out/previews/<package hash>/`. The matrix covers transport states, sections,
   every menu opener, long titles in all languages, failure, large captions and bright/dark scenes.
7. Submit the source directory and README. CI retains the built archives, lint reports, full
   previews and visual differences. Following the initial bundle baseline, increment the plugin
   version whenever its published archive bytes change.

The registry uses its original AI-generated coast, painted village and rain-lit city for every
preview frame, chapter thumbnail and information image. The pinned SDK still supplies the native
HUD and complete state matrix. Preview provenance binds the source images and fixture recipe;
old film-based renders cannot be reused. Each gallery scene also has equivalent native frames on all three backgrounds for automatic preview cycling; the HUD state and metadata stay fixed. Generation prompts are in `assets/preview-scenes/scenes.json`.


Validation selects the oldest pinned SDK that supports the manifest's package/HUD version pair
and app bounds. It invokes the native packer once per source and writes the exact archive and
provenance to `out/packages/`. Rendering and publishing consume that snapshot. Run validation
again after editing source files to build a new snapshot.

For direct native tools, `--hud-pack DIR --out FILE --format json` emits the distributable and
its report. `--hud-lint DIR_OR_FILE --format json --lang all` and `--hud-inspect DIR_OR_FILE` use
the same loader. `--hud-export builtin:classic --out FILE` exports the embedded bundle. Ordinary
ZIP tools can open the bundle for editing, and the native packer rebuilds its deterministic
STORE-only distribution. `--hud-schema manifest|hud --version 1.0` emits each schema.

## Fit and schema checks

`HUD-E0601` identifies app text that exceeds its room. Increase the containing width or adjust
the layout. `HUD-W0602` identifies insufficient measured TV headroom on the simulator. `HUD-E0603`
identifies a control below the supported size. The other findings cover geometry, safe area,
focus travel, menu clearance and rendering cost. Fixed app labels must fit in every language.
Server-provided titles can use the format's elision behavior.

Both schema mirrors come from the native SDK descriptor tables. CI compares stock Draft 2020-12
validation with the SDK's hash-bound corpus using `(file, path)`, including document failures
and a separate set of malformed archives. The native compiler enforces duplicate keys,
resource resolution, reachability, geometry and rendering costs.

## Compatibility and publication

Optional `app.min` and `app.max` are exact X.Y.Z app releases. SDK pins bind source, archive,
manifest, supported version pairs, schemas and limits. Published stable SDK pins are immutable.
Development pins can advance to newly published, source-bound development artifacts.

Release dispatches and the weekly backstop enumerate the published catalog and re-lint its exact
`.plxhud` bytes. Each published entry and preview proof retain the original SDK pin. That SDK
authenticates the archive and its authored metadata before later SDKs evaluate compatibility.
Source edits and removals can proceed while a published version is still being checked.
The checks record per-language `unfit` transitions and deduplicated author issues. Total or non-text
failures cap the catalog at the last passing app, and later successful releases restore compatibility.
Authored app bounds come from the archive, so catalog compatibility ceilings allow future rechecks.
The TV retains its own fit and cost checks when selecting a package.

Publication writes `index.json`, `p/<sha256>.plxhud`, hashed previews and revocation reasons.
Main deploys when `PUBLISH_PAGES` is true. Manual publication is explicit. With publication disabled,
CI retains the same verified catalog artifact.

Future package minors can raise transport/member limits or add compression. Future HUD minors
can add bitmap, font and plugin-localization semantics with their own decode and rendering budgets.
Each declared profile keeps its own limits. SVG bundles use the app's existing fonts and labels.

## Authoring exercise

The automated exercise uses this guide's public starter and both schemas. It edits identity,
introduces one invalid HUD key, checks the native `file` and `path`, corrects that key and runs the
native lint again. Its report retains both iterations and the exact SDK source. Bundle acceptance
is recorded in `IMPLEMENTATION.md` after the new native SDK and full captures are available.
