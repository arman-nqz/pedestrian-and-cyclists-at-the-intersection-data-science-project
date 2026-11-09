#!/usr/bin/env python
"""Does track stitching change the near-miss (TTC / PET-proxy) results?

Runs the existing near-miss functions (near_miss_analysis.py) on the same time window in four ways:

  published  the pipeline exactly as published (per-file chunks, original track ids)
  segmented  same functions, whole window at once; tracks split at time gaps > 1 s, one class per
             segment, no stitching                                                         (control)
  stitched   segmented + track stitching (track_stitching.py), one class per stitched track
  clean      stitched + drop tracks with < 3 frames or < 2 m of movement

Why `segmented` and not the raw ids: the sensor reuses a track_id for different objects minutes or hours
apart, so over a window longer than one file the id alone would glue unrelated objects together.

Usage:
    python compare_stitching.py --data-dir <folder with the 288 json files> --start 07:00 --minutes 60
    python compare_stitching.py --data-dir <folder> --start 07:00 --minutes 15 --skip-published
"""
import argparse
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import near_miss_analysis as nma
import track_stitching as tsx

FILE_RE = re.compile(r"_(\d{2})-(\d{2})_to_(\d{2})-(\d{2})\.json$")


def window_files(data_dir, start, minutes):
    h, m = [int(v) for v in start.split(":")]
    lo, hi = h * 60 + m, h * 60 + m + minutes
    out = []
    for p in sorted(Path(data_dir).glob("*.json")):
        mt = FILE_RE.search(p.name)
        if mt and lo <= int(mt.group(1)) * 60 + int(mt.group(2)) < hi:
            out.append(p)
    if not out:
        raise FileNotFoundError(f"no files for {start} + {minutes} min in {data_dir}")
    return out


def load_window(files):
    """JSON files -> one DataFrame, one row per object per frame."""
    import json
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        for frame in data["frames"]:
            ts = frame["frame_timestamp"]
            t = ts["seconds"] + ts["nanosec"] * 1e-9
            for o in frame["objects"]:
                b = o["bounding_box"]
                p, s, v = b["position"], b["scale"], o["velocity"]
                rows.append((t, o["track_id"], o["class_name"], p["x"], p["y"], v["x"], v["y"], b["yaw"], s["x"], s["y"]))
    return pd.DataFrame(rows, columns=["t", "track_id", "class_name", "x", "y", "vx", "vy", "yaw", "length", "width"])


def to_nma_schema(d, tid_col, cls_col):
    """Rows in the column layout the near_miss_analysis functions expect."""
    motor, vul = nma.CONFIG["MOTORIZED_CLASSES"], nma.CONFIG["VULNERABLE_CLASSES"]
    cls = d[cls_col].astype(str)
    cat = np.where(cls.isin(motor), nma.CAT_MOTOR, np.where(cls.isin(vul), nma.CAT_VUL, nma.CAT_OTHER))
    return pd.DataFrame({
        "ts": d["t"].to_numpy(), "tsl": "", "tid": d[tid_col].astype("int64").to_numpy(), "cls": cls.to_numpy(),
        "cat": cat, "x": d["x"].to_numpy(), "y": d["y"].to_numpy(), "vx": d["vx"].to_numpy(), "vy": d["vy"].to_numpy(),
        "r": 0.5 * np.hypot(d["length"].to_numpy(), d["width"].to_numpy()),
    })


def run_pipeline(tbl):
    """The existing near-miss functions on one table (whole window = one chunk)."""
    t0 = time.perf_counter()
    quality = defaultdict(int)
    df = nma.preprocess_chunk(tbl, quality)
    ttc_df = pd.DataFrame(nma.run_ttc_on_chunk(df))
    acc = nma.PETAccumulator()
    acc.update(df)
    pet_df = pd.DataFrame(acc.compute())
    events = nma.consolidate_ttc_events(ttc_df)
    tracks = df[["cls", "tid"]].drop_duplicates().groupby("cls").size().to_dict()
    return {"events": events, "pet_near_miss": 0 if pet_df.empty else int(pet_df["nm"].sum()),
            "tracks": tracks, "runtime_s": round(time.perf_counter() - t0, 1), "quality": dict(quality)}


def match_share(a, b, dt=1.0, dist=3.0):
    """Share of events in `a` that have an event in `b` within dt seconds and dist meters."""
    if a.empty:
        return np.nan
    if b.empty:
        return 0.0
    tb = b["event_start_timestamp"].to_numpy()
    order = np.argsort(tb)
    tb, xb, yb = tb[order], b["x_mid"].to_numpy()[order], b["y_mid"].to_numpy()[order]
    hit = 0
    for t, x, y in zip(a["event_start_timestamp"], a["x_mid"], a["y_mid"]):
        lo, hi = np.searchsorted(tb, t - dt), np.searchsorted(tb, t + dt, side="right")
        if hi > lo and (np.hypot(xb[lo:hi] - x, yb[lo:hi] - y) <= dist).any():
            hit += 1
    return hit / len(a)


def summarise(name, res):
    ev = res["events"]
    ped = ev[(ev["class_1"] == "Pedestrian") | (ev["class_2"] == "Pedestrian")] if len(ev) else ev
    cyc = ev[(ev["class_1"] == "Cyclist") | (ev["class_2"] == "Cyclist")] if len(ev) else ev
    return {
        "variant": name,
        "ttc_events": len(ev),
        "with_pedestrian": len(ped), "with_cyclist": len(cyc),
        "median_min_ttc_s": round(float(ev["min_ttc_sec"].median()), 3) if len(ev) else np.nan,
        "events_ttc_below_0.1s": int((ev["min_ttc_sec"] < 0.1).sum()) if len(ev) else 0,
        "pet_proxy_near_miss": res["pet_near_miss"],
        "tracks_pedestrian": res["tracks"].get("Pedestrian", 0), "tracks_cyclist": res["tracks"].get("Cyclist", 0),
        "tracks_car": res["tracks"].get("Car", 0),
        "runtime_s": res["runtime_s"],
    }


def make_figure(rows, results, out_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing, skipping figure")
        return
    names = [r["variant"] for r in rows]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    w = 0.38
    x = np.arange(len(names))
    axes[0].bar(x - w / 2, [r["with_pedestrian"] for r in rows], w, label="with pedestrian", color="tab:blue")
    axes[0].bar(x + w / 2, [r["with_cyclist"] for r in rows], w, label="with cyclist", color="tab:orange")
    axes[0].set(title="TTC near-miss events (TTC < 1.5 s)", xticks=x, xticklabels=names)
    axes[0].legend()
    axes[1].bar(x, [r["pet_proxy_near_miss"] for r in rows], color="tab:green")
    axes[1].set(title="PET-proxy near-miss events", xticks=x, xticklabels=names)
    axes[2].bar(x - w / 2, [r["tracks_pedestrian"] for r in rows], w, label="pedestrian tracks", color="tab:blue")
    axes[2].bar(x + w / 2, [r["tracks_cyclist"] for r in rows], w, label="cyclist tracks", color="tab:orange")
    axes[2].set(title="Tracks used", xticks=x, xticklabels=names)
    axes[2].legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=130)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--start", default="07:00", help="window start, local HH:MM")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--output-dir", default="output/stitching_comparison")
    ap.add_argument("--skip-published", action="store_true", help="skip the run of the published pipeline")
    ap.add_argument("--min-frames", type=int, default=3)
    ap.add_argument("--min-extent-m", type=float, default=2.0)
    args = ap.parse_args(argv)

    files = window_files(args.data_dir, args.start, args.minutes)
    label = f"{args.start.replace(':', '')}_{args.minutes}min"
    out = Path(args.output_dir) / label
    out.mkdir(parents=True, exist_ok=True)
    print(f"window {args.start} + {args.minutes} min: {len(files)} files -> {out}")

    results = {}
    if not args.skip_published:
        t0 = time.perf_counter()
        ttc_df, pet_df, stats = nma.main(["--files", *[p.name for p in files], "--data-dir", args.data_dir,
                                          "--output-dir", str(out / "published_run"), "--no-plots"])
        results["published"] = {"events": nma.consolidate_ttc_events(ttc_df), "pet_near_miss": int(pet_df["nm"].sum()) if len(pet_df) else 0,
                                "tracks": stats["class_distribution"], "runtime_s": round(time.perf_counter() - t0, 1)}

    print("loading window ...")
    d = load_window(files)
    print(f"{len(d):,} rows")

    print("segmenting and stitching ...")
    t0 = time.perf_counter()
    seg, links = tsx.stitch_tracks(d)
    n_seg = seg["trk"].nunique()
    stitch_info = {"segments": n_seg, "joins": len(links), "tracks_after": seg["trk_s"].nunique(),
                   "stitch_runtime_s": round(time.perf_counter() - t0, 1)}
    print(stitch_info)

    # Control: tracks split at time gaps (the sensor reuses track ids for different objects minutes apart,
    # so the original id alone cannot be used over a long window), but NOT stitched.
    print("variant: segmented")
    results["segmented"] = run_pipeline(to_nma_schema(seg, "trk", "class_seg"))

    print("variant: stitched")
    results["stitched"] = run_pipeline(to_nma_schema(seg, "trk_s", "class_final"))

    print("variant: clean")
    g = seg.groupby("trk_s")
    ext = np.hypot(g["x"].max() - g["x"].min(), g["y"].max() - g["y"].min())
    keep = g.size().index[(g.size() >= args.min_frames) & (ext >= args.min_extent_m)]
    results["clean"] = run_pipeline(to_nma_schema(seg[seg["trk_s"].isin(keep)], "trk_s", "class_final"))

    rows = [summarise(k, v) for k, v in results.items()]
    table = pd.DataFrame(rows)
    table.to_csv(out / "summary.csv", index=False)
    for k, v in results.items():
        v["events"].to_csv(out / f"ttc_events_{k}.csv", index=False)

    ref = results["segmented"]["events"]
    overlap = pd.DataFrame([{"variant": k, "share_of_segmented_events_also_found": match_share(ref, v["events"]),
                             "share_of_its_events_also_in_segmented": match_share(v["events"], ref)}
                            for k, v in results.items() if k != "segmented"])
    overlap.to_csv(out / "event_overlap_vs_segmented.csv", index=False)
    pd.Series(stitch_info).to_json(out / "stitch_info.json")
    make_figure(rows, results, out / "comparison.png")

    pd.set_option("display.width", 200)
    print("\n" + table.to_string(index=False))
    print("\nevent overlap (events matched within 1 s and 3 m):\n" + overlap.to_string(index=False))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
