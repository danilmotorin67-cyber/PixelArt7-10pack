#!/usr/bin/env python3
"""Review sheet for one category (20 slots) from raw/fixed images. review_sheet.py PACK FIRST OUT"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pack, first, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
files = []
for n in range(first, first + 20):
    hits = glob.glob(os.path.join(ROOT, "production", "fixed", "pack%02d_%03d_*.png" % (pack, n))) or \
        glob.glob(os.path.join(ROOT, "production", "raw", "pack%02d_%03d_*.png" % (pack, n)))
    files += hits
qa.sheet(out, files, scale=2, cols=4)
for f in files:
    m = qa.metrics(f)
    if m["flags"]:
        print(m["file"][:50], m["longest_side"], m["min_margin"], m["colors"], m["flags"])
print(len(files), "files")
