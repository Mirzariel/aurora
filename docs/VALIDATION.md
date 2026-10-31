# Validation — 2026-10-31

## Website checks

- `node --check assets/js/main.js`: passed.
- HTML local asset references, CSS URLs, fragment anchors and unique IDs: passed.
- All seven original numeric evidence values match Git HEAD `0806f55`.
- SHA-256 checks show original image, video and logo files unchanged. Credit documentation was intentionally updated.
- No page references to unfinished `assets/3d/`, `assets/vendor/`, or `pcb-viewer.js`.

## Browser checks

Chrome headless, served locally using a temporary profile. Raw report, script and screenshots are in `tmp/aurora-site-review/` in the Capstone workspace.

| Viewport | Horizontal overflow | Journey layout |
| --- | --- | --- |
| 1440 × 1000 | None | Native-scroll sticky |
| 1024 × 768 | None | Linear: sticky content would exceed available height |
| 768 × 1024 | None | Linear |
| 390 × 844 | None | Linear |
| 320 × 740 | None | Linear |

- Packet progress checked at start, midpoint, end and reverse movement.
- Reduced motion, `?static`, and a simulated save-data connection use linear layout.
- With JavaScript disabled, seven content sections and all five journey steps remain available without horizontal overflow.
- Native hardware disclosure opens through the keyboard.
- Stock video does not download before playback; playback decoded at 1280 × 720 with a duration of 6.5065 seconds.
- No JavaScript errors, failed HTTP responses, or external network requests were observed in the tested page flows.
- Desktop hero, context photo, packet scene, composited PCB render and mobile hero screenshots were inspected. Mobile art is placed lower so the lamp does not cross the copy.

## Boundaries

These checks cover the local Chrome implementation, not a full cross-browser accessibility or performance audit. They do not validate electrical hardware, field radio behavior, or current-board fabrication readiness. The page uses the old PCB model for the render under the user's explicit visualization waiver; see `3D-ASSET-REVIEW.md`.

Validation was completed locally before the repository upload. No hosting deployment was performed as part of these checks.
