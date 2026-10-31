# Old-model rendering sources

These scripts reproduce the visualization session, not a fresh KiCad export. Blender 5.2.2 and Pillow were used. Expected input: `assets/3d/_src-orig.glb`, SHA-256 `B13467A05BF1269DF07EFBBA2E3F06426AC4AA08FDA7A9C2F44E904191C1B1CF`.

The input belongs to the existing unfinished/untracked model sources. Obtain that exact archived model before reproducing this pass; do not substitute a newer board and imply it has passed DRC.

From the website directory, run:

```text
blender --background --python assets/tools/render-v2/render.py
blender --background --python assets/tools/render-v2/render-top.py
python assets/tools/render-v2/web-export.py
```

The first script renders four PNG views, the second supplies the wider top camera, and the third crops the hero canvas and exports WebP derivatives. Geometry and imported materials are retained. See `docs/3D-ASSET-REVIEW.md` for the user's old-model visualization waiver and unresolved current-board DRC findings.
