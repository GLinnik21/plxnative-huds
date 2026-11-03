# Bundle 1.0 acceptance

The initial bundle contract separates manifest and HUD documents, both at version 1.0, and keeps
seed plugin releases at 1.0.0. The registry implementation uses native-built `.plxhud` snapshots
through validation, rendering and publication. Release rechecks consume published archive bytes.

The published bundle SDK, native-emitted schema mirrors and source-bound calibration are imported.
Registry-native lint, authoring, capture and publication acceptance remain pending the Ubuntu CI run.
Python protocol fixtures exercise pipeline behavior with explicitly synthetic executables and data.

- [x] Verify the SDK archive, manifest and file inventory, import both native-emitted schemas, and
  derive the current host profile from the existing measured TV corpus.
- [ ] Confirm the pin/bundle/binary contract through the registry's native SDK runner.
- [ ] Pass the indexed native document/archive corpus and all-language package lint.
- [ ] Record the two native authoring iterations with member and JSON-pointer findings.
- [ ] Render and inspect the complete Reference and Minimal matrices and normal before/after differences.
- [ ] Publish identical validated archive bytes and verify every download and preview hash.
- [ ] Complete the release-dispatch/recheck path with the new SDK and exact published archives.

## Bundle SDK import

The source-pinned developer SDK was published from
`017ff3ad29443e5ecf47e7c3d3b93f4625cf5c2c` under utility tag
`hud-simulator-017ff3ad29443e5ecf47e7c3d3b93f4625cf5c2c`.
The registry import verified its 39,127,843-byte archive, manifest and all 307 listed files through
the existing `acquire` and `verify_bundle` helpers. [App SDK CI](https://github.com/GLinnik21/plx-native/actions/runs/41664064627)

| Artifact | SHA-256 |
|---|---|
| SDK archive | `2636ee4f63a5cf2c5f1701ff5cb4af5e2a84abb80179e674da978587893167af` |
| SDK manifest | `913f76629c24bbf27346b70deda1a9b24c1dc8a79366128e022abf5b46f407d3` |
| Native manifest schema | `8782727f4fe4c029edb29201a522e693d636016883ff167e5a8ad9cfe419e9e9` |
| Native HUD schema | `cff1151a179dc8b271c007f35de34ed1aa13cbf6a5df33757c0034c357130868` |
| Linux text report | `97b33421b7e99e72e2c3b1db372203742a6d80e8f53b00beb80846f1797807ae` |
| Existing TV text report | `dc2e1f388421d0a4eab49ab97ffc4dbd08ef252f4cdfa02eb5f94bdbe394d3fe` |

`release_profile` compared all 12,276 rows directly with TV source `9266c34e7`, including every
language, type rung and weight. Font identities, corpus coverage and text/type sizes matched.
The new source-bound profile reproduces the measured 4–9 px per-rung margins. Its host report is
retained byte for byte, and the profile binds both report hashes and the SDK's renderer identities.

Both schema files were copied byte for byte from the verified SDK inventory. Stock Draft 2020-12
checks passed for all 16 registry/example source documents. The SDK contains 22 native corpus
cases, including four malformed archives. Execution of that corpus and the complete Reference and
Minimal capture matrices is the pending registry-native CI gate.

The SDK reports the seven-character source abbreviation `017ff3a`. A regression first exposed the
registry wrapper's overly strict nine-character minimum. The wrapper accepts the native abbreviation
and checks it against the full pinned source SHA, while archive, manifest and binary hashes remain
part of SDK verification.

## Earlier developer-tool acceptance record

The following evidence describes the preceding inline-JSON developer tools and their actual
runs. Bundle acceptance is tracked above.

## PR12 acceptance record

The owner made this registry public and enabled Actions to create compatibility pull requests.
Repository token defaults remain read-only; write permissions are limited to the relevant jobs.
The app implementation landed in [plx-native PR #1206](https://github.com/GLinnik21/plx-native/pull/1206)
as squash `f1436ba4746c477537144276ff928840f0be7566`.

Completion requires evidence for every item below, not merely a green Python suite:

- [x] App publishes a relocatable Linux simulator bundle with source SHA, app version, fonts,
  native host libraries, schema, fixture corpus and the existing mock/screenshot machinery.
- [x] Registry pins immutable simulator bundles by SHA-256 and chooses the oldest compatible
  app version for each package. A new app release cannot silently replace an older pin.
- [x] Submission CI uses the app's lint in all shipped languages, compares the generated schema
  against the mirror, and checks schema/parser agreement on the fixture corpus.
- [x] Linux/Xvfb previews cover transport states, episode navigation, Up Next, both Skip kinds,
  every allowed section combination, both player menus at every authored opener, failure,
  long server text in every shipped language, largest/highest captions, bright/dark backgrounds.
  Changed packages include a comparison against the previous version's previews.
- [x] Publisher emits a deterministic index, original package bytes at content-addressed URLs,
  preview URLs and hashes, and revocation reasons. Every published hash is checked.
- [x] GitHub Pages publication is exercised end-to-end; disabling publication still produces
  the same verifiable catalog artifact for private staging.
- [x] Authoring kit includes AGENTS.md, llms.txt, AUTHORING.md, examples, schema and lint guidance.
  An authoring exercise succeeds using only the kit, schema, example and at most two lint runs.
- [x] The app release workflow sends repository_dispatch; weekly re-lint is the fallback. Compatibility
  data records per-language unfit results, caps app.max after total failure, and files a deduplicated
  author issue. These branches are exercised using a deliberately incompatible test release.
- [x] Simulator/TV text-width corpus is measured at every supported rung in all languages.
  The measured per-rung margin is enforced only by registry CI, without weakening TV fit checks.
- [x] A seeded PR containing Reference and Minimal passes actual CI and produces inspected previews.
- [x] App gates, before/after build-bench, review, and squash landing complete; registry also
  uses a reviewed, green PR. No real Plex account is used for verification.

Gallery UI, index signatures, a live authoring server and cargo-fuzz are PR13-PR16, respectively.

## Corrected native acceptance and registry landing

- [Run 41517403918](https://github.com/GLinnik21/plxnative-huds/actions/runs/41517403918)
  passed validation, 70 Reference states, 32 Minimal states and catalog staging on reviewed registry
  head `a4483fa3f92c86ea27ffdc82303b16298500ce7b`. Every capture binds the corrected app source
  `3bc30f4edd3b392724968f9945dbef002cd646f2`, is native 1920×1080, and passed its SHA-256 check.
  Compared with the fully inspected chapter-corrected baseline, 101 PNGs are byte-identical.
  The only changed capture is Reference's Belarusian long title; visual inspection confirms the
  replacement glyph is gone. The title's existing 128-byte capacity remains unchanged.
- Two independent catalog generations matched all 87 staged files byte for byte. Original HUD
  JSON bytes are preserved. The staged index SHA-256 is
  `82d63c40d619a3abdf7bc3284293a3ae22c9d631a33a613e25eba740020cc4b9`.
- All 28 registry tests passed on the exact clean reviewed head. Combined implementation and
  prose review found no remaining issues. [PR #1](https://github.com/GLinnik21/plxnative-huds/pull/1)
  squash-landed as `2ab53fe2ff4678e455f971f7a611b8c6a6195f91` after its four CI jobs passed;
  publication was intentionally skipped on the submission PR. The first main publication is
  [run 41567297415](https://github.com/GLinnik21/plxnative-huds/actions/runs/41567297415),
  which passed all five jobs including deployment.
- Production readback fetched all 87 files (91,949,606 bytes) from
  [GitHub Pages](https://glinnik21.github.io/plxnative-huds/) and matched the staged artifact
  byte for byte, including both original package downloads, preview manifests and all PNG hashes.
  The deployed index SHA-256 is
  `b604f5495c6c713139251de6536dec43bf7bd998f117cad2f7a37522c1f053bb`;
  an `If-None-Match` read of its ETag returned HTTP 304.
- Production Reference's 70 captures are byte-identical to the inspected corrected baseline.
  Minimal has 31 identical captures; Up Next differs in 133 button-area pixels by at most one
  channel level. Both full-size images were inspected: placement, labels and footage agree.
  All 102 production PNGs pass native dimensions and SHA-256 checks. Production validation again
  passed 17 schema/parser fixtures per HUD, all eleven languages, and the two-iteration exercise.

## Release-notification integration

- Post-landing app [probe 41567314247](https://github.com/GLinnik21/plx-native/actions/runs/41567314247)
  succeeded through the configured dispatch secret without building or publishing an app release.
  It triggered registry [receiver 41567344597](https://github.com/GLinnik21/plxnative-huds/actions/runs/41567344597),
  which completed discovery and native all-language re-linting and opened
  [compatibility PR #2](https://github.com/GLinnik21/plxnative-huds/pull/2).
  The projection contains exactly the two original package hashes, no findings, no unfit
  languages and no compatibility ceilings. Its package bytes and immutable simulator pin are unchanged.
  [Gate 41567368097](https://github.com/GLinnik21/plxnative-huds/actions/runs/41567368097)
  passed validation, both complete before/current preview checks and staging; publication was
  intentionally skipped on the PR. The logs confirm verified public-proof reuse for both HUDs.
  Reviewed head `02a0ec23488c0a5790ff1f7423c14e4295eb38bc` squash-landed as
  `12c56a93c5a7ea7cfd7419c407012151b35b5fb6`.
- The real stable-release workflow uses the same dispatch sender after attaching its immutable SDK.
  The first actual stable app release carrying that SDK remains a future observation; the probe
  verifies transport and receiver wiring without inventing a stable release. The weekly schedule
  and manual backstop use the same discovery/re-lint path. A post-merge manual backstop,
  [run 41571212731](https://github.com/GLinnik21/plxnative-huds/actions/runs/41571212731),
  passed and reported `No compatibility changes`, without opening a duplicate PR.
- Deliberately incompatible release protocol fixtures test the production archive, manifest,
  calibration, subprocess lint, compatibility projection and notification paths. They verify a
  German-only failure, deduplicated notification, total/non-text failure ceiling, immutable old
  pins, later recovery and unchanged package bytes. These are isolated executable test releases;
  they make no native-rendering or live GitHub-issue claim.

## Implementation checkpoints

- App PR #1206 passed all 21 reported CI checks (20 passed, one expected skip) and squash-landed.
  Follow-ups #1209 and #1212 also landed. The active developer simulator was published by run
  [41515162200](https://github.com/GLinnik21/plx-native/actions/runs/41515162200). Its bootstrap
  pin binds the 38,938,002-byte archive, source `3bc30f4edd3b392724968f9945dbef002cd646f2`,
  manifest and 273 files. It includes the actual long-chapter fixture and UTF-8 truncation fixes.
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
  Reference's complete 70-state matrix and catalog staging also passed. All 102 images were
  inspected and hash/dimension checked. Two independent publications matched all 87 catalog
  files byte for byte (index SHA-256 `c5b73c788f70622b009333f085ef953726bb6a4ae882875cb4b2d4aeaa4ebe4e`).
  Inspection exposed that long-chapter scenes wrote PMS `title` instead of `tag`; a failing-then-
  passing regression fixes it in app follow-up `a50307d32`. The corrected bundle required a new pin
  and complete recapture; the corrected native acceptance record above closes those requirements.
  That corrected bundle was published and independently hash-verified; its bundled `hud_preview.py`
  matches the reviewed chapter correction byte for byte. Corrected run
  [41489989922](https://github.com/GLinnik21/plxnative-huds/actions/runs/41489989922) passed
  validation and Minimal's 32-state matrix (all 32 PNGs byte-identical to the first run).
  Reference saved 69 of 70 checked PNG/log pairs, including ten corrected long-chapter languages,
  before the registry's 3,600-second whole-process timeout interrupted the Dutch capture. The
  partial images and terminal log are preserved; they are not accepted as a complete matrix.
  The retry allows 90 minutes for each full matrix and 210 minutes for a previous/current job,
  while preserving the app tool's 180-second per-scene settle guard and full state coverage.
  Unbuffered Python progress makes completed scene names visible during the job.
  Retry [41501332421](https://github.com/GLinnik21/plxnative-huds/actions/runs/41501332421)
  passed validation, all 70 Reference and 32 Minimal captures, and catalog staging. Every PNG
  hash/native dimension was checked; 91 images matched the previously inspected baseline and
  all eleven changed long-chapter captures were inspected. Two independent publications matched
  all 87 staged files; index SHA-256 is
  `498f18adc36ad341bf9866db7e5e833134d560305728e5ea4f7226aadc9fcd39`.
  Inspection found a replacement glyph in the Belarusian main title: its 137 UTF-8 bytes were
  cut at byte 127 inside a character by the player's fixed title buffer. App
  [PR #1212](https://github.com/GLinnik21/plx-native/pull/1212) fixes both shared text writers to
  preserve character boundaries while leaving raw byte-key prefixes intact. The regression
  failed before the fix and passed afterwards. Exact clean commit `c63ecab29d945f16811ae5f93067f28b0ab19856`
  passed host checks, shipping-feature checks, ARM build and combined-diff/prose review. It
  squash-landed as `3bc30f4edd3b392724968f9945dbef002cd646f2` through the landing tool, with
  all 19 GitHub checks passing. The current pin includes this fix; its 12,276 metric rows and
  font hashes are identical to the preceding SDK, and its source-bound profile again measures
  directly against TV evidence. The complete corrected native run above closes that rerun requirement.
- The app's public schema URL returned HTTP 404 during the final authoring audit: the tracked
  `site/hud/` files were not copied by its Pages workflow. Follow-up branch
  `fix/hud-authoring-publication` (`a50307d32`) fixes that delivery gap and updates stale
  verification notes. It passed `make check` and `make check-nodef` on a clean committed tree,
  17 toolkit tests, 80 workflow checks, before/after build-bench and a no-findings review. It also
  adds a manual scoped-secret probe without publishing an app release. App [PR #1209](https://github.com/GLinnik21/plx-native/pull/1209)
  squash-merged as `1c9a75db47dfbfddffdae133684698507be263cf` (owner merge observed while the
  landing gate waited; the reviewed head's checks passed). App Pages run
  [41487108486](https://github.com/GLinnik21/plx-native/actions/runs/41487108486) deployed it;
  all 27 authoring URLs were independently fetched from `https://plxnative.com/hud/` and matched
  source bytes. Corrected toolkit publication run
  [41487654770](https://github.com/GLinnik21/plx-native/actions/runs/41487654770) succeeded; its
  source-bound profile again measures 12,276 rows directly against TV evidence with 4–9 px margins.
- The owner-added dispatch credential passed app probe
  [41510758423](https://github.com/GLinnik21/plx-native/actions/runs/41510758423): the actual app
  workflow sent `app-release-probe` successfully. This verifies credential/API acceptance;
  this first probe preceded registry landing. The post-landing receiver result is recorded above.
- The owner configured public visibility and GitHub's combined Actions create/approve-PR setting.
  Pages is enabled with Actions builds and `PUBLISH_PAGES=true`; artifact staging remains available
  when publication is disabled. The automation creates review PRs and never approves or merges them.
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

Before source `f2449cc55`; after source `60410e182` covers the core PR #1206 Rust implementation.
Follow-up #1209 changed Python/workflows; #1212 fixes the shared UTF-8 buffer helper and does not
change the build graph. Those follow-ups have separate gates; this table does not measure them.
After-run machine load was 12.46–12.85 on ten cores: noisy timings,
not evidence of a performance regression. The rebuilt sets stayed 27/169 leaf and 7/169 hub.
Tests were 11,501 passed before and 11,506 after, zero failures, 99 ignored in both benchmark runs.
The separate final ARM link passed; it is not an ARM timing measurement.
