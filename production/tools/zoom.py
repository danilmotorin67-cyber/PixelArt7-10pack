#!/usr/bin/env python3
"""Zoomed view with a coordinate grid, for planning free pixel fixes. zoom.py IN OUT [scale]"""
import sys
from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]
s = int(sys.argv[3]) if len(sys.argv) > 3 else 12
im = Image.open(src).convert("RGBA")
w, h = im.size
bg = Image.new("RGBA", (w * s + 24, h * s + 24), (120, 120, 120, 255))
big = im.resize((w * s, h * s), Image.NEAREST)
canvas = Image.new("RGBA", big.size, (40, 40, 48, 255))
canvas.alpha_composite(big)
bg.paste(canvas, (24, 24))
d = ImageDraw.Draw(bg)
for i in range(0, w + 1, 4):
    d.line([(24 + i * s, 24), (24 + i * s, 24 + h * s)], fill=(255, 255, 0, 90) if i % 8 else (255, 80, 80, 160))
    if i < w and i % 8 == 0:
        d.text((24 + i * s + 2, 6), str(i), fill=(255, 255, 255, 255))
for j in range(0, h + 1, 4):
    d.line([(24, 24 + j * s), (24 + w * s, 24 + j * s)], fill=(255, 255, 0, 90) if j % 8 else (255, 80, 80, 160))
    if j < h and j % 8 == 0:
        d.text((2, 24 + j * s + 2), str(j), fill=(255, 255, 255, 255))
bg.save(out)
