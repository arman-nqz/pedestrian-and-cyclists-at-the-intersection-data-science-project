#!/usr/bin/env python
"""Build the data files the dashboard reads (see docs/DASHBOARD_SPEC.md, section 5).

    python build_dashboard_data.py                       # 29 Oct 2026, NSE, from database/newsense/object_list
    python build_dashboard_data.py --start 07:20 --minutes 10 --out dashboard/data_test   # quick test on window W1

Steps (all by default, pick with --steps):
    tracks   tracks_<variant>.parquet            one row per track, for the three cleaning variants
    counts   counts_15min_<variant>.parquet      tracks started / present per 15 minutes and class
    density  density_<variant>.parquet           dwell seconds per 0.5 m cell, class and hour
    events   events_published_*.parquet          near-miss events of the original pipeline (from its CSV files)
    quality  quality.json                        stage counts, sensitivity table, stitching summary and test
    replay   replay/<variant>/<HHMM>.json.gz     5-minute chunks for the replay player
    meta     meta.json                           parameters, counts, build time, git commit

Events recomputed on our own tracks (slow, about an hour per variant) are optional: --compute-events clean stitched
Only `clean` is written for the replay by default (--replay-variants clean stitched segmented for more).
"""
import argparse
import gzip
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import track_pipeline as tp
import track_stitching as tsx

SCHEMA = 1
UTC_OFFSET_S = 3600          # set in main() from the data; 29 Oct 2026 is CET (UTC+1)
DAY = "2026-10-29"
MIN_SCORE = 0.25             # NSE detection score threshold, same as near_miss_analysis.py
# approximate sunrise / sunset in Aschaffenburg (local time), for shading only
DAYLIGHT = {"2026-10-29": ("07:13", "16:57"), "2026-10-28": ("07:11", "16:59"), "2026-10-14": ("07:40", "18:35")}
CLASSES = ["Pedestrian", "Cyclist", "Motorcycle", "Car", "Van", "Truck", "Bus"]
VRU = ["Pedestrian", "Cyclist", "Motorcycle"]
LIM = 46.0                   # half size of the map in meters
CELL = 0.5                   # density cell in meters
DT = 0.1                     # nominal frame time (10 Hz)
FILE_RE = re.compile(r"_(\d{2})-(\d{2})_to_(\d{2})-(\d{2})\.json$")


def local_s(t):
    """Epoch seconds -> local seconds of the day."""
    return (np.asarray(t, dtype="float64") + UTC_OFFSET_S) % 86400


# ------------------------------------------------------------------ tables
def track_table(v):
    """One row per track of a variant frame (sorted by trk, t)."""
    g = v.groupby("trk")
    same = v["trk"].eq(v["trk"].shift()).to_numpy()
    step = np.where(same, np.hypot(v["x"].diff().to_numpy(), v["y"].diff().to_numpy()), 0.0)
    path = pd.Series(step, index=v.index).groupby(v["trk"]).sum()
    speed = pd.Series(np.hypot(v["vx"].to_numpy(), v["vy"].to_numpy()), index=v.index).groupby(v["trk"]).mean()
    first, last = g[["t", "x", "y"]].first(), g[["t", "x", "y"]].last()
    tt = pd.DataFrame({
        "cls": g["cls"].first(),
        "t_start": first["t"], "t_end": last["t"], "frames": g.size(),
        "n_segments": g["seg_id"].nunique(),
        "path_m": path, "mean_speed": speed,
        "extent_m": np.hypot(g["x"].max() - g["x"].min(), g["y"].max() - g["y"].min()),
        "length_m": g["length"].median(), "width_m": g["width"].median(),
        "x_start": first["x"], "y_start": first["y"], "x_end": last["x"], "y_end": last["y"],
    })
    tt["duration_s"] = tt["t_end"] - tt["t_start"]
    tt.index.name = "trk"
    return tt.reset_index()


def counts_15min(tt):
    """Per class, entry arm ('all' = every track) and 15-minute bin: tracks that start in the bin, tracks present."""
    rows = []
    arms = ["all"] + (sorted(tt["arm_in"].dropna().unique().tolist()) if "arm_in" in tt else [])
    for cls in CLASSES:
        for arm in arms:
            sub = tt[tt["cls"] == cls]
            if arm != "all":
                sub = sub[sub["arm_in"] == arm]
            s = (local_s(sub["t_start"]) // 900).astype(int)
            e = np.maximum((local_s(sub["t_end"]) // 900).astype(int), s)
            started = np.bincount(s, minlength=96)[:96]
            span = e - s + 1
            present = np.bincount(np.repeat(s, span) + (np.arange(span.sum()) - np.repeat(np.cumsum(span) - span, span)),
                                  minlength=96)[:96]
            for b in range(96):
                rows.append((cls, arm, b, int(started[b]), int(present[b])))
    return pd.DataFrame(rows, columns=["cls", "arm", "bin", "started", "present"])


def add_zones(tt, v, zones_path):
    """Entry / exit arm and the crossings each track uses (needs zones.json from zones.py)."""
    import zones as zn
    zones = json.loads(Path(zones_path).read_text(encoding="utf-8"))
    tt["arm_in"] = zn.arm_of(tt["x_start"], tt["y_start"], zones)
    tt["arm_out"] = zn.arm_of(tt["x_end"], tt["y_end"], zones)
    cid = zn.crossing_of(v["x"].to_numpy(), v["y"].to_numpy(), zones)
    used = pd.DataFrame({"trk": v["trk"].to_numpy(), "c": cid}).dropna()
    used = used.drop_duplicates().groupby("trk")["c"].agg(lambda s: ",".join(sorted(s)))
    tt["crossings"] = tt["trk"].map(used).fillna("")
    return tt, crossing_visits(v, cid)


def crossing_visits(v, cid, max_gap_s=1.0):
    """One row per stay of a track inside a crossing: trk, cls, crossing, t_enter, t_exit, mean speed."""
    d = pd.DataFrame({"trk": v["trk"].to_numpy(), "cls": v["cls"].to_numpy(), "t": v["t"].to_numpy(), "c": cid,
                      "speed": np.hypot(v["vx"].to_numpy(), v["vy"].to_numpy())})
    d = d[d["c"].notna()]
    if d.empty:
        return pd.DataFrame(columns=["trk", "cls", "crossing", "t_enter", "t_exit", "duration_s", "mean_speed"])
    new = (d["trk"].ne(d["trk"].shift()) | d["c"].ne(d["c"].shift()) | (d["t"].diff() > max_gap_s)).cumsum()
    g = d.groupby(new)
    out = pd.DataFrame({"trk": g["trk"].first(), "cls": g["cls"].first(), "crossing": g["c"].first(),
                        "t_enter": g["t"].min(), "t_exit": g["t"].max(), "mean_speed": g["speed"].mean()})
    out["duration_s"] = out["t_exit"] - out["t_enter"]
    return out.reset_index(drop=True)


def density(v):
    """Dwell seconds (rows * 0.1 s) per class, local hour and 0.5 m cell."""
    n = int(2 * LIM / CELL)
    ix = np.clip(((v["x"].to_numpy() + LIM) / CELL).astype(int), 0, n - 1)
    iy = np.clip(((v["y"].to_numpy() + LIM) / CELL).astype(int), 0, n - 1)
    hour = (local_s(v["t"]) // 3600).astype(int)
    d = pd.DataFrame({"cls": v["cls"].to_numpy(), "hour": hour, "ix": ix, "iy": iy})
    out = d.groupby(["cls", "hour", "ix", "iy"], observed=True).size().rename("rows").reset_index()
    out["dwell_s"] = (out["rows"] * DT).astype("float32")
    return out.drop(columns="rows").astype({"hour": "int8", "ix": "int16", "iy": "int16"})


def passes(v, cells=(0.5, 1.0, 2.0)):
    """Distinct tracks per class, local hour and cell, for several cell sizes.

    Dwell time counts a person who waits 60 s like 60 people passing for 1 s; this counts each track once per cell
    and hour. Computed per cell size because distinct counts cannot be added up into bigger cells.
    """
    hour = (local_s(v["t"]) // 3600).astype("int8")
    parts = []
    for cell in cells:
        n = int(2 * LIM / cell)
        d = pd.DataFrame({
            "cls": v["cls"].to_numpy(), "hour": hour, "trk": v["trk"].to_numpy(),
            "ix": np.clip(((v["x"].to_numpy() + LIM) / cell).astype(int), 0, n - 1).astype("int16"),
            "iy": np.clip(((v["y"].to_numpy() + LIM) / cell).astype(int), 0, n - 1).astype("int16"),
        }).drop_duplicates()
        g = d.groupby(["cls", "hour", "ix", "iy"], observed=True).size().rename("tracks").reset_index()
        g["cell_m"] = cell
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    return out.astype({"tracks": "int32", "cell_m": "float32"})


# ------------------------------------------------------------------ events
def published_events(run_dir):
    """Events of the original pipeline, read from its CSV files (no rerun)."""
    run_dir = Path(run_dir)
    ttc = pd.read_csv(run_dir / "near_miss_ttc_events.csv")
    ttc = ttc.rename(columns={"event_start_timestamp": "t", "event_end_timestamp": "t_end"})
    ttc["local_time"] = pd.to_datetime(ttc["timestamp_local"], utc=True, errors="coerce").dt.tz_convert("Europe/Berlin").dt.strftime("%H:%M:%S") \
        if ttc["timestamp_local"].notna().any() else None
    ttc["source"] = "published"
    pet = pd.read_csv(run_dir / "near_miss_pet_proxy_events.csv")
    pet = pet.rename(columns={"timestamp": "t", "cell_center_x_m": "x", "cell_center_y_m": "y"})
    pet["source"] = "published"
    return ttc, pet


def compute_events(variant_frame, name):
    """Run the original TTC / PET-proxy functions on our tracks (slow). Returns the consolidated TTC events."""
    import compare_stitching as cs
    print(f"computing events on {name} (slow) ...", flush=True)
    res = cs.run_pipeline(cs.to_nma_schema(variant_frame, "trk", "cls"))
    ev = res["events"].rename(columns={"event_start_timestamp": "t", "event_end_timestamp": "t_end"})
    ev["source"] = name
    return ev, res["pet_near_miss"]


# ------------------------------------------------------------------ quality
def quality(raw, variants, info):
    seg, links, ep = info["seg"], info["links"], info["ep"]
    stats = info["stats_stitched"]
    stage = {}
    for name, v in variants.items():
        stage[name] = v.groupby("cls")["trk"].nunique().reindex(CLASSES).fillna(0).astype(int).to_dict()
    sens = []
    for mf in (1, 3, 10, 30):
        for me in (0, 1, 2, 5):
            k = stats[(stats["frames"] >= mf) & (stats["extent_m"] >= me)]
            c = k["cls"].value_counts()
            sens.append({"min_frames": mf, "min_extent_m": me, "tracks": int(len(k)),
                         **{cl: int(c.get(cl, 0)) for cl in CLASSES}})
    gaps, edges = np.histogram(links["gap_s"], bins=np.arange(0, 10.5, 0.5)) if len(links) else (np.zeros(20), np.arange(0, 10.5, 0.5))
    joins_by_class = ep.loc[links["a"], "cls"].value_counts().to_dict() if len(links) else {}
    mid = pd.DataFrame({"x": (ep.loc[links["a"], "ex"].to_numpy() + ep.loc[links["b"], "sx"].to_numpy()) / 2,
                        "y": (ep.loc[links["a"], "ey"].to_numpy() + ep.loc[links["b"], "sy"].to_numpy()) / 2,
                        "cls": ep.loc[links["a"], "cls"].to_numpy()}) if len(links) else pd.DataFrame(columns=["x", "y", "cls"])
    mid = mid.sample(min(6000, len(mid)), random_state=0).round(2)
    print("synthetic cut test ...", flush=True)
    syn = tsx.synthetic_cut_test(seg, ep, info["edge_r"], n=3000)
    synt = syn.groupby("cls").agg(tracks=("trk", "size"), recall=("joined_right", "mean"), wrong=("joined_wrong", "mean")).round(4)
    synt.loc["ALL"] = [len(syn), round(syn["joined_right"].mean(), 4), round(syn["joined_wrong"].mean(), 4)]
    return {
        "schema": SCHEMA,
        "raw": {"rows": int(len(raw)), "unique_track_ids": int(raw["track_id"].nunique()),
                "duplicate_rows_removed": int(info["duplicates_removed"])},
        "tracks_per_stage": {"segments": stage["segmented"], "stitched": stage["stitched"], "clean": stage["clean"]},
        "sensitivity": sens,
        "stitching": {"segments": int(len(ep)), "joins": int(len(links)), "joins_by_class": joins_by_class,
                      "gap_histogram": {"bin_edges_s": edges.round(2).tolist(), "joins": gaps.tolist()},
                      "join_midpoints": mid.to_dict(orient="records"),
                      "edge_radius_m": round(float(info["edge_r"]), 2)},
        "synthetic_cut_test": synt.reset_index().to_dict(orient="records"),
        "parameters": {"gap_s": tsx.GAP_S, "max_gap_s": tsx.MAX_GAP_S, "static_gap_s": tsx.STATIC_GAP_S, "static_speed": tsx.STATIC_SPEED,
                       "base_tol_m": tsx.BASE_TOL_M, "speed_tol": tsx.SPEED_TOL, "ambig_margin": tsx.AMBIG_MARGIN,
                       "min_frames": info["min_frames"], "min_extent_m": info["min_extent_m"]},
        "known_issues": ["track_id is reused for different objects minutes apart (tracks are always split at gaps)",
                         "no scooter class; scooters probably sit in Cyclist or Pedestrian",
                         "class label can change inside one track (majority vote used)"],
    }


# ------------------------------------------------------------------ replay
def write_replay(v, tt, variant, out_dir):
    """5-minute chunks in the format of the player: T (frame times), F (frames of [trk, x, y, yaw]), M (track meta)."""
    out = Path(out_dir) / "replay" / variant
    out.mkdir(parents=True, exist_ok=True)
    cidx = {c: i for i, c in enumerate(CLASSES)}
    meta = {int(r.trk): [cidx.get(r.cls, 3), round(float(max(r.length_m, 0.5)), 1), round(float(max(r.width_m, 0.5)), 1)]
            for r in tt[["trk", "cls", "length_m", "width_m"]].itertuples(index=False)}
    sod = local_s(v["t"])
    chunk = (sod // 300).astype(int)
    order = np.lexsort((v["t"].to_numpy(), chunk))
    v = v.iloc[order]
    chunk = chunk[order]
    t_all = v["t"].to_numpy()
    trk_all = v["trk"].to_numpy()
    x_all, y_all, yaw_all = np.round(v["x"].to_numpy(), 1), np.round(v["y"].to_numpy(), 1), np.round(v["yaw"].to_numpy(), 2)
    starts = np.r_[0, np.flatnonzero(np.diff(chunk)) + 1, len(chunk)]
    total = 0
    for a, b in zip(starts[:-1], starts[1:]):
        c = int(chunk[a])
        t = t_all[a:b]
        fr_start = np.r_[0, np.flatnonzero(np.diff(t)) + 1, len(t)]
        rows = list(zip(trk_all[a:b].tolist(), x_all[a:b].tolist(), y_all[a:b].tolist(), yaw_all[a:b].tolist()))
        t0 = float(t[0])
        T = [round(float(t[i]) - t0, 2) for i in fr_start[:-1]]
        F = [[list(r) for r in rows[i:j]] for i, j in zip(fr_start[:-1], fr_start[1:])]
        used = {r[0] for fr in F for r in fr}
        data = {"schema": SCHEMA, "chunk_start_local_s": c * 300, "local0": float((t0 + UTC_OFFSET_S) % 86400),
                "T": T, "F": F, "M": {str(k): meta[k] for k in used if k in meta}, "C": CLASSES, "lim": LIM}
        name = f"{(c * 300) // 3600:02d}{((c * 300) % 3600) // 60:02d}.json.gz"
        with gzip.open(out / name, "wt", encoding="utf-8", compresslevel=6) as fh:
            json.dump(data, fh, separators=(",", ":"))
        total += 1
    print(f"  replay/{variant}: {total} chunks")


# ------------------------------------------------------------------ main
def select_window(files, start, minutes):
    h, m = [int(x) for x in start.split(":")]
    lo, hi = h * 60 + m, h * 60 + m + minutes
    keep = [f for f in files if (mt := FILE_RE.search(f.name)) and lo <= int(mt.group(1)) * 60 + int(mt.group(2)) < hi]
    if not keep:
        raise FileNotFoundError(f"no files for {start} + {minutes} min")
    return keep


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def main(argv=None):
    global UTC_OFFSET_S, DAY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="database/newsense/object_list")
    ap.add_argument("--date", default=DAY, help="which day's files to use (YYYY-MM-DD)")
    ap.add_argument("--min-score", type=float, default=MIN_SCORE, help="drop detections with a lower NSE score")
    ap.add_argument("--out", default="dashboard/data")
    ap.add_argument("--steps", nargs="+", default=["tracks", "counts", "density", "events", "signals", "quality", "replay", "meta"])
    ap.add_argument("--signals-dir", default="database/traffic_signal_data")
    ap.add_argument("--reparse", action="store_true", help="ignore the cached parse of the raw json")
    ap.add_argument("--start", help="only files from this local time (HH:MM), for quick tests")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--replay-variants", nargs="+", default=["clean"], choices=list(tp.VARIANTS))
    ap.add_argument("--compute-events", nargs="*", default=[], choices=list(tp.VARIANTS),
                    help="also run the near-miss functions on our tracks (slow)")
    ap.add_argument("--published-run", default=None,
                    help="near_miss_analysis.py output folder; default: newest output/k305_<date>_full_day_* folder")
    ap.add_argument("--zones", default="dashboard/config/zones.json",
                    help="zones.json from zones.py; zones.py needs a first build (density), so build, run zones.py, build again")
    args = ap.parse_args(argv)

    t_start = time.perf_counter()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    DAY = args.date
    all_files = tp.list_files(args.data_dir, DAY)
    UTC_OFFSET_S = tp.utc_offset_s(all_files)
    print(f"{DAY}: {len(all_files)} files, local time = UTC{UTC_OFFSET_S / 3600:+.0f}")
    partial = bool(args.start)
    if partial:
        files = select_window(all_files, args.start, args.minutes)
        print(f"partial build: {len(files)} files from {args.start}")
        raw = tp.parse_files(files)
    else:
        raw = tp.load_raw(args.data_dir, out / "cache" / f"raw_{DAY}.parquet", reparse=args.reparse, date=DAY)
    if "score" not in raw:  # cache from an older build
        raw["score"] = np.float32(1.0)
    n_all = len(raw)
    raw = raw[raw["score"] >= args.min_score].reset_index(drop=True)
    low_score = n_all - len(raw)
    print(f"{n_all:,} rows, {low_score:,} with score < {args.min_score} removed ({low_score / max(n_all, 1):.0%})")
    if args.published_run is None:
        runs = sorted(Path("output").glob(f"k305_{DAY}_full_day_*"))
        args.published_run = str(runs[-1]) if runs else ""

    variants, info = tp.make_variants(raw)
    tables, visits = {}, {}
    zones_ok = Path(args.zones).exists()
    for name, v in variants.items():
        tables[name] = track_table(v)
        if zones_ok:
            tables[name], visits[name] = add_zones(tables[name], v, args.zones)
    print("zones: " + (f"arms and crossings added from {args.zones}" if zones_ok else f"{args.zones} missing, run zones.py and build again"))

    if "tracks" in args.steps:
        for name, tt in tables.items():
            tt.to_parquet(out / f"tracks_{name}.parquet")
        for name, vis in visits.items():
            vis.to_parquet(out / f"crossing_visits_{name}.parquet")
        print("tracks" + (" and crossing visits" if visits else "") + " written")
    if "counts" in args.steps:
        for name, tt in tables.items():
            counts_15min(tt).to_parquet(out / f"counts_15min_{name}.parquet")
        print("counts written")
    if "density" in args.steps:
        for name, v in variants.items():
            density(v).to_parquet(out / f"density_{name}.parquet")
            passes(v).to_parquet(out / f"passes_{name}.parquet")
        print("density and passes written")
    if "events" in args.steps:
        run = Path(args.published_run) if args.published_run else None
        if run and run.exists() and not partial:
            ttc, pet = published_events(run)
            ttc.to_parquet(out / "events_published_ttc.parquet")
            pet.to_parquet(out / "events_published_pet.parquet")
            print(f"published events: {len(ttc):,} TTC, {len(pet):,} PET-proxy")
        else:
            print(f"published events skipped (partial build or {run} missing)")
        for name in args.compute_events:
            ev, pet_n = compute_events(variants[name], name)
            ev.to_parquet(out / f"events_{name}_ttc.parquet")
            print(f"{name}: {len(ev):,} TTC events, {pet_n:,} PET-proxy near misses")
    if "signals" in args.steps:
        import signals as sg
        sig_file = Path(args.signals_dir) / f"K305_{DAY.replace('-', '_')}.xlsx"
        if sig_file.exists():
            sig = sg.read_signals(sig_file)
            sig.to_parquet(out / "signals.parquet")
            groups = sg.signal_groups(sig)
            (out / "signal_groups.json").write_text(json.dumps(groups, indent=1), encoding="utf-8")
            print(f"signals: {len(sig):,} seconds, {sig['local'].iat[0]} to {sig['local'].iat[-1]}, {len(groups)} independent groups")
        else:
            print(f"signals: {sig_file} missing")
    if "quality" in args.steps:
        q = quality(raw, variants, info)
        q["raw"].update({"rows_before_score_filter": int(n_all), "low_score_rows_removed": int(low_score), "min_score": args.min_score})
        (out / "quality.json").write_text(json.dumps(q), encoding="utf-8")
        print("quality written")
    if "replay" in args.steps:
        for name in args.replay_variants:
            write_replay(variants[name], tables[name], name, out)
    if "meta" in args.steps:
        meta = {
            "schema": SCHEMA, "day": DAY, "utc_offset_s": UTC_OFFSET_S, "classes": CLASSES, "vru_classes": VRU,
            "source": "NSE object list", "min_score": args.min_score, "low_score_rows_removed": int(low_score),
            "daylight_local": DAYLIGHT.get(DAY), "published_run": Path(args.published_run).name if args.published_run else None,
            "variants": list(tp.VARIANTS), "default_variant": "clean", "bounds_m": [-LIM, LIM, -LIM, LIM], "density_cell_m": CELL,
            "dt_s": DT, "partial": partial, "window": {"start": args.start, "minutes": args.minutes} if partial else None,
            "rows": int(len(raw)),
            "tracks": {k: {c: int(n) for c, n in tt["cls"].value_counts().items()} for k, tt in tables.items()},
            "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_commit": git_commit(),
            "build_seconds": round(time.perf_counter() - t_start, 1),
        }
        (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"done in {time.perf_counter() - t_start:.0f} s -> {out}")


if __name__ == "__main__":
    main()
