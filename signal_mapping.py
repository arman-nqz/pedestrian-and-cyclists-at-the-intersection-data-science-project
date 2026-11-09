#!/usr/bin/env python
"""Infer which signal group serves each crossing, from when pedestrians / cyclists step onto it.

    python signal_mapping.py          # reads dashboard/data, writes dashboard/config/signal_mapping.json

There is no official signal plan in the data, so this is an inference: for every crossing (zones.json) and every
independent pedestrian / cyclist signal group (F*, R1), it takes the share of crossing entries that start on green
minus how often that group is green at all. The best group wins if it is clearly better than the next one and at least
60% of entries start on its green. One clock offset for the whole junction is searched within +-10 s.
Check the result against the junction plan before using it in conclusions.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

import signals as sg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="dashboard/data")
    ap.add_argument("--variant", default="stitched", help="stitched keeps people who wait before crossing")
    ap.add_argument("--out", default="dashboard/config/signal_mapping.json")
    args = ap.parse_args(argv)
    d = Path(args.data)
    sig = pd.read_parquet(d / "signals.parquet")
    groups = json.loads((d / "signal_groups.json").read_text(encoding="utf-8"))
    vru_groups = {k: v for k, v in groups.items() if k.startswith(("F", "R"))}
    visits = pd.read_parquet(d / f"crossing_visits_{args.variant}.parquet")

    result = {"schema": 1, "method": __doc__.strip().splitlines()[2].strip(), "variant": args.variant, "crossings": {}}
    pd.set_option("display.width", 200)
    for classes in (("Pedestrian",), ("Cyclist",)):
        res = sg.infer_mapping(visits, sig, vru_groups, classes=classes)
        if res.empty:
            continue
        print(f"\n=== {classes[0]} ===")
        for crossing, sub in res.groupby("crossing"):
            sub = sub.sort_values("score", ascending=False)
            best, second = sub.iloc[0], sub.iloc[1] if len(sub) > 1 else None
            clear = (second is None or best["score"] >= second["score"] + 0.1) and best["green_share"] >= 0.6
            print(f"{crossing}: " + " | ".join(f"{r.group} score {r.score:+.2f} (green {r.green_share:.0%} vs {r.green_base:.0%}, lag {r.lag_s:+d}s)"
                                              for r in sub.head(3).itertuples()) + ("" if clear else "   <- not clear"))
            entry = result["crossings"].setdefault(crossing, {})
            entry[classes[0]] = {"group": best["group"], "members": best["members"].split(","), "score": round(float(best["score"]), 3),
                                 "green_share": round(float(best["green_share"]), 3), "green_base": round(float(best["green_base"]), 3),
                                 "lag_s": int(best["lag_s"]), "entries": int(best["entries"]), "clear": bool(clear),
                                 "runner_up": None if second is None else {"group": second["group"], "score": round(float(second["score"]), 3)}}
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\nwritten {args.out}")


if __name__ == "__main__":
    main()
