#!/usr/bin/env python3
"""Owner-approved replacement generations for rejected slots (user request 2026-10-24:
"доделай пак до 200 артов"). Outside the method's one-attempt-per-slot plan, so they are
kept in their own ledger table `reroll_attempts`, with receipts as <id>.reroll.json.

Each replacement uses the pack's latest prompt (v4 for pack 09, v2 for pack 10) with an
adjusted item text (pack 09: without the words that turned items into vehicles; pack 10:
naming the book construction) and a new seed. Same reserve -> one call -> receipt flow.
Usage: reroll.py [PACK]   (processes REROLLS, optionally one pack; skips ones already attempted)
"""
import base64
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid

import pixellab_mcp as mcp
from build_prompts_v2 import prompt as prompt_v2
from build_prompts_v4_pack09 import prompt as prompt_v4

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROD = os.path.join(ROOT, "production")
REROLLS = {
    "pack09_015_ship_mounted_navigation_lamp_miniature": "Brass navigation lamp with a teal glass lens",
    "pack09_034_small_airship_hull_tapping_hammer": "Small brass hull tapping hammer with a teak handle",
    "pack09_046_twin_cylinder_airship_engine_miniature": "Twin cylinder engine block miniature",
    "pack09_054_crystal_energized_propeller_shaft_coupler": "Propeller shaft coupler with a small crystal",
    "pack09_055_balloon_pressure_relief_spring_valve": "Pressure relief spring valve with a brass wheel",
    "pack09_096_windproof_treasure_satchel_with_double_buckles": "Windproof leather satchel bag with double buckles",
    "pack09_098_padded_bird_egg_shaped_navigation_cargo_pod": "Padded egg-shaped cargo pod with leather straps",
    "pack09_100_airship_freight_seal_made_of_blue_wax": "Round freight seal made of blue wax",
    "pack09_132_transparent_sky_coral_branching_relic": "Transparent branching coral relic",
    "pack09_144_brass_pocket_sky_telescope_with_shoulder_strap": "Single tube brass pocket telescope with a shoulder strap",
    "pack09_184_airship_master_engine_ignition_key": "Master engine ignition key with a brass bow",
    "pack09_200_final_flight_log_sealed_by_a_brass_propeller": "Final flight logbook sealed with a brass propeller emblem",
    "pack10_049_triptych_hinged_map_book_with_blue_panels": "Triptych map book standing open as three hinged blue panels",
    "pack10_053_pearl_inlaid_music_score_codex_without_text": "Tall narrow music score codex standing upright, pearl inlay on the spine, ribbon bookmarks hanging",
    "pack10_068_locking_metal_deed_storage_box": "Flat rectangular metal deed box with a hinged lid and a padlock hasp",
    "pack10_080_cloth_lined_crown_jewel_record_casket": "Low open casket lined with navy cloth, a velvet tray inside",
}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def main():
    plan = {}
    with open(os.path.join(ROOT, "method", "prompts_packs_08_10.jsonl"), encoding="utf-8") as f:
        for e in map(json.loads, f):
            plan[e["id"]] = e
    c = sqlite3.connect(os.path.join(PROD, "production_ledger.sqlite"), isolation_level=None)
    c.execute("""CREATE TABLE IF NOT EXISTS reroll_attempts (
        attempt_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(asset_id),
        request_id TEXT NOT NULL UNIQUE, request_sha256 TEXT NOT NULL, item_text TEXT NOT NULL,
        state TEXT NOT NULL, submitted_at TEXT, job_id TEXT UNIQUE, gallery_id TEXT,
        receipt_path TEXT, charged_units INTEGER, local_file TEXT, approval TEXT NOT NULL)""")
    jobs = {}
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    for asset, text in REROLLS.items():
        if only and plan[asset]["pack_number"] != only:
            continue
        if c.execute("SELECT 1 FROM reroll_attempts WHERE asset_id=?", (asset,)).fetchone():
            continue
        e = dict(plan[asset], name_en=text)
        build = prompt_v4 if e["pack_number"] == 9 else prompt_v2
        args = dict(e["args"], description=build(e), seed=e["args"]["seed"] + 1000000)
        sha = hashlib.sha256(json.dumps(args, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        rid = str(uuid.uuid4())
        aid = "reroll1_" + asset
        c.execute("INSERT INTO reroll_attempts(attempt_id,asset_id,request_id,request_sha256,item_text,state,"
                  "submitted_at,approval) VALUES(?,?,?,?,?,'submitting',?,?)",
                  (aid, asset, rid, sha, text, now(), "user: доделай пак до 200 артов / и пак 10 тоже доделай до 200"))
        keys = ("description", "width", "height", "no_background", "view", "direction", "outline", "detail", "seed")
        try:
            result, _ = mcp.call("create_image_pixen", {k: args[k] for k in keys}, timeout=90)
        except Exception as ex:
            c.execute("UPDATE reroll_attempts SET state='ambiguous' WHERE attempt_id=?", (aid,))
            print("AMBIGUOUS", asset, repr(ex)[:200])
            break
        rpath = os.path.join(PROD, "receipts", asset + ".reroll.json")
        with open(rpath + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"attempt_id": aid, "request_id": rid, "request_sha256": sha, "arguments": args,
                       "received_at": now(), "result": result}, f, ensure_ascii=False)
        os.replace(rpath + ".tmp", rpath)
        job = (result.get("structuredContent") or {}).get("job_id")
        if not job:
            c.execute("UPDATE reroll_attempts SET state='ambiguous', receipt_path=? WHERE attempt_id=?",
                      (os.path.relpath(rpath, ROOT), aid))
            print("AMBIGUOUS (no job id)", asset, mcp.text_of(result)[:200])
            break
        c.execute("UPDATE reroll_attempts SET state='submitted', job_id=?, receipt_path=? WHERE attempt_id=?",
                  (job, os.path.relpath(rpath, ROOT), aid))
        jobs[aid] = (asset, job)
        print("submitted", asset, job, flush=True)
    for aid, asset, job in c.execute("SELECT attempt_id, asset_id, job_id FROM reroll_attempts WHERE state='submitted'").fetchall():
        jobs[aid] = (asset, job)
    while jobs:
        for aid, (asset, job) in list(jobs.items()):
            result, _ = mcp.call("get_image", {"job_id": job}, timeout=90)
            status = (result.get("structuredContent") or {}).get("status")
            imgs = mcp.images_of(result)
            if status == "completed" and imgs:
                png = base64.b64decode(imgs[0]["data"])
                out = os.path.join(PROD, "rerolls", plan[asset]["filename"])
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "wb") as f:
                    f.write(png)
                gal = (result.get("structuredContent") or {}).get("asset_id")
                c.execute("UPDATE reroll_attempts SET state='completed', gallery_id=?, charged_units=1, local_file=? "
                          "WHERE attempt_id=?", (gal, os.path.relpath(out, ROOT), aid))
                del jobs[aid]
                print("done", asset, flush=True)
            elif status == "failed" or result.get("isError"):
                c.execute("UPDATE reroll_attempts SET state='failed' WHERE attempt_id=?", (aid,))
                del jobs[aid]
                print("FAILED", asset)
        time.sleep(5)
    print(c.execute("SELECT state, COUNT(*), COALESCE(SUM(charged_units),0) FROM reroll_attempts GROUP BY 1").fetchall())


if __name__ == "__main__":
    main()
