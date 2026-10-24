#!/usr/bin/env python3
"""Prompt version 4 for still-unsent slots of pack 09.

v3 (slots 051-060) still turned parts into blimps and small planes: the words "sky" and
"airship" in the shared text pull the whole object toward a vehicle. v4 keeps the item
text as planned and frames it as a small workshop part or hand tool, without those words
in the shared part. Writes method/prompts_v4_pack09.jsonl.
"""
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V1 = os.path.join(ROOT, "method", "prompts_packs_08_10.jsonl")
V4 = os.path.join(ROOT, "method", "prompts_v4_pack09.jsonl")
STYLE = ("Adventure pixel art, dark walnut blue outlines, honey brass, weathered teak, "
         "pale canvas and muted teal accents, broad readable shapes, cheerful rather than grim")
MATERIALS = "brass, varnished teak, sail canvas, leather straps, lightweight wicker"


def prompt(e):
    return (f"{e['name_en']}. A single small workshop part, hand tool or personal belonging, "
            f"shown alone as an isolated inventory icon. {STYLE}. Made from {MATERIALS}, "
            "only where they suit this item. One centered object drawn as a compact pixel-art icon "
            "with generous empty space around it, the whole object inside the canvas. Front three-quarter "
            "view from slightly above, light from the upper left, one-pixel dark outline, crisp square "
            "pixel clusters, plain transparent background.")


if __name__ == "__main__":
    with open(V1, encoding="utf-8") as f, open(V4 + ".tmp", "w", encoding="utf-8") as out:
        for e in map(json.loads, f):
            if e["pack_number"] != 9:
                continue
            e = dict(e, prompt_version=4)
            e["prompt"] = prompt(e)
            e["args"] = dict(e["args"], description=e["prompt"])
            e["request_sha256"] = hashlib.sha256(
                json.dumps(e["args"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            out.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(V4 + ".tmp", V4)
