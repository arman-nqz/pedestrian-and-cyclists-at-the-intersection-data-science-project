#!/usr/bin/env python
"""NSE vs Ouster BlueCity comparison data for the four shared windows (config/analysis_windows.json).

    python build_comparison_data.py                 # all windows -> dashboard/data/compare/
    python build_comparison_data.py --windows W1    # one window

Per window: Ouster -> NSE transform (stability check), frame-by-frame matching in the area both systems cover,
detections per frame, matched shares, class confusion, distance histogram, counts per second, density per system,
and track counts per system before and after our cleaning pipeline. Each window uses its own transform (the Ouster
frame changed between W3 and W4, around the 08:18 Ouster recording); all are written to
dashboard/config/ouster_to_nse.json, with a warning when windows disagree.
NSE detections with a score below 0.25 are left out (as in the rest of the project). Ouster has no score filter.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import build_dashboard_data as bdd
import nse_ouster as no
import ouster_reader as orr
import track_pipeline as tp

CELL = 0.5


def load_window(w, nse_dir, ouster_dir, spans, min_score):
    t0, t1 = w["start_epoch_s"], w["end_epoch_s"]
    files = tp.list_files(nse_dir, "2026-10-29")
    h, m = (int(x) for x in w["start_local"].split(":"))
    start = f"{h:02d}:{m - m % 5:02d}"
    files = bdd.select_window(files, start, 15)  # file boundaries are 5-min aligned; take one extra
    n = tp.parse_files(files, progress=False)
    n = n[(n["t"] >= t0) & (n["t"] < t1) & (n["score"] >= min_score)].reset_index(drop=True)
    o = orr.read_window(ouster_dir, t0, t1, spans)
    return n, o


def density(d, system, wid):
    n = int(2 * no.LIM / CELL)
    ix = np.clip(((d["x"].to_numpy() + no.LIM) / CELL).astype(int), 0, n - 1)
    iy = np.clip(((d["y"].to_numpy() + no.LIM) / CELL).astype(int), 0, n - 1)
    g = pd.DataFrame({"group": no.group(d["class_name"].to_numpy()), "ix": ix, "iy": iy})
    out = g.groupby(["group", "ix", "iy"]).size().rename("rows").reset_index()
    out["dwell_s"] = (out["rows"] * 0.1).astype("float32")
    out["window"], out["system"] = wid, system
    return out.drop(columns="rows")


def counts_1s(d, system, wid, t0):
    s = pd.DataFrame({"second": ((d["t"] - t0) // 1).astype(int), "group": no.group(d["class_name"].to_numpy()),
                      "t": d["t"].to_numpy()})
    frames = s.groupby("second")["t"].nunique()
    c = s.groupby(["second", "group"]).size().rename("rows").reset_index()
    c["per_frame"] = c["rows"] / c["second"].map(frames)
    c["window"], c["system"] = wid, system
    return c.drop(columns="rows")


def track_counts(d, system, wid):
    rows = []
    raw = d.groupby("track_id").agg(cls=("class_name", lambda s: s.astype(str).mode().iat[0]), t0=("t", "min"), t1=("t", "max"))
    raw["group"] = no.group(raw["cls"].to_numpy())
    for g, sub in raw.groupby("group"):
        rows.append((wid, system, "raw ids", g, len(sub), float((sub["t1"] - sub["t0"]).median())))
    variants, _ = tp.make_variants(d.drop(columns=[c for c in ("ouster_class", "ouster_sub") if c in d]))
    for name in ("stitched", "clean"):
        tt = bdd.track_table(variants[name])
        tt["group"] = no.group(tt["cls"].to_numpy())
        for g, sub in tt.groupby("group"):
            rows.append((wid, system, name, g, len(sub), float(sub["duration_s"].median())))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nse-dir", default="database/newsense/object_list")
    ap.add_argument("--ouster-dir", default="database/ouster")
    ap.add_argument("--windows", nargs="+", default=None)
    ap.add_argument("--out", default="dashboard/data/compare")
    ap.add_argument("--min-score", type=float, default=bdd.MIN_SCORE)
    ap.add_argument("--min-rows", type=int, default=5, help="detections per 1 m cell (each system) for the common area")
    args = ap.parse_args(argv)
    t_start = time.perf_counter()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    windows = json.loads(Path("config/analysis_windows.json").read_text(encoding="utf-8"))["windows"]
    if args.windows:
        windows = [w for w in windows if w["id"] in args.windows]

    spans_path = out / "ouster_spans.json"
    if spans_path.exists():
        spans = {k: tuple(v) for k, v in json.loads(spans_path.read_text()).items()}
    else:
        print("reading Ouster file time spans ...")
        spans = {f.name: orr.file_span(f) for f in orr.files(args.ouster_dir)}
        spans_path.write_text(json.dumps(spans))

    loaded, transforms = {}, {}
    for w in windows:
        t0 = time.perf_counter()
        n, o = load_window(w, args.nse_dir, args.ouster_dir, spans, args.min_score)
        tr = no.estimate_transform(n, o)
        transforms[w["id"]] = tr
        loaded[w["id"]] = (n, o)
        print(f"{w['id']}: NSE {len(n):,} rows, Ouster {len(o):,} rows; transform {tr['rotation_deg']} deg "
              f"{tr['shift_m']} m, residual {tr['median_residual_m']} m ({time.perf_counter() - t0:.0f} s)", flush=True)

    # group windows whose transforms agree (within 1 deg and 0.5 m): each group is one Ouster frame
    frames_, ids = [], list(transforms)
    for k in ids:
        t = transforms[k]
        for fr in frames_:
            r = transforms[fr[0]]
            if abs(t["rotation_deg"] - r["rotation_deg"]) < 1 and np.hypot(*np.subtract(t["shift_m"], r["shift_m"])) < 0.5:
                fr.append(k)
                break
        else:
            frames_.append([k])
    bad = [k for k, t in transforms.items() if t["median_residual_m"] > 0.6 or t["vote_peak_ratio"] < 3]
    note = (f"Ouster frame changes between windows: groups {frames_}" if len(frames_) > 1 else "one Ouster frame for all windows")
    Path("dashboard/config/ouster_to_nse.json").write_text(json.dumps({
        "schema": 1, "formula": "q_nse = R(-rotation_deg) @ p_ouster + shift_m", "per_window": transforms,
        "frame_groups": frames_, "note": note, "low_quality_windows": bad,
        "method": "Hough voting on moving vehicle pairs + Kabsch refinement (nse_ouster.estimate_transform); clocks: 0 s offset",
    }, indent=1), encoding="utf-8")
    print(note, "| low quality:", bad or "none")

    summ, conf, hist, cnt, dens, masks, tracks = [], [], [], [], [], [], []
    for w in windows:
        wid, (n, o) = w["id"], loaded[w["id"]]
        on = no.to_nse(o, transforms[wid])
        mask = no.common_mask(n, on, min_rows=args.min_rows)
        jj, ii = np.nonzero(mask)
        masks.append(pd.DataFrame({"window": wid, "ix": ii, "iy": jj}))
        nm, om = n[no.in_mask(n, mask)], on[no.in_mask(on, mask)]
        m = no.match_frames(nm, om)
        nf = m["t"].nunique()
        s = no.summarize(m, nf)
        s["window"], s["frames"], s["common_area_m2"] = wid, nf, int(mask.sum())
        summ.append(s)
        c = pd.crosstab(m["nse_group"], m["ouster_group"]).stack().rename("n").reset_index()
        c["window"] = wid
        conf.append(c)
        mm = m.dropna(subset=["dist_m"])
        for g, sub in mm.groupby("nse_group"):
            h, e = np.histogram(sub["dist_m"], bins=np.arange(0, no.RADIUS_M + 0.05, 0.05))
            hist.append(pd.DataFrame({"window": wid, "group": g, "dist_m": e[:-1] + 0.025, "n": h}))
        cnt += [counts_1s(nm, "NSE", wid, w["start_epoch_s"]), counts_1s(om, "Ouster", wid, w["start_epoch_s"])]
        dens += [density(n, "NSE", wid), density(on, "Ouster", wid)]
        tracks += track_counts(nm, "NSE", wid) + track_counts(om, "Ouster", wid)
        print(f"{wid}: common area {int(mask.sum())} m2, {nf} frames matched")

    pd.concat(summ).to_parquet(out / "summary.parquet")
    pd.concat(conf).to_parquet(out / "confusion.parquet")
    pd.concat(hist).to_parquet(out / "dist_hist.parquet")
    pd.concat(cnt).to_parquet(out / "counts_1s.parquet")
    pd.concat(dens).to_parquet(out / "density.parquet")
    pd.concat(masks).to_parquet(out / "common_area.parquet")
    pd.DataFrame(tracks, columns=["window", "system", "stage", "group", "tracks", "median_duration_s"]).to_parquet(out / "tracks.parquet")
    (out / "meta.json").write_text(json.dumps({
        "schema": 1, "windows": windows, "transforms": transforms, "frame_groups": frames_, "min_score_nse": args.min_score,
        "radius_m": no.RADIUS_M,
        "min_rows_common_area": args.min_rows, "built_seconds": round(time.perf_counter() - t_start, 1)}, indent=1), encoding="utf-8")
    print(f"done in {time.perf_counter() - t_start:.0f} s -> {out}")


if __name__ == "__main__":
    main()
