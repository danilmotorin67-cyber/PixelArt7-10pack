#!/usr/bin/env python3
"""Series catalog for packs 08-10, cross-pack duplicate check and the combined archive."""
import csv
import json
import os
import sqlite3
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "outputs", "pixel_series_2000")
packs = sorted(d for d in os.listdir(OUT) if os.path.isdir(os.path.join(OUT, d)) and d[:2] in ("08", "09", "10"))

rows, shas, summary = [], {}, []
for p in packs:
    m = json.load(open(os.path.join(OUT, p, "manifest.json"), encoding="utf-8"))
    q = json.load(open(os.path.join(OUT, p, "qa", "qa_report.json"), encoding="utf-8"))
    zips = [f for f in os.listdir(os.path.join(OUT, p)) if f.endswith(".zip")]
    summary.append({"pack": p, "title": m["pack"], "icons": m["count"], "zip": p + "/" + zips[0],
                    "renamed": sum(a["status"] == "accepted_renamed" for a in m["assets"]),
                    "replacements": sum(a["prompt_version"] == "replacement" for a in m["assets"]),
                    "manual_free_fixes": sum(any(f.startswith("free fix") for f in a["free_fixes"]) for a in m["assets"]),
                    "missing": [x["stable_id"] for x in q["missing"]]})
    for a in m["assets"]:
        shas.setdefault(a["visible_sha256"], []).append(a["stable_id"])
        rows.append([p, a["stable_id"], a["category_id"], a["category_ru"], a["name_en"], a["planned_name_en"],
                     a["status"], p + "/" + a["paths"]["64"]])

db = sqlite3.connect(os.path.join(ROOT, "production", "production_ledger.sqlite"))
plan = db.execute("SELECT * FROM budget_summary").fetchone()
rr = db.execute("SELECT COUNT(*), COALESCE(SUM(charged_units),0) FROM reroll_attempts").fetchone()
spend = {"planned_slots": 600, "paid_attempts": plan[0], "confirmed_charged": plan[1], "held": plan[2],
         "ambiguous": plan[4], "owner_approved_replacements": rr[0], "replacement_charged": rr[1],
         "total_generations_charged": plan[1] + rr[1]}
dups = [v for v in shas.values() if len(v) > 1]
json.dump({"packs": summary, "spend": spend, "cross_pack_exact_duplicates": dups, "icons": len(rows)},
          open(os.path.join(OUT, "catalog_08_10.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "catalog_08_10.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["pack", "stable_id", "category_id", "category_ru", "name_en", "planned_name_en", "status", "png_64"])
    w.writerows(rows)
zpath = os.path.join(OUT, "Packs_08_10_%d.zip" % len(rows))
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
    for s in summary:
        z.write(os.path.join(OUT, s["zip"]), s["zip"].split("/")[-1])
    z.write(os.path.join(OUT, "catalog_08_10.csv"), "catalog_08_10.csv")
with zipfile.ZipFile(zpath) as z:
    assert z.testzip() is None
print(json.dumps({"icons": len(rows), "dups": dups, "spend": spend, "zip": os.path.relpath(zpath, ROOT),
                  "packs": [(s["pack"], s["icons"], s["renamed"], s["replacements"], s["manual_free_fixes"]) for s in summary]}, ensure_ascii=False))
