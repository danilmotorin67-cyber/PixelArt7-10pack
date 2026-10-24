#!/usr/bin/env python3
"""Paid Pixen submissions for packs 08-10, following METHOD_GUIDE_RU.md section 7.

Submissions go through the PixelLab MCP tool create_image_pixen, which returns a
job id immediately (the synchronous REST endpoint lost a charged response to a
30 s proxy cut, see production/receipts/*.recovery.json).

One slot = at most one paid call. Every call is reserved in the SQLite ledger
before it is sent; its full response is written to receipts/ (temp file +
atomic rename) and the ledger updated before the next paid call starts.
Paid calls are sequential with at most 8 own jobs in flight; results are
fetched with the free get_image.

Usage: generate.py ASSET_ID [...] | --pack 8 [--category evidence] | --reconcile
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import uuid

import pixellab_mcp as mcp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROD = os.path.join(ROOT, "production")
DB = os.path.join(PROD, "production_ledger.sqlite")
RECEIPTS = os.path.join(PROD, "receipts")
RAW = os.path.join(PROD, "raw")
PROMPT_FILES = [os.path.join(ROOT, "method", "prompts_packs_08_10.jsonl"),
                os.path.join(ROOT, "method", "prompts_v2_packs_08_10.jsonl")]
PACK_LIMIT = 200
MAX_IN_FLIGHT = 8
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_prompts():
    """Latest prompt version per asset wins (v2 file overrides v1 for unsent slots)."""
    out = {}
    for path in PROMPT_FILES:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for e in map(json.loads, f):
                    if e["id"] not in out or e["prompt_version"] > out[e["id"]]["prompt_version"]:
                        out[e["id"]] = e
    return out


def connect():
    c = sqlite3.connect(DB, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA synchronous=FULL")
    return c


def event(c, asset_id, kind, detail):
    c.execute("INSERT INTO events(asset_id,event_time,event_type,detail_json) VALUES(?,?,?,?)",
              (asset_id, now(), kind, json.dumps(detail, ensure_ascii=False)))


def atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def reconcile(c):
    """A 'submitting' attempt left by a crash becomes 'ambiguous', never 'planned' again."""
    for (aid, asset) in c.execute("SELECT attempt_id, asset_id FROM attempts WHERE state='submitting'").fetchall():
        c.execute("UPDATE attempts SET state='ambiguous', notes='interrupted while submitting' WHERE attempt_id=?", (aid,))
        c.execute("UPDATE assets SET state='ambiguous' WHERE asset_id=?", (asset,))
        event(c, asset, "reconciled_ambiguous", {"attempt_id": aid})
        print("AMBIGUOUS after interruption:", asset)


def submit(c, entry):
    asset = entry["id"]
    row = c.execute("SELECT pack_number FROM assets WHERE asset_id=?", (asset,)).fetchone()
    if row is None:
        raise SystemExit("unknown asset " + asset)
    if c.execute("SELECT 1 FROM attempts WHERE asset_id=?", (asset,)).fetchone():
        return "skip"
    if os.path.exists(os.path.join(RECEIPTS, asset + ".json")):
        print("skip (receipt on disk without attempt - reconcile)", asset)
        return "skip"
    used = c.execute("SELECT COUNT(*) FROM attempts JOIN assets USING(asset_id) WHERE pack_number=?",
                     (row[0],)).fetchone()[0]
    if used >= PACK_LIMIT:
        raise SystemExit("pack limit reached")

    a = entry["args"]
    arguments = {k: a[k] for k in ("description", "width", "height", "no_background",
                                   "view", "direction", "outline", "detail", "seed")}
    attempt_id = "att_" + asset
    request_id = str(uuid.uuid4())
    c.execute("BEGIN IMMEDIATE")
    c.execute("INSERT INTO attempts(attempt_id,asset_id,request_id,request_sha256,state,reserved_units,submitted_at,notes) "
              "VALUES(?,?,?,?,'submitting',1,?,?)",
              (attempt_id, asset, request_id, entry["request_sha256"], now(),
               json.dumps({"prompt_version": entry["prompt_version"], "via": "mcp create_image_pixen"})))
    c.execute("INSERT INTO budget_reservations(attempt_id,units,state) VALUES(?,1,'held')", (attempt_id,))
    c.execute("UPDATE assets SET state='submitting' WHERE asset_id=?", (asset,))
    event(c, asset, "reserved", {"request_id": request_id, "seed": a["seed"], "prompt_version": entry["prompt_version"]})
    c.execute("COMMIT")

    try:
        result, raw = mcp.call("create_image_pixen", arguments, timeout=90)
    except Exception as e:
        c.execute("UPDATE attempts SET state='ambiguous', notes=? WHERE attempt_id=?", (repr(e)[:500], attempt_id))
        c.execute("UPDATE assets SET state='ambiguous' WHERE asset_id=?", (asset,))
        event(c, asset, "ambiguous", {"error": repr(e)[:500]})
        print("AMBIGUOUS", asset, repr(e)[:200])
        return "ambiguous"

    receipt = {"asset_id": asset, "attempt_id": attempt_id, "request_id": request_id,
               "request_sha256": entry["request_sha256"], "prompt_version": entry["prompt_version"],
               "tool": "create_image_pixen", "arguments": arguments, "received_at": now(), "result": result}
    path = os.path.join(RECEIPTS, asset + ".json")
    atomic_write(path, json.dumps(receipt, ensure_ascii=False).encode())

    sc = result.get("structuredContent") or {}
    job_id = sc.get("job_id")
    if not job_id:
        m = re.search(r"job[_ ]id\W+(" + UUID_RE.pattern + ")", mcp.text_of(result))
        job_id = m.group(1) if m else None
    if result.get("isError") or not job_id:
        c.execute("UPDATE attempts SET state='ambiguous', receipt_path=?, notes=? WHERE attempt_id=?",
                  (os.path.relpath(path, ROOT), "no job id: " + mcp.text_of(result)[:400], attempt_id))
        c.execute("UPDATE assets SET state='ambiguous' WHERE asset_id=?", (asset,))
        event(c, asset, "ambiguous", {"text": mcp.text_of(result)[:400]})
        print("AMBIGUOUS (no job id)", asset, mcp.text_of(result)[:300])
        return "ambiguous"
    c.execute("UPDATE attempts SET state='submitted', job_id=?, receipt_path=? WHERE attempt_id=?",
              (job_id, os.path.relpath(path, ROOT), attempt_id))
    c.execute("UPDATE assets SET state='submitted' WHERE asset_id=?", (asset,))
    event(c, asset, "submitted", {"job_id": job_id})
    print("submitted", asset, job_id, flush=True)
    return "ok"


def poll(c, prompts):
    """Free reads: fetch finished jobs. Returns number still in flight."""
    rows = c.execute("SELECT attempt_id, asset_id, job_id FROM attempts WHERE state='submitted'").fetchall()
    for attempt_id, asset, job_id in rows:
        try:
            result, _ = mcp.call("get_image", {"job_id": job_id}, timeout=90)
        except Exception as e:
            print("poll error", asset, repr(e)[:120])
            continue
        text = mcp.text_of(result)
        status = (result.get("structuredContent") or {}).get("status") or \
            (re.search(r"status:\s*(\w+)", text) or [None, None])[1]
        imgs = mcp.images_of(result)
        if status == "completed" and imgs:
            png = base64.b64decode(imgs[0]["data"])
            raw_path = os.path.join(RAW, prompts[asset]["filename"])
            atomic_write(raw_path, png)
            gallery = (result.get("structuredContent") or {}).get("asset_id")
            if not gallery:
                m = re.search(r"asset_id:\s*(" + UUID_RE.pattern + ")", text)
                gallery = m.group(1) if m else None
            for im in imgs:
                im["data"] = "<saved %s sha256=%s>" % (os.path.relpath(raw_path, ROOT), hashlib.sha256(png).hexdigest())
            rpath = os.path.join(RECEIPTS, asset + ".result.json")
            atomic_write(rpath, json.dumps({"asset_id": asset, "job_id": job_id, "received_at": now(),
                                            "result": result}, ensure_ascii=False).encode())
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE attempts SET state='completed', gallery_id=?, charged_units=1 WHERE attempt_id=?",
                      (gallery, attempt_id))
            c.execute("UPDATE budget_reservations SET state='settled' WHERE attempt_id=?", (attempt_id,))
            c.execute("UPDATE assets SET state='generated', local_file=? WHERE asset_id=?",
                      (os.path.relpath(raw_path, ROOT), asset))
            event(c, asset, "completed", {"gallery_id": gallery, "png_sha256": hashlib.sha256(png).hexdigest()})
            c.execute("COMMIT")
            print("done", asset, flush=True)
        elif status == "failed" or result.get("isError"):
            rpath = os.path.join(RECEIPTS, asset + ".result.json")
            atomic_write(rpath, json.dumps({"asset_id": asset, "job_id": job_id, "received_at": now(),
                                            "result": result}, ensure_ascii=False).encode())
            c.execute("UPDATE attempts SET state='failed', notes=? WHERE attempt_id=?", (text[:500], attempt_id))
            c.execute("UPDATE assets SET state='failed' WHERE asset_id=?", (asset,))
            event(c, asset, "job_failed", {"text": text[:500]})
            print("FAILED job", asset, text[:200], flush=True)
    return c.execute("SELECT COUNT(*) FROM attempts WHERE state='submitted'").fetchone()[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--pack", type=int)
    ap.add_argument("--category")
    ap.add_argument("--reconcile", action="store_true")
    a = ap.parse_args()
    prompts = load_prompts()
    c = connect()
    reconcile(c)
    ids = list(a.ids)
    if a.pack:
        ids += sorted(k for k, e in prompts.items() if e["pack_number"] == a.pack
                      and (not a.category or e["category_id"] == a.category))
    if a.reconcile:
        ids = []
    for asset in ids:
        while poll(c, prompts) >= MAX_IN_FLIGHT:
            time.sleep(5)
        res = submit(c, prompts[asset])
        if res == "ambiguous":
            print("stopping on ambiguous result; reconcile before continuing")
            break
    while poll(c, prompts):
        time.sleep(5)
    print(json.dumps(dict(zip(["attempts", "confirmed_charged", "held", "occupied", "ambiguous", "accepted"],
                              c.execute("SELECT * FROM budget_summary").fetchone()))))


if __name__ == "__main__":
    main()
