# AURORA PCB 3D asset review

Review date: 2026-10-31

## Decision

Keep the existing website PCB illustrations as design visualizations. A fresh KiCad export is blocked by the current DRC gate. The user explicitly authorized “Lanjut render visual dari model lama” for visualization of the older existing model only. The `assets/renders-v2/` images are new Cycles renders from that older GLB, not a new board export. The existing render is not evidence of a manufactured board or a verified match to the current board revision.

## Source and provenance

- Board reviewed: `PCB Komunikasi/commie/commie.kicad_pcb` (SHA-256 `4AEEFD432323C2E2D9B9B8A87659D021FA963040D7D14EB39F94F462D3DE33A7`).
- `AURORA-Website/assets/3d/_src-orig.glb` and `PCB Komunikasi/commie/render-3d-warna-resistor/commie-warna.glb` are byte-identical (SHA-256 `B13467A05BF1269DF07EFBBA2E3F06426AC4AA08FDA7A9C2F44E904191C1B1CF`). The latter has a 2026-10-28 timestamp, matching the adjacent `commie-warna-resistor.kicad_pcb` timestamp, but matching timestamps alone do not prove how it was exported. That adjacent board has SHA-256 `C7AAE4D9AA7943A6C1298951F97DCDA26E933E0C95FBFDD851A636C139B697DF`, different from the reviewed board.
- `assets/3d/optimize_glb.py` describes a local geometry optimizer that bakes transforms and quantizes geometry; the compressed viewer assets are derivatives intended for the unfinished viewer, not authoritative hardware sources. No Blender scene or STEP was found in the website or the render directory.
- Existing `assets/img/pcb-3D-iso*.webp` and `pcb-3D-atas-berlabel*.webp` are already identified in `assets/img/CREDITS.md` as renderings. Inspection shows simplified module geometry and a CAD-like appearance. The large isometric image has pronounced horizontal edge/background artifacts; the labeled top image is a tightly cropped overhead diagram. Neither is a realistic product photograph. Do not infer unseen component details or fabrication readiness from them.

## Current DRC gate

KiCad 10 `pcb drc --severity-all --schematic-parity --exit-code-violations` on the reviewed board reported **161 DRC violations, 3 unconnected items, and 53 schematic parity issues**. Examples include annular-width errors, silkscreen issues, isolated copper, footprint library mismatches, and schematic pin conflicts. The full generated report is at `tmp/terra-3d/drc-current.rpt`. KiCad also printed registry access warnings; it nonetheless produced the report and counts above. The board was not modified or refilled.

## Next rendering pass

After resolving the DRC findings, or receiving an explicit waiver for a fresh export, regenerate STEP and GLB from the reviewed board with KiCad, inspect outline, holes and component models, and render hero, near-overhead, detail and back views with Cycles. Validate the actual outputs and disclose missing or simplified source models. Use the existing images as interim website illustrations with their existing design-visualization label; avoid presenting the old GLB as a current verified hardware export.


## Visualization outputs and checks

The authorized pass imports the older `_src-orig.glb` directly into Blender 5.2.2, without a new KiCad export or component geometry edits. Cycles rendered 32 samples with denoising and transparent film; original imported materials and component colors were retained. The camera, lighting, and hero canvas framing were adjusted. Outputs are `assets/renders-v2/aurora-old-model-hero-v3.webp` (1600 × 930), `aurora-old-model-top-v2.webp`, `aurora-old-model-detail-v2.webp`, and `aurora-old-model-back-v2.webp` (each 1400 × 1000); PNG counterparts are included. The hero v2 is the original, looser composition. The script is `tmp/terra-3d/render.py`, with the wider top camera in `tmp/terra-3d/render-top.py` and canvas/export processing in `tmp/terra-3d/web-export.py`.

Each PNG was visually inspected, including a pale-green composite of the hero. The source includes simplified module cases and ghost-marked parts; no model completeness or correspondence with the current PCB was verified. WebP files retain alpha; their fully transparent RGB can contain encoder color streaks in viewers that display RGB without respecting alpha. A normal alpha composite onto pale green was checked and does not show those streaks. Prefer the PNG when inspecting in an alpha-ignoring viewer.

Reproducible copies of the session scripts are retained in `assets/tools/render-v2/`, with workspace-relative paths and a usage README. These copies do not regenerate or certify the current PCB. The website displays the tighter hero v3 and offers top/detail/back views through a native disclosure.
