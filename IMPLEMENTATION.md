# PR12 acceptance record

This registry remains private before release. Test publication is authorized by the owner.
The app implementation is developed separately on `feat/hud-registry-pr12` in `plx-native`.

Completion requires evidence for every item below, not merely a green Python suite:

- [ ] App publishes a relocatable Linux simulator bundle with source SHA, app version, fonts,
  native host libraries, schema, fixture corpus and the existing mock/screenshot machinery.
- [ ] Registry pins immutable simulator bundles by SHA-256 and chooses the oldest compatible
  app version for each package. A new app release cannot silently replace an older pin.
- [ ] Submission CI uses the app's lint in all shipped languages, compares the generated schema
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
- [ ] Simulator/TV text-width corpus is measured at every supported rung in all languages.
  The measured per-rung margin is enforced only by registry CI, without weakening TV fit checks.
- [ ] A seeded PR containing Reference and Minimal passes actual CI and produces inspected previews.
- [ ] App gates, before/after build-bench, review, and squash landing complete; registry also
  uses a reviewed, green PR. No real Plex account is used for verification.

Gallery UI, index signatures, a live authoring server and cargo-fuzz are PR13-PR16, respectively.

## Implementation checkpoints

- App instrument/bundle implementation: `plx-native` branch `feat/hud-registry-pr12`, commits
  `39f1dffd5` and `60410e182`. Before benchmark recorded; final gates/after benchmark pending.
- Registry unit suite: 19 tests pass, including preserved package bytes, deterministic publication,
  revocation, oldest-compatible selection, immutable pins/manifest tamper checks, measured per-rung
  calibration, language regressions, non-text regressions, recovery and deduplicated author issues.
- The simulator pin list intentionally remains empty until the actual Linux artifact and matching
  TV measurements exist. An empty list fails validation; no placeholder pin can produce a green CI.
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
- Stock Draft 2020-12/schema/parser agreement passed over all 17 app corpus packages in a real
  local simulator iteration. Both seeded HUDs also returned zero findings with measured headroom
  in that iteration. These do not replace the canonical Linux seeded-PR checks still pending.
- Deliberately incompatible protocol-fixture app releases exercise archive/manifest verification,
  real child-process lint reports, release acceptance/idempotence, per-language `unfit`, author
  notification dispatch, total-failure `app.max`, recovery and unchanged original package bytes.
  These fixtures are isolated unit-test executables, never published app releases.
- App exact-tree gates passed on `9266c34e7`: `make check`, `make check-nodef`, and real ARM build.
  A later Python-only stable-tag provenance review fix has its own failing-then-passing regression
  and is receiving the final gate before squash landing. The companion registry review returned
  no findings at `b682a39`.
