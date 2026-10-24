#!/usr/bin/env python3
"""Free fix: erase painted scenery fragments that are not connected to the object.

Keeps the 8-connected opaque component holding (or nearest to) the canvas centre, plus
components lying entirely inside its bounding box; writes production/fixed/<name>.
Usage: strip_scenery.py [--largest-only] RAW_PNG [...]   (--largest-only keeps just the biggest component)
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def components(op):
    lab = np.zeros(op.shape, int)
    n = 0
    for y, x in zip(*np.nonzero(op)):
        if lab[y, x]:
            continue
        n += 1
        lab[y, x] = n
        q = deque([(y, x)])
        while q:
            cy, cx = q.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < op.shape[0] and 0 <= nx < op.shape[1] and op[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        q.append((ny, nx))
    return lab, n


largest_only = "--largest-only" in sys.argv
for src in [x for x in sys.argv[1:] if not x.startswith("--")]:
    a = np.array(Image.open(src).convert("RGBA"))
    op = a[..., 3] > 0
    lab, n = components(op)
    ys, xs = np.nonzero(op)
    d = (ys - 31.5) ** 2 + (xs - 31.5) ** 2
    main = lab[ys[d.argmin()], xs[d.argmin()]]
    if largest_only:
        main = int(np.argmax([(lab == k).sum() for k in range(1, n + 1)])) + 1
    my, mx = np.nonzero(lab == main)
    t, b, l, r = my.min(), my.max(), mx.min(), mx.max()
    keep = lab == main
    for k in range(1, n + 1):
        ky, kx = np.nonzero(lab == k)
        if not largest_only and k != main and ky.min() >= t and ky.max() <= b and kx.min() >= l and kx.max() <= r:
            keep |= lab == k
    a[~keep] = 0
    out = os.path.join(ROOT, "production", "fixed", os.path.basename(src))
    Image.fromarray(a).save(out)
    print(os.path.basename(out), "components", n, "kept px", int(keep.sum()), "of", int(op.sum()))
