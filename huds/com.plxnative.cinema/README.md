# Cinema

PlxNative's Cinema HUD: a bottom block with the title, a gold scrub bar, one transport row, an inline Chapters
strip and an Info card. Its look follows a community mock-up of the player
([discussion](https://github.com/GLinnik21/plx-native/discussions/933#discussioncomment-19174382)).

What it shows of Player HUD format 1.0:

- A bottom-anchored block whose Chapters and Info sections open inline, together or alone.
- A centred row of back 10, previous, play/pause, next and forward 30; subtitles, the Chapters list, Info and
  the More menu at the right end of the row. Previous always shows its skip-back glyph, also when a press restarts.
- A strip of chapter cards with left-aligned labels, and an Info card with a still, the title, a two-line
  synopsis and the facts.
- Thin outline glyphs in `assets/` (alpha masks, one stroke weight); the transport glyphs stay the app's own.

The type sits on the app's ladder, so it is larger than the mock's literal sizes. The knob and clocks, the clock
spelling, focus, menus, captions and playback stay the app's.

HUD source and SVG assets use CC0-1.0.

Maintenance contact: @GLinnik21.
