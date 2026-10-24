#!/usr/bin/env python
"""Split a manifest into per-sub-agent batches.

    python slice.py --manifest work_L12/manifest_L12.json --out work_L12/batches --size 36
"""
import argparse, json, os


def slice_manifest(manifest, outdir, size):
    d = json.load(open(manifest, encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    outs = []
    for k in range(0, len(d), size):
        chunk = d[k:k + size]
        a, b = chunk[0]["n"], chunk[-1]["n"]
        p = os.path.join(outdir, f"batch_{a:03d}_{b:03d}.json")
        json.dump(chunk, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        outs.append((p, a, b))
    return outs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=36)
    a = ap.parse_args()
    for p, s, e in slice_manifest(a.manifest, a.out, a.size):
        print(p, s, e)
