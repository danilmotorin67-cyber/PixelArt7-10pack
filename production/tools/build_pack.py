#!/usr/bin/env python3
"""Assemble one finished pack (METHOD_GUIDE_RU.md sections 10-11).

Source per slot: production/fixed/<file> (manual free fix) else production/raw/<file>.
Automatic free cleanup, recorded per asset: alpha binarised at 128; a whole object
shifted toward the centre when a margin is under 4 px and the opposite side has room.
Review decisions come from production/review/packNN.json.

Usage: build_pack.py 8
"""
import csv
import hashlib
import html
import json
import os
import shutil
import sqlite3
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROD = os.path.join(ROOT, "production")
OUT = os.path.join(ROOT, "outputs", "pixel_series_2000")
PLAN = os.path.join(ROOT, "method", "generation_plan.json")
CELL, PAD, COLS = 68, 2, 14


def load_prompts():
    out = {}
    for name in ("prompts_packs_08_10.jsonl", "prompts_v2_packs_08_10.jsonl"):
        with open(os.path.join(ROOT, "method", name), encoding="utf-8") as f:
            for e in map(json.loads, f):
                out.setdefault(e["id"], {})[e["prompt_version"]] = e
    return out


def prompt_version(notes):
    """Attempts store {"prompt_version": n, ...} in notes; the two early REST attempts were v1."""
    try:
        return int(json.loads(notes).get("prompt_version", 1))
    except (TypeError, ValueError, AttributeError):
        return 1


def cleanup(a):
    """Free pixel cleanup; returns (array, list of notes)."""
    notes = []
    al = a[..., 3]
    semi = (al > 0) & (al < 255)
    if semi.any():
        a = a.copy()
        a[..., 3] = np.where(al >= 128, 255, 0)
        a[a[..., 3] == 0] = 0
        notes.append("alpha binarised (%d semi-transparent px)" % int(semi.sum()))
    vis = a[..., 3] > 0
    ys, xs = np.nonzero(vis)
    l, t, r, b = xs.min(), ys.min(), 64 - xs.max() - 1, 64 - ys.max() - 1
    dx = dy = 0
    if min(l, r) < 4 and abs(l - r) > 1:
        dx = (r - l) // 2
    if min(t, b) < 4 and abs(t - b) > 1:
        dy = (b - t) // 2
    if dx or dy:
        a = np.roll(np.roll(a, dy, 0), dx, 1)
        notes.append("object shifted by (%d,%d) to balance margins" % (dx, dy))
    return a, notes


def upscale(im, k):
    return im.resize((64 * k, 64 * k), Image.NEAREST)


def contact_sheet(files, labels, out, scale=2, cols=5, bg=(38, 34, 44, 255)):
    cell = 64 * scale
    lab = 26
    W = cols * (cell + 12) + 12
    rows = (len(files) + cols - 1) // cols
    S = Image.new("RGBA", (W, rows * (cell + lab + 12) + 12), bg)
    d = ImageDraw.Draw(S)
    for i, (f, t) in enumerate(zip(files, labels)):
        x = 12 + (i % cols) * (cell + 12)
        y = 12 + (i // cols) * (cell + lab + 12)
        S.alpha_composite(Image.open(f).convert("RGBA").resize((cell, cell), Image.NEAREST), (x, y))
        words, line, lines = t.split(), "", []
        for w in words:
            if len(line) + len(w) + 1 > 24:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        for k, ln in enumerate(lines[:2]):
            d.text((x, y + cell + 2 + k * 11), ln, fill=(225, 220, 210, 255))
    S.save(out)


GALLERY = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#1e1b22;--fg:#ece6da;--card:#2a2630;--line:#45404c;--accent:#c4a662}
body{margin:0;font:14px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;background:var(--bg);padding:12px 16px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:8px;align-items:center;z-index:1}
h1{font-size:18px;margin:0 12px 0 0}
input,select,button{font:inherit;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 8px}
button.on{border-color:var(--accent);color:var(--accent)}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--cw),1fr));gap:10px;padding:16px}
.c{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center}
.c .im{display:flex;align-items:center;justify-content:center;border-radius:4px;margin-bottom:6px}
.c img{image-rendering:pixelated;display:block}
.c small{display:block;opacity:.7;font-size:11px;word-break:break-all}
.c a{color:var(--accent);font-size:11px;margin:0 3px}
.dark .im{background:#141218}.light .im{background:#efe9dd}
.chk .im{background:repeating-conic-gradient(#bbb 0 25%,#888 0 50%) 0 0/16px 16px}
#count{opacity:.7}
</style></head><body class="dark">
<header><h1>__TITLE__</h1>
<input id="q" placeholder="Search ID or name" size="22">
<select id="cat"><option value="">All categories</option></select>
<span><button data-z="1">1×</button><button data-z="2" class="on">2×</button><button data-z="4">4×</button></span>
<span><button data-b="dark" class="on">Dark</button><button data-b="light">Light</button><button data-b="chk">Checker</button></span>
<span id="count"></span></header>
<div id="grid"></div>
<script>
const DATA=__DATA__;let z=2;
const cat=document.getElementById('cat'),grid=document.getElementById('grid'),q=document.getElementById('q');
[...new Map(DATA.map(d=>[d.category_id,d.category_ru+' / '+d.category_id]))].forEach(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=v;cat.appendChild(o)});
function draw(){const s=q.value.trim().toLowerCase(),c=cat.value;const items=DATA.filter(d=>(!c||d.category_id===c)&&(!s||d.stable_id.includes(s)||d.name_en.toLowerCase().includes(s)));
document.documentElement.style.setProperty('--cw',(64*z+40)+'px');
grid.innerHTML=items.map(d=>`<div class="c"><div class="im" style="height:${64*z+8}px"><img src="${d.paths['64']}" width="${64*z}" height="${64*z}" alt="${d.name_en}"></div>${d.name_en}<small>${d.stable_id}</small><a href="${d.paths['64']}">64</a><a href="${d.paths['128']}">128</a><a href="${d.paths['256']}">256</a></div>`).join('');
document.getElementById('count').textContent=items.length+' / '+DATA.length;}
document.querySelectorAll('[data-z]').forEach(b=>b.onclick=()=>{z=+b.dataset.z;document.querySelectorAll('[data-z]').forEach(x=>x.classList.toggle('on',x===b));draw()});
document.querySelectorAll('[data-b]').forEach(b=>b.onclick=()=>{document.body.className=b.dataset.b;document.querySelectorAll('[data-b]').forEach(x=>x.classList.toggle('on',x===b))});
q.oninput=draw;cat.onchange=draw;draw();
</script></body></html>
"""


def main(pack_no):
    plan = json.load(open(PLAN, encoding="utf-8"))
    pack = [p for p in plan["packs"] if p["number"] == pack_no][0]
    prompts = load_prompts()
    entries = sorted((v[1] for v in prompts.values() if v[1]["pack_number"] == pack_no), key=lambda e: e["number"])
    review_path = os.path.join(PROD, "review", "pack%02d.json" % pack_no)
    review = json.load(open(review_path, encoding="utf-8")) if os.path.exists(review_path) else {}
    db = sqlite3.connect(os.path.join(PROD, "production_ledger.sqlite"))
    att = {r[0]: r for r in db.execute(
        "SELECT asset_id,state,job_id,gallery_id,charged_units,request_sha256,notes FROM attempts")}

    slug = "%02d_%s" % (pack_no, pack["slug"])
    root = os.path.join(OUT, slug)
    if os.path.exists(root):
        shutil.rmtree(root)
    dirs = ["png_64", "png_128", "png_256", "atlases/categories", "previews", "sample_20", "source", "qa"]
    for d in dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)

    manifest, rows, audit, qa_rows, missing = [], [], [], [], []
    accepted = []
    for e in entries:
        aid = e["id"]
        a_row = att.get(aid)
        src = os.path.join(PROD, "fixed", e["filename"])
        manual_fix = os.path.exists(src)
        if not manual_fix:
            src = os.path.join(PROD, "raw", e["filename"])
        rv = review.get(aid, {})
        if not os.path.exists(src) or a_row is None or a_row[1] != "completed" or rv.get("decision") == "problem":
            missing.append({"stable_id": aid, "state": a_row[1] if a_row else "not_submitted",
                            "reason": rv.get("note", "no accepted image")})
            continue
        raw_m = qa.metrics(os.path.join(PROD, "raw", e["filename"]))
        arr, notes = cleanup(np.array(Image.open(src).convert("RGBA")))
        if manual_fix:
            notes.insert(0, rv.get("fix_note", "manual free pixel fix"))
        im = Image.fromarray(arr.astype(np.uint8), "RGBA")
        p64 = os.path.join(root, "png_64", e["filename"])
        im.save(p64, optimize=True)
        upscale(im, 2).save(os.path.join(root, "png_128", e["filename"]), optimize=True)
        upscale(im, 4).save(os.path.join(root, "png_256", e["filename"]), optimize=True)
        m = qa.metrics(p64)
        pv = prompt_version(a_row[6])
        used = prompts[aid].get(pv, e)
        accepted.append((e, m))
        qa_rows.append({"stable_id": aid, "raw_flags": raw_m["flags"], "final_flags": m["flags"], "fixes": notes,
                        "review": rv.get("decision", "accepted"), "review_note": rv.get("note", "")})
        audit.append({"stable_id": aid, "prompt_version": pv, "seed": used["args"]["seed"],
                      "request_sha256": a_row[5], "job_id": a_row[2], "gallery_id": a_row[3],
                      "charged_generations": a_row[4], "tool": "PixelLab create_image_pixen",
                      "params": {k: v for k, v in used["args"].items() if k != "description"}})
        manifest.append({"stable_id": aid, "pack_id": pack["slug"], "category_id": e["category_id"],
                         "name_en": rv.get("drawn_as", e["name_en"]), "planned_name_en": e["name_en"],
                         "category_ru": e["category_ru"], "tags": e["tags"],
                         "status": "accepted_renamed" if rv.get("drawn_as") else "accepted",
                         "native_size": [64, 64],
                         "paths": {"64": "png_64/" + e["filename"], "128": "png_128/" + e["filename"],
                                   "256": "png_256/" + e["filename"]},
                         "visible_bbox": m["bbox"], "colors": m["colors"], "visible_sha256": m["visible_sha256"],
                         "prompt_version": pv, "free_fixes": notes,
                         "generation": {"seed": used["args"]["seed"], "request_sha256": a_row[5],
                                        "job_id": a_row[2], "gallery_id": a_row[3], "charged_generations": a_row[4]}})
        with open(os.path.join(root, "source", "prompts.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"stable_id": aid, "prompt_version": pv, "prompt": used["prompt"],
                                "args": used["args"]}, ensure_ascii=False) + "\n")

    # exact-pixel checks of exports
    for e, _ in accepted:
        base = np.array(Image.open(os.path.join(root, "png_64", e["filename"])).convert("RGBA"))
        for k, d in ((2, "png_128"), (4, "png_256")):
            big = np.array(Image.open(os.path.join(root, d, e["filename"])).convert("RGBA"))
            assert (big == base.repeat(k, 0).repeat(k, 1)).all(), e["filename"]

    # duplicate check (visible pixels)
    shas = {}
    for m in manifest:
        shas.setdefault(m["visible_sha256"], []).append(m["stable_id"])
    dups = [v for v in shas.values() if len(v) > 1]

    # atlas 1024x1024, 14 columns, 68 px cells, sprite offset 2 px
    atlas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    frames = {}
    for i, m in enumerate(manifest):
        x, y = (i % COLS) * CELL + PAD, (i // COLS) * CELL + PAD
        atlas.paste(Image.open(os.path.join(root, m["paths"]["64"])), (x, y))
        m["atlas_rect"] = [x, y, 64, 64]
        frames[m["stable_id"]] = {"frame": {"x": x, "y": y, "w": 64, "h": 64}, "category_id": m["category_id"]}
    atlas.save(os.path.join(root, "atlases", "pack_64.png"), optimize=True)
    json.dump({"meta": {"image": "pack_64.png", "size": {"w": 1024, "h": 1024}, "cell": CELL, "padding": PAD,
                        "columns": COLS, "sprite": 64, "count": len(manifest)}, "frames": frames},
              open(os.path.join(root, "atlases", "pack_64.json"), "w"), indent=1)
    A = np.array(atlas)
    for m in manifest:
        x, y, w, h = m["atlas_rect"]
        assert (A[y:y + h, x:x + w] == np.array(Image.open(os.path.join(root, m["paths"]["64"])).convert("RGBA"))).all()

    # category atlases 5x4 (340x272) and contact sheets
    cats = []
    for c in pack["categories"]:
        items = [m for m in manifest if m["category_id"] == c["id"]]
        cats.append((c, items))
        ca = Image.new("RGBA", (5 * CELL, 4 * CELL), (0, 0, 0, 0))
        cf = {}
        for i, m in enumerate(items):
            x, y = (i % 5) * CELL + PAD, (i // 5) * CELL + PAD
            ca.paste(Image.open(os.path.join(root, m["paths"]["64"])), (x, y))
            cf[m["stable_id"]] = {"frame": {"x": x, "y": y, "w": 64, "h": 64}}
        n = "%02d_%s" % (pack["categories"].index(c) + 1, c["id"])
        ca.save(os.path.join(root, "atlases", "categories", n + ".png"), optimize=True)
        json.dump({"meta": {"image": n + ".png", "size": {"w": 340, "h": 272}, "cell": CELL, "padding": PAD,
                            "columns": 5, "rows": 4}, "frames": cf},
                  open(os.path.join(root, "atlases", "categories", n + ".json"), "w"), indent=1)
        contact_sheet([os.path.join(root, m["paths"]["64"]) for m in items], [m["name_en"] for m in items],
                      os.path.join(root, "previews", "sheet_" + n + ".png"))
    # cover: first 3 of each category from finished art only
    pick = [m for _, items in cats for m in items[:3]]
    cover = Image.new("RGBA", (10 * 140 + 20, 3 * 140 + 120), (30, 27, 35, 255))
    for ci, (c, items) in enumerate(cats):
        for k, m in enumerate(items[:3]):
            cover.alpha_composite(Image.open(os.path.join(root, m["paths"]["128"])).convert("RGBA"),
                                  (16 + ci * 140, 100 + k * 140))
    d = ImageDraw.Draw(cover)
    d.text((16, 24), pack["title"], fill=(236, 228, 210, 255), font_size=40)
    d.text((16, 72), "%d static 64x64 pixel-art icons  |  128 / 256 exports" % len(manifest),
           fill=(190, 182, 168, 255), font_size=18)
    cover.save(os.path.join(root, "previews", "cover.png"), optimize=True)

    # sample_20: two finished icons of each category, all three sizes
    for size in ("png_64", "png_128", "png_256"):
        os.makedirs(os.path.join(root, "sample_20", size), exist_ok=True)
    for c, items in cats:
        for m in items[:2]:
            for size in ("png_64", "png_128", "png_256"):
                shutil.copy(os.path.join(root, size, os.path.basename(m["paths"]["64"])),
                            os.path.join(root, "sample_20", size))

    json.dump({"pack": pack["title"], "pack_id": pack["slug"], "pack_number": pack_no, "count": len(manifest),
               "planned": 200, "native_size": [64, 64], "exports": [64, 128, 256],
               "bbox_format": "[left, top, right, bottom], right/bottom exclusive",
               "atlas_rect_format": "[x, y, width, height] in atlases/pack_64.png", "assets": manifest},
              open(os.path.join(root, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(root, "asset_list.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stable_id", "number", "category_id", "category_ru", "name_en", "file_64", "file_128",
                    "file_256", "atlas_x", "atlas_y", "colors"])
        for m in manifest:
            w.writerow([m["stable_id"], int(m["stable_id"][7:10]), m["category_id"], m["category_ru"], m["name_en"],
                        m["paths"]["64"], m["paths"]["128"], m["paths"]["256"], m["atlas_rect"][0],
                        m["atlas_rect"][1], m["colors"]])
    data = [{k: m[k] for k in ("stable_id", "name_en", "category_id", "category_ru", "paths")} for m in manifest]
    with open(os.path.join(root, "preview.html"), "w", encoding="utf-8") as f:
        f.write(GALLERY.replace("__TITLE__", html.escape(pack["title"])).replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    cat_table_ru = "\n".join("| %s | %d |" % (c["name_ru"], len(items)) for c, items in cats)
    cat_table_en = "\n".join("| %s | %d |" % (c["id"].replace("_", " "), len(items)) for c, items in cats)
    open(os.path.join(root, "README.md"), "w", encoding="utf-8").write(f"""# {pack['title']}

{len(manifest)} distinct static pixel-art inventory icons. Native 64×64 transparent PNGs, exact 128×128 and 256×256 nearest-neighbour exports, atlas, manifest and searchable preview. AI-generated with PixelLab (Pixen model), curated and checked individually.

## Contents

| Folder / file | What it is |
|---|---|
| `png_64/` | {len(manifest)} native 64×64 RGBA PNGs |
| `png_128/`, `png_256/` | The same icons scaled exactly 2× and 4× (nearest neighbour) |
| `atlases/pack_64.png` + `.json` | 1024×1024 atlas, 14 columns, 68 px cells, sprite at +2 px |
| `atlases/categories/` | One 5×4 atlas (340×272) + JSON per category |
| `previews/` | Cover and one contact sheet per category |
| `sample_20/` | Two icons from each category (part of the {len(manifest)}, not extra art) |
| `manifest.json`, `asset_list.csv` | IDs, names, categories, paths, bounding boxes, atlas rects |
| `preview.html` | Offline gallery: search, category filter, 1×/2×/4×, dark/light/checker |

## Categories

| Category | Icons |
|---|---:|
{cat_table_en}

Bounding boxes are `[left, top, right, bottom]` with exclusive right/bottom; atlas rects are `[x, y, width, height]`.
Graphics were created with generative AI (PixelLab) and then reviewed and cleaned by hand-picked free pixel edits.
""")
    open(os.path.join(root, "README_RU.md"), "w", encoding="utf-8").write(f"""# {pack['title']} — {pack['name_ru']}

{len(manifest)} самостоятельных статичных пиксельных иконок. Исходник 64×64 PNG с прозрачностью, точные экспорты 128×128 и 256×256 (nearest neighbour), атласы, манифест и локальная галерея. Создано с помощью генеративного AI PixelLab (модель Pixen), каждая иконка проверена отдельно.

Назначение: {pack['purpose']}

| Категория | Иконок |
|---|---:|
{cat_table_ru}

Папки: `png_64/`, `png_128/`, `png_256/` — иконки; `atlases/` — общий атлас 1024×1024 (14 колонок, ячейка 68 px, сдвиг 2 px) и атласы категорий 5×4; `previews/` — обложка и контактные листы; `sample_20/` — по 2 иконки каждой категории из этих же {len(manifest)}; `preview.html` — галерея без интернета.
""")
    json.dump({"pack": pack["title"], "assets": audit}, open(os.path.join(root, "source", "generation_audit.json"), "w"), indent=1)
    json.dump({"accepted": len(manifest), "planned": 200, "missing": missing, "exact_duplicates": dups,
               "exports_pixel_exact": True, "atlas_regions_exact": True, "per_asset": qa_rows},
              open(os.path.join(root, "qa", "qa_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    title = pack["title"].replace(" & ", "_").replace(" ", "_")
    zname = "%s_%d.zip" % (title, len(manifest))
    zpath = os.path.join(root, zname)
    buyer = ["png_64", "png_128", "png_256", "atlases", "previews", "sample_20",
             "manifest.json", "asset_list.csv", "preview.html", "README.md", "README_RU.md"]
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for item in buyer:
            p = os.path.join(root, item)
            if os.path.isdir(p):
                for dp, _, fs in os.walk(p):
                    for fn in sorted(fs):
                        full = os.path.join(dp, fn)
                        z.write(full, os.path.join(slug, os.path.relpath(full, root)))
            else:
                z.write(p, os.path.join(slug, item))
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        n64 = len([n for n in z.namelist() if "/png_64/" in n and "sample_20" not in n])
    print(json.dumps({"pack": slug, "accepted": len(manifest), "missing": len(missing), "dups": dups,
                      "zip": os.path.relpath(zpath, ROOT), "zip_png64": n64,
                      "zip_mb": round(os.path.getsize(zpath) / 1e6, 2)}))


if __name__ == "__main__":
    main(int(sys.argv[1]))
