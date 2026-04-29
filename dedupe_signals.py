#!/usr/bin/env python3
import json, sys
from collections import OrderedDict

def dedupe(records):
    seen = set()
    out = []
    for r in records:
        k = (r.get("trade_date"), r.get("ticker"), r.get("framework") or r.get("pattern"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out

if __name__ == "__main__":
    inp = sys.argv[1]
    outp = sys.argv[2]
    with open(inp, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "signals" in data:
        data["signals"] = dedupe(data["signals"])
    elif isinstance(data, list):
        data = dedupe(data)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {outp}")
