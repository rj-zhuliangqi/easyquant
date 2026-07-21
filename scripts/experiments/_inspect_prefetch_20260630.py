#!/usr/bin/env python3
"""Inspect the prefetch JSON file."""
import json
import sys

path = "/tmp/easyquant_market_data_2026-06-30.json"
with open(path) as f:
    d = json.load(f)

print("=== META ===")
print(json.dumps(d.get("meta", {}), ensure_ascii=False, indent=2))

print("\n=== MARKET INDICES (top-level keys) ===")
mi = d.get("market_indices") or {}
print("Type:", type(mi).__name__, "keys:", list(mi.keys())[:40] if isinstance(mi, dict) else f"len={len(mi)}")
if isinstance(mi, dict):
    for k, v in list(mi.items())[:20]:
        if isinstance(v, dict):
            sample = {kk: vv for kk, vv in v.items() if kk in ("name", "current", "change_percent", "change", "open", "close", "high", "low", "pre_close")}
            print(f"  {k}: {sample}")
        elif isinstance(v, list):
            print(f"  {k}: list len={len(v)}; first={v[0] if v else None}")

print("\n=== SECTOR RANKINGS (top-level keys) ===")
sr = d.get("sector_rankings") or {}
print("Type:", type(sr).__name__, "keys:", list(sr.keys())[:20] if isinstance(sr, dict) else f"len={len(sr)}")
if isinstance(sr, dict):
    for k, v in list(sr.items())[:5]:
        if isinstance(v, list):
            print(f"  {k}: list len={len(v)}; first sample={v[0] if v else None}")

print("\n=== INDIVIDUAL RANKINGS ===")
ir = d.get("individual_rankings") or {}
print("Type:", type(ir).__name__, "keys:", list(ir.keys())[:20] if isinstance(ir, dict) else f"len={len(ir)}")

print("\n=== LIMIT-UP POOL ===")
lu = d.get("limit_up_pool") or {}
print("Type:", type(lu).__name__, "keys:", list(lu.keys())[:20] if isinstance(lu, dict) else f"len={len(lu)}")

print("\n=== MONITOR SIGNALS ===")
ms = d.get("monitor_signals") or {}
print("Type:", type(ms).__name__, "keys:", list(ms.keys())[:20] if isinstance(ms, dict) else f"len={len(ms)}")

print("\n=== OPPORTUNITIES ===")
op = d.get("opportunities") or {}
print("Type:", type(op).__name__, "keys:", list(op.keys())[:20] if isinstance(op, dict) else f"len={len(op)}")