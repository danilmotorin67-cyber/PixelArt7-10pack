#!/usr/bin/env python3
"""Prompt version 3 for still-unsent slots of pack 09 only.

Review of pack 09 slots 1-40 (v2) found the phrase "inventory item from the world of
Sky Pirates & Floating Isles" turning tools into ships, airships and floating islands
(005, 015, 024, 029, 003, 018) and painting island scenery instead of a transparent
background (011, 022, 032); "blue sky crystals" put blue gems on most items. v3 drops
the world name and that material, and frames each item as a loose crew tool.
Writes method/prompts_v3_pack09.jsonl; generate.py uses the highest version per slot.
"""
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V1 = os.path.join(ROOT, "method", "prompts_packs_08_10.jsonl")
V3 = os.path.join(ROOT, "method", "prompts_v3_pack09.jsonl")
STYLE = ("Sky adventure pixel art, dark walnut blue outlines, honey brass, weathered teak, "
         "pale canvas and muted cloud teal, broad readable shapes, adventurous rather than grim")
MATERIALS = "brass, varnished teak, sail canvas, leather straps, lightweight wicker"


def prompt(e):
    return (f"{e['name_en']}. One loose piece of airship crew equipment, shown alone as an isolated "
            f"inventory icon. {STYLE}. Made from {MATERIALS}, only where they suit this item. "
            "One centered object drawn as a compact pixel-art icon with generous empty space around it, "
            "the whole object inside the canvas. Front three-quarter view from slightly above, "
            "light from the upper left, one-pixel dark outline, crisp square pixel clusters, "
            "plain transparent background.")


with open(V1, encoding="utf-8") as f, open(V3 + ".tmp", "w", encoding="utf-8") as out:
    for e in map(json.loads, f):
        if e["pack_number"] != 9:
            continue
        e = dict(e, prompt_version=3)
        e["prompt"] = prompt(e)
        e["args"] = dict(e["args"], description=e["prompt"])
        e["request_sha256"] = hashlib.sha256(
            json.dumps(e["args"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        out.write(json.dumps(e, ensure_ascii=False) + "\n")
os.replace(V3 + ".tmp", V3)
