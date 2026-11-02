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
