# Haunted Manor & Ghost Investigation

200 distinct static pixel-art inventory icons. Native 64×64 transparent PNGs, exact 128×128 and 256×256 nearest-neighbour exports, atlas, manifest and searchable preview. AI-generated with PixelLab (Pixen model), curated and checked individually.

## Contents

| Folder / file | What it is |
|---|---|
| `png_64/` | 200 native 64×64 RGBA PNGs |
| `png_128/`, `png_256/` | The same icons scaled exactly 2× and 4× (nearest neighbour) |
| `atlases/pack_64.png` + `.json` | 1024×1024 atlas, 14 columns, 68 px cells, sprite at +2 px |
| `atlases/categories/` | One 5×4 atlas (340×272) + JSON per category |
| `previews/` | Cover and one contact sheet per category |
| `sample_20/` | Two icons from each category (part of the 200, not extra art) |
| `manifest.json`, `asset_list.csv` | IDs, names, categories, paths, bounding boxes, atlas rects |
| `preview.html` | Offline gallery: search, category filter, 1×/2×/4×, dark/light/checker |

## Categories

| Category | Icons |
|---|---:|
| evidence | 20 |
| investigator tools | 20 |
| seating furniture | 20 |
| lighting | 20 |
| curios | 20 |
| locks clocks | 20 |
| haunted toys | 20 |
| mirrors frames | 20 |
| spectral instruments | 20 |
| manor quest | 20 |

Bounding boxes are `[left, top, right, bottom]` with exclusive right/bottom; atlas rects are `[x, y, width, height]`.
Graphics were created with generative AI (PixelLab) and then reviewed and cleaned by hand-picked free pixel edits.
