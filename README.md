# PlxNative Player HUD registry

Declarative player layouts for [PlxNative](https://github.com/GLinnik21/plx-native).
Start with [AUTHORING.md](AUTHORING.md), [the schema](schema/1.0.json) and an [example](examples/).

Reference and Minimal seed the registry. Validation uses the app's exact compiler, all shipped
languages and the oldest compatible hash-pinned simulator. CI renders native state previews,
checks original-byte hashes and prepares a Pages catalog with revocation and compatibility data.

The repository is private during PR12 staging. `IMPLEMENTATION.md` records the remaining acceptance
evidence. Pushes always retain the verified catalog as a CI artifact. Set the repository variable
`PUBLISH_PAGES=true` to deploy main automatically, or dispatch the workflow with `publish=true`
for an explicit deployment. Pages hosting must first be available for the repository/account plan.
