"""Minimal JSON-RPC client for the PixelLab MCP server (auth is injected by the session proxy)."""
import itertools
import json

import requests

URL = "https://api.pixellab.ai/mcp"
_ids = itertools.count(1)


def call(tool, arguments, timeout=120):
    """Return (result_dict, raw_text). Raises on transport errors."""
    body = {"jsonrpc": "2.0", "id": next(_ids), "method": "tools/call",
            "params": {"name": tool, "arguments": arguments}}
    r = requests.post(URL, json=body, timeout=timeout,
                      headers={"Accept": "application/json, text/event-stream"})
    r.raise_for_status()
    raw = r.text
    for line in raw.splitlines():
        if line.startswith("data:"):
            msg = json.loads(line[5:])
            if "error" in msg:
                raise RuntimeError("MCP error: %s" % msg["error"])
            return msg["result"], raw
    raise RuntimeError("no data line in MCP response: %r" % raw[:500])


def text_of(result):
    return "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")


def images_of(result):
    return [c for c in result.get("content", []) if c.get("type") == "image"]
