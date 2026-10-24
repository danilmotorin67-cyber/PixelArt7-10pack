#!/usr/bin/env python3
"""Record a review decision. note.py PACK NUM DECISION [--as "drawn as name"] [--note "..."] [--fix "..."]
DECISION: accepted | renamed | problem"""
import argparse
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("pack", type=int)
ap.add_argument("num", type=int)
ap.add_argument("decision", choices=["accepted", "renamed", "problem"])
ap.add_argument("--as", dest="drawn_as")
ap.add_argument("--note", default="")
ap.add_argument("--fix")
a = ap.parse_args()
path = os.path.join(ROOT, "production", "review", "pack%02d.json" % a.pack)
data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
f = glob.glob(os.path.join(ROOT, "production", "raw", "pack%02d_%03d_*.png" % (a.pack, a.num)))[0]
aid = os.path.basename(f)[:-4]
rec = {"decision": a.decision, "note": a.note}
if a.drawn_as:
    rec["drawn_as"] = a.drawn_as
if a.fix:
    rec["fix_note"] = a.fix
data[aid] = rec
json.dump(dict(sorted(data.items())), open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(aid, rec)
