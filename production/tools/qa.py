#!/usr/bin/env python3
"""Per-image QA metrics and review contact sheets (METHOD_GUIDE_RU.md section 10).

Usage: qa.py sheet OUT.png FILE [FILE ...]   # review sheet: dark / light / checker at 3x
       qa.py metrics FILE [FILE ...]          # JSON metrics per file
"""
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw


def metrics(path):
    im = Image.open(path)
    frames = getattr(im, "n_frames", 1)
    a = np.array(im.convert("RGBA"))
    al = a[..., 3]
    vis = al > 0
    m = {"file": os.path.basename(path), "size": list(im.size), "mode": im.mode, "frames": frames,
         "visible_px": int(vis.sum()), "transparent_px": int((al == 0).sum()),
         "semi_alpha_px": int(((al > 0) & (al < 255)).sum())}
    if vis.any():
        ys, xs = np.nonzero(vis)
        l, t, r, b = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        w, h = im.size
        m["bbox"] = [l, t, r, b]
        m["longest_side"] = max(r - l, b - t)
        m["min_margin"] = min(l, t, w - r, h - b)
        m["colors"] = len({tuple(p) for p in a[vis][:, :4]})
        clean = a.copy()
        clean[~vis] = 0
        m["visible_sha256"] = hashlib.sha256(clean.tobytes()).hexdigest()
    flags = []
    if tuple(im.size) != (64, 64):
        flags.append("size")
    if frames != 1:
        flags.append("frames")
    if not vis.any() or m["transparent_px"] == 0:
        flags.append("empty_or_opaque")
    else:
        if m["semi_alpha_px"]:
            flags.append("semi_alpha")
        if m["min_margin"] == 0:
            flags.append("touches_edge")
        elif m["min_margin"] < 4:
            flags.append("margin<4")
        if m["colors"] > 48:
            flags.append("colors>48")
    m["flags"] = flags
    return m


def checker(w, h, s=8):
    yy, xx = np.mgrid[0:h, 0:w]
    c = (((yy // s) + (xx // s)) % 2).astype(np.uint8)
    arr = np.where(c[..., None] == 0, [200, 200, 200, 255], [150, 150, 150, 255]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def sheet(out, files, scale=3, cols=2):
    cell = 64 * scale
    pad = 6
    label_h = 14
    bgs = [Image.new("RGBA", (cell, cell), (34, 30, 40, 255)),
           Image.new("RGBA", (cell, cell), (236, 232, 222, 255)),
           checker(cell, cell)]
    rows = (len(files) + cols - 1) // cols
    W = cols * (3 * cell + 2 * pad) + pad * 3
    H = rows * (cell + label_h + pad) + pad
    S = Image.new("RGBA", (W, H), (90, 90, 90, 255))
    d = ImageDraw.Draw(S)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA").resize((cell, cell), Image.NEAREST)
        x0 = pad + (i % cols) * (3 * cell + 2 * pad + pad)
        y0 = pad + (i // cols) * (cell + label_h + pad)
        for j, bg in enumerate(bgs):
            t = bg.copy()
            t.alpha_composite(im)
            S.paste(t, (x0 + j * (cell + 1), y0 + label_h))
        d.text((x0, y0), os.path.basename(f)[:70], fill=(255, 255, 255, 255))
    S.save(out)


if __name__ == "__main__":
    if sys.argv[1] == "sheet":
        sheet(sys.argv[2], sys.argv[3:])
    else:
        for f in sys.argv[2:]:
            print(json.dumps(metrics(f)))
