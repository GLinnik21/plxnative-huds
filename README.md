# PlxNative Player HUD registry

Declarative player layouts for [PlxNative](https://github.com/GLinnik21/plx-native).
A source directory becomes one deterministic `.plxhud` bundle through the native SDK.
Start with [AUTHORING.md](AUTHORING.md), [the manifest schema](schema/manifest/1.0.json), [the HUD schema](schema/hud/1.0.json) and an [example](examples/).

Reference and Minimal seed the registry. Validation uses the app's exact compiler, all shipped
languages and the oldest compatible hash-pinned Ubuntu 24.04 x86_64 simulator. CI renders native state previews,
checks exact native-built archive hashes and prepares a Pages catalog with revocation and compatibility data.

The source-pinned bundle SDK, native-emitted schemas and measured calibration profile are imported.
The complete registry-native lint, authoring and preview acceptance run remains pending.

The registry is public. `IMPLEMENTATION.md` records acceptance evidence. Main deploys the verified
catalog to [GitHub Pages](https://glinnik21.github.io/plxnative-huds/) with the repository variable
`PUBLISH_PAGES=true`. Pushes also retain the catalog as a CI artifact. Disabling that variable
keeps artifact staging available; a manual workflow dispatch with `publish=true` deploys explicitly.

The app workflow can send an `app-release-probe` after the dispatch secret is configured. This
runs the same registry discovery/re-lint backstop without accepting a synthetic app-release pin.
GitHub's combined Actions create/approve-PR setting must allow PR creation for the compatibility
projection to open its review PR; the workflow never approves or merges it.
