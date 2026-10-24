#!/usr/bin/env python
"""Validate annotation JSON against the manifest.

    python check.py --manifest work_L12/manifest_L12.json --ann "work_L12/ann_*.json"
"""
import argparse, glob, json


def check(manifest, pattern, tol=1.02):
    man = {r["n"]: r for r in json.load(open(manifest, encoding="utf-8"))}
    ann, dup = {}, []
    for p in sorted(glob.glob(pattern)):
        for r in json.load(open(p, encoding="utf-8"))["pages"]:
            if r["n"] in ann:
                dup.append(r["n"])
            ann[r["n"]] = r
    missing = sorted(set(man) - set(ann))
    extra = sorted(set(ann) - set(man))
    over = []
    for n, a in ann.items():
        if a.get("drop"):
            continue
        tot = sum(len(x["s"]) for x in a.get("notes", []))
        if tot > man[n]["cap"] * tol:
            over.append((n, tot, man[n]["cap"]))
    drops = sorted(n for n, a in ann.items() if a.get("drop"))
    merges = sorted((n, a.get("merge")) for n, a in ann.items()
                    if a.get("merge") not in (None, "none"))
    supp = sorted(n for n, a in ann.items() if a.get("supp"))
    notitle = sorted(n for n, a in ann.items() if not a.get("drop") and not a.get("title"))
    print(f"pages {len(man)} / annotated {len(ann)}  missing {missing}  extra {extra}  dup {dup}")
    print(f"drop   {len(drops)}: {drops}")
    print(f"merge  {merges}")
    print(f"supp   {supp}")
    print(f"over-cap {over}")
    print(f"no-title {notitle}")
    ok = not missing and not extra and not dup and not over and not notitle
    print("OK" if ok else "NEEDS FIX")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--ann", required=True)
    a = ap.parse_args()
    raise SystemExit(0 if check(a.manifest, a.ann) else 1)
