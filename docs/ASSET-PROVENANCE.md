# Asset provenance

Updated 2026-10-31.

## Existing work retained

Original Claude images, logos, videos, and generators remain at their original paths in `assets/brand/`, `assets/img/`, `assets/video/`, and `assets/tools/`. New variants do not overwrite them. The local session records original image/video/brand hashes in `tmp/aurora-site-review/original-assets-sha256.json`.

The unfinished `assets/3d/`, `assets/vendor/`, and `assets/js/pcb-viewer.js` were already untracked before this work. They remain inactive source work, not page dependencies.

The old LoRa video is retained as source material. Its captions/ACK sequence have unresolved technical caveats, so the revised page uses a native scroll diagram to explain the planned flow.

## New assets

| Directory | Purpose | Details |
| --- | --- | --- |
| `assets/generated/` | Aurora streetlight hero illustration and small-screen derivative | Built-in ImageGen; full prompt in `GENERATED-ASSETS.md` |
| `assets/media-stock/` | Actual Simalungun PJU-TS photograph and short nighttime stock clip | Sources, credits, licenses and transformations in `STOCK-MEDIA.md` |
| `assets/renders-v2/` | New lighting and views of the old PCB model | Source hash, visualization waiver, DRC limits in `3D-ASSET-REVIEW.md` |

The page serves optimized derivatives; generated source PNG and native render outputs are retained for revision. Normal viewing does not contact image-generation services or stock providers. Fonts and scripts are local.
