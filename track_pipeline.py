"""Raw JSON -> cleaned tracks in three variants. Shared by build_dashboard_data.py and the notebooks.

    parse_files(files)        one row per object per frame
    make_variants(raw)        dict of variant frames + info about the stitching

Variants (same names as in the dashboard and STITCHING_COMPARISON.md):
    segmented  tracks split at time gaps > 1 s, no stitching
    stitched   segmented + pieces of the same object joined (track_stitching.py)
    clean      stitched, then drop tracks with < MIN_FRAMES frames or < MIN_EXTENT_M of movement

Every variant frame has the columns
    t, trk, seg_id, cls, x, y, vx, vy, yaw, length, width, file_idx
where `trk` is the id to use for that variant and `cls` is one majority-vote class per track.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import track_stitching as tsx

MIN_FRAMES = 3
MIN_EXTENT_M = 2.0
RAW_COLUMNS = ["t", "track_id", "class_name", "x", "y", "vx", "vy", "yaw", "length", "width", "file_idx"]
VARIANT_COLUMNS = ["t", "trk", "seg_id", "cls", "x", "y", "vx", "vy", "yaw", "length", "width", "file_idx"]
VARIANTS = ("segmented", "stitched", "clean")


def list_files(data_dir):
    files = sorted(Path(data_dir).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no json files in {data_dir}")
    return files


def parse_files(files, progress=True):
    """JSON files (5 min each) -> one DataFrame. file_idx is the position in `files`."""
    parts = []
    for i, f in enumerate(files):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = []
        for frame in data["frames"]:
            ts = frame["frame_timestamp"]
            t = ts["seconds"] + ts["nanosec"] * 1e-9
            for o in frame["objects"]:
                b = o["bounding_box"]
                p, s, v = b["position"], b["scale"], o["velocity"]
                rows.append((t, o["track_id"], o["class_name"], p["x"], p["y"], v["x"], v["y"], b["yaw"], s["x"], s["y"], i))
        df = pd.DataFrame(rows, columns=RAW_COLUMNS)
        df = df.astype({c: "float32" for c in ["x", "y", "vx", "vy", "yaw", "length", "width"]})
        df["file_idx"] = df["file_idx"].astype("int16")
        parts.append(df)
        if progress and ((i + 1) % 24 == 0 or i + 1 == len(files)):
            print(f"  parsed {i + 1}/{len(files)} files", flush=True)
    raw = pd.concat(parts, ignore_index=True)
    raw["class_name"] = raw["class_name"].astype("category")
    return raw


def load_raw(data_dir, cache_path=None, reparse=False, limit_files=None):
    """Parse (or load the cached parse of) the raw data."""
    cache_path = Path(cache_path) if cache_path else None
    if cache_path and cache_path.exists() and not reparse:
        print(f"loading cached raw table {cache_path}")
        return pd.read_parquet(cache_path)
    files = list_files(data_dir)
    if limit_files:
        files = files[:limit_files]
    t0 = time.perf_counter()
    raw = parse_files(files)
    print(f"parsed {len(raw):,} rows in {time.perf_counter() - t0:.0f} s")
    if cache_path and not limit_files:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(cache_path)
    return raw


def _frame(seg, trk_col, cls_col, mask=None):
    cols = {"t": seg["t"], "trk": seg[trk_col], "seg_id": seg["trk"], "cls": seg[cls_col], "x": seg["x"], "y": seg["y"],
            "vx": seg["vx"], "vy": seg["vy"], "yaw": seg["yaw"], "length": seg["length"], "width": seg["width"],
            "file_idx": seg["file_idx"]}
    out = pd.DataFrame(cols)
    if mask is not None:
        out = out[mask]
    return out.sort_values(["trk", "t"], kind="stable").reset_index(drop=True)


def make_variants(raw, min_frames=MIN_FRAMES, min_extent_m=MIN_EXTENT_M):
    """Returns (variants, info). info holds the stitching details that the quality page needs."""
    t0 = time.perf_counter()
    # the sensor sometimes writes the same object twice in one frame: keep the first row
    n_before = len(raw)
    raw = raw.drop_duplicates(["track_id", "t"], keep="first")
    duplicates = n_before - len(raw)
    seg, links, ep, edge_r = tsx.stitch_tracks(raw, return_details=True)
    seg["class_seg"] = seg["class_seg"].astype(str)
    g = seg.groupby("trk_s")
    ext = np.hypot(g["x"].max() - g["x"].min(), g["y"].max() - g["y"].min())
    size = g.size()
    keep = size.index[(size >= min_frames) & (ext >= min_extent_m)]
    variants = {
        "segmented": _frame(seg, "trk", "class_seg"),
        "stitched": _frame(seg, "trk_s", "class_final"),
        "clean": _frame(seg, "trk_s", "class_final", mask=seg["trk_s"].isin(keep).to_numpy()),
    }
    stats_s = pd.DataFrame({"frames": size, "extent_m": ext,
                            "cls": seg.groupby("trk_s")["class_final"].first()})
    info = {"links": links, "ep": ep, "edge_r": edge_r, "seg": seg, "stats_stitched": stats_s, "duplicates_removed": duplicates,
            "min_frames": min_frames, "min_extent_m": min_extent_m, "runtime_s": round(time.perf_counter() - t0, 1)}
    print(f"variants built in {info['runtime_s']} s: {duplicates:,} duplicate rows removed, segments {ep.shape[0]:,}, joins {len(links):,}, "
          f"stitched tracks {len(size):,}, clean tracks {len(keep):,}")
    return variants, info
