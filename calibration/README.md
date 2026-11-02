# Measured registry text headroom

The initial corpus was collected on 2026-11-02 from the real rooted LG development TV
(app source `9266c34e7`) and the Linux/Ubuntu 24.04 simulator built by app CI run
[41461558740](https://github.com/GLinnik21/plx-native/actions/runs/41461558740)
(source `60410e182b1474cf10c48dac89310fdfd0ac0c7e`). The TV session used the repository TV lock,
a synthetic guest/mock, a muted TV and its panel on. Deployment verified all 47 files.
The native diagnostic reported `hud-text-metrics: wrote 12276 samples`.

The TV's `/usr/lib/libSDL2_ttf-2.0.so.0` SHA-256 was
`ab1dd4bd1648055f028459a573384a381e5a8ce276f22493910543fc756f3c42`.
Font identities are recorded in both reports and match exactly. No account, server address,
credential or device serial is part of the stored measurement reports.

`tv-metrics.json` is the native report. `60410e182.host.json` is the Linux CI report;
`60410e182.json` records their hashes, complete corpus coverage and worst positive differences.
There are 12,276 rows: all eleven shipped languages, every supported rung and both weights,
using the lint's actual label/command/chapter/episode-prefix candidates and clock-width envelopes.
A clock envelope can choose different widest digits on each renderer; its maximum width is compared.

| Rung | Registry margin, px |
|---|---:|
| MICRO | 7 |
| CAPTION | 6 |
| LABEL | 4 |
| BODY | 4 |
| HEADLINE | 7 |
| TITLE | 6 |
| DISPLAY | 6 |
| HUD_TITLE | 8 |
| HERO | 9 |

Each margin is the ceiling of the maximum positive `TV width - Linux width` at that rung.
Registry lint receives it explicitly with `--text-skew`; normal TV admission adds zero and uses
its own native widths. These measurements describe this renderer/font corpus; installed HUDs
continue to compile locally on each TV.

Every accepted simulator pin has a profile naming its exact host source and font bytes. The
release job compares an unchanged corpus directly with this TV evidence. When translations or
languages change, it carries the empirical per-rung margins only while the font hashes, native
text-renderer library hashes and type scale match a measured baseline. The profile records both
the original measurement and its current host binding; it does not claim the new strings were
measured on the TV. Changed fonts, renderer libraries or type sizes with a changed corpus require
fresh native evidence. Local compilation on each TV remains authoritative.
The `60410e182` and `f1436ba` profiles retain earlier iteration evidence. The active corrected
bootstrap pin is source `1c9a75db47dfbfddffdae133684698507be263cf`, published by app CI run
[41487654770](https://github.com/GLinnik21/plx-native/actions/runs/41487654770). Its manifest-hash-
named profile and host report (`3f9a62fc…`) compare all 12,276 rows directly with the native report,
without carrying a changed corpus, and produce the same margins above. The pinned bundle's preview
fixture now sets actual PMS chapter `tag` values for the long-title stress cases.
