# PR12 acceptance record

This registry remains private before release. Test publication is authorized by the owner.
The app implementation landed in [plx-native PR #1206](https://github.com/GLinnik21/plx-native/pull/1206)
as squash `f1436ba4746c477537144276ff928840f0be7566`.

Completion requires evidence for every item below, not merely a green Python suite:

- [x] App publishes a relocatable Linux simulator bundle with source SHA, app version, fonts,
  native host libraries, schema, fixture corpus and the existing mock/screenshot machinery.
- [x] Registry pins immutable simulator bundles by SHA-256 and chooses the oldest compatible
  app version for each package. A new app release cannot silently replace an older pin.
- [x] Submission CI uses the app's lint in all shipped languages, compares the generated schema
  against the mirror, and checks schema/parser agreement on the fixture corpus.
- [ ] Linux/Xvfb previews cover transport states, episode navigation, Up Next, both Skip kinds,
  every allowed section combination, both player menus at every authored opener, failure,
  long server text in every shipped language, largest/highest captions, bright/dark backgrounds.
  Changed packages include a comparison against the previous version's previews.
- [ ] Publisher emits a deterministic index, original package bytes at content-addressed URLs,
  preview URLs and hashes, and revocation reasons. Every published hash is checked.
- [ ] GitHub Pages publication is exercised end-to-end; disabling publication still produces
  the same verifiable catalog artifact for private staging.
- [ ] Authoring kit includes AGENTS.md, llms.txt, AUTHORING.md, examples, schema and lint guidance.
  An authoring exercise succeeds using only the kit, schema, example and at most two lint runs.
- [ ] An app release sends repository_dispatch; weekly re-lint is the fallback. Compatibility
  data records per-language unfit results, caps app.max after total failure, and files a deduplicated
  author issue. These branches are exercised using a deliberately incompatible test release.
- [x] Simulator/TV text-width corpus is measured at every supported rung in all languages.
  The measured per-rung margin is enforced only by registry CI, without weakening TV fit checks.
- [ ] A seeded PR containing Reference and Minimal passes actual CI and produces inspected previews.
- [ ] App gates, before/after build-bench, review, and squash landing complete; registry also
  uses a reviewed, green PR. No real Plex account is used for verification.

Gallery UI, index signatures, a live authoring server and cargo-fuzz are PR13-PR16, respectively.

## Implementation checkpoints

- App PR #1206 passed all 21 reported CI checks (20 passed, one expected skip) and squash-landed.
  Published developer simulator run [41473507619](https://github.com/GLinnik21/plx-native/actions/runs/41473507619)
  passed; the bootstrap pin binds its 38,910,181-byte archive, source, manifest and 273 files.
  It is explicitly a prerelease developer utility, not a stable television app release.
- Registry unit suite: 28 tests pass, including preserved package bytes, deterministic publication,
  revocation, oldest-compatible selection, immutable pins/manifest tamper checks, measured per-rung
  calibration, future-format filtering, changed-translation release acceptance, renderer mismatch refusal, language regressions,
  non-text regressions, recovery and deduplicated author issues.
- The bootstrap pin and its source-bound calibration are populated from the published artifact.
  Its 12,276-row corpus compares directly with the real TV report and yields the same 4–9 px margins.
- Real macOS iterations have produced native menu, paused, seeking, Up Next, Skip Intro/Credits and
  bright-footage artifacts. These are iteration evidence; the acceptance matrix remains Linux/Xvfb.

## Native calibration and integration evidence

- Real TV collection completed on app source `9266c34e7`, with the TV lock, synthetic guest/mock,
  panel on and sound muted. Deployment verified 47 files; the atomic diagnostic wrote 12,276 rows.
  The TV lock and owned mock/tunnel were released and the temporary private header removed.
- Linux artifact CI runs `41461558740` (`60410e182`) and `41463540976` (`a43f214b4`) passed native
  library load and relocation checks. The first archive's 273 manifest-bound files were independently
  hash-verified; its real corpus matches the TV's fonts and text coverage. Calibration evidence is in
  `calibration/`, with per-rung margins of 4–9 px and zero added margin on normal TV admission.
- Seeded [registry PR #1](https://github.com/GLinnik21/plxnative-huds/pull/1), Linux run
  [41476101187](https://github.com/GLinnik21/plxnative-huds/actions/runs/41476101187): validation
  passed, both HUDs had zero findings in all eleven languages, all 17 schema/parser fixtures
  agreed, and the authoring exercise passed in two lint runs. Minimal's complete 32-state native
  matrix passed and was visually inspected; all PNG dimensions/hashes were independently checked.
  Reference's larger matrix and final catalog staging are still running.
- The app's public schema URL returned HTTP 404 during the final authoring audit: the tracked
  `site/hud/` files were not copied by its Pages workflow. Follow-up branch
  `fix/hud-authoring-publication` fixes that delivery gap and updates stale verification notes.
- Repository visibility and GitHub's combined Actions create/approve-PR setting remain unchanged
  pending owner approval. Pages is explicitly opt-in; private pushes retain the catalog artifact.
- Deliberately incompatible protocol-fixture app releases exercise archive/manifest verification,
  real child-process lint reports, release acceptance/idempotence, per-language `unfit`, author
  notification dispatch, total-failure `app.max`, recovery and unchanged original package bytes.
  These fixtures are isolated unit-test executables, never published app releases.
- App exact-tree gates passed on final head `bed1807376282c79b07d8fac2f76d9e99aeec0c3`:
  `make check`, `make check-nodef`, and real ARM build. The stable-tag provenance review finding
  has a failing-then-passing regression. The companion registry review returned no findings at
  `b682a39`; final combined-diff review found one future-format filtering bug, fixed with an observed failing-then-passing regression.

| App build-bench case | Before | After |
|---|---:|---:|
| No-op | 0.2 s | 0.2 s |
| Leaf edit | 30.4 s | 40.8 s |
| Hub edit | 16.9 s | 28.3 s |
| Host tests | 58.1 s | 60.4 s |
| ARM benchmark | skipped, no archive | skipped, no archive |

Before source `f2449cc55`; after source `60410e182` contains all final Rust changes (later edits
were Python/workflow-only). After-run machine load was 12.46–12.85 on ten cores: noisy timings,
not evidence of a performance regression. The rebuilt sets stayed 27/169 leaf and 7/169 hub.
Tests were 11,501 passed before and 11,506 after, zero failures, 99 ignored in both benchmark runs.
The separate final ARM link passed; it is not an ARM timing measurement.
