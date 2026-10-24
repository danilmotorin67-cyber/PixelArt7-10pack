#!/usr/bin/env python3
"""Prompt version 2 for still-unsent slots of packs 08-10 (METHOD_GUIDE_RU.md section 5).

Pilot findings (12 pilots, v1): the negative list "Do not add wings, horns, eyes,
limbs, crystals..." pulled those very parts in (wings on 08_001, crystal horns on
08_121), and objects filled the canvas (9/12 with margin < 4 px). v2 drops every
negative list, shortens the boilerplate and asks for empty space around the object.
Same item text, seed and Pixen parameters; new prompt text and request hash.
"""
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V1 = os.path.join(ROOT, "method", "prompts_packs_08_10.jsonl")
V2 = os.path.join(ROOT, "method", "prompts_v2_packs_08_10.jsonl")
PLAN = os.path.join(ROOT, "method", "generation_plan.json")

packs = {p["number"]: p for p in json.load(open(PLAN, encoding="utf-8"))["packs"]}


def prompt(e):
    p = packs[e["pack_number"]]
    return (f"{e['name_en']}. A single inventory item from the world of {p['title']}. "
            f"{p['style']}. Made from {p['materials']}, only where they suit this item. "
            "One centered object drawn as a compact pixel-art icon with generous empty space around it, "
            "the whole object inside the canvas. Front three-quarter view from slightly above, "
            "light from the upper left, one-pixel dark outline, crisp square pixel clusters, "
            "plain transparent background.")


with open(V1, encoding="utf-8") as f, open(V2 + ".tmp", "w", encoding="utf-8") as out:
    for e in map(json.loads, f):
        e = dict(e)
        e["prompt_version"] = 2
        e["prompt"] = prompt(e)
        e["args"] = dict(e["args"], description=e["prompt"])
        e["request_sha256"] = hashlib.sha256(
            json.dumps(e["args"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        out.write(json.dumps(e, ensure_ascii=False) + "\n")
os.replace(V2 + ".tmp", V2)
