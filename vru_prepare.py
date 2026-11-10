"""Job 1 + 2: clean VRU tracks and count them per 15 minutes.

Works on however many 5-minute JSON files are in DATA_DIR (3 now, 288 later).
Run from the repo's main folder:  python vru_prepare.py
"""
import glob
import json
import os

import pandas as pd

DATA_DIR = "database/k305_object_list_2026-10-14_aggregation_5min"
OUT_DIR = "output/vru_analysis"
VRU_CLASSES = {"Pedestrian", "Cyclist"}
MIN_FRAMES = 5  # tracks shorter than 0.5 s at 10 Hz are sensor noise


def load_file(path):
    """Return (time, track_id, class, x, y) rows for pedestrians and cyclists only."""
    with open(path) as f:
        data = json.load(f)
    rows = []
    for frame in data["frames"]:
        t = frame.get("timestamp_local")
        if t is None:  # fall back to the numeric timestamp
            ts = frame["frame_timestamp"]
            t = ts["seconds"] + ts["nanosec"] / 1e9
        for o in frame["objects"]:
            if o["class_name"] not in VRU_CLASSES:
                continue
            pos = o["bounding_box"]["position"]
            rows.append((t, o["track_id"], o["class_name"], pos["x"], pos["y"]))
    return rows


def to_local_time(series):
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="s", utc=True).dt.tz_convert("Europe/Berlin")
    return pd.to_datetime(series, utc=True).dt.tz_convert("Europe/Berlin")


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    if not files:
        raise SystemExit(f"No JSON files found in {DATA_DIR}. Run from the repo's main folder.")
    print(f"Found {len(files)} file(s)")

    rows = []
    for i, path in enumerate(files, 1):
        rows.extend(load_file(path))
        if i % 20 == 0 or i == len(files):
            print(f"  loaded {i}/{len(files)}")

    df = pd.DataFrame(rows, columns=["time", "track_id", "cls", "x", "y"])
    if df.empty:
        raise SystemExit("No pedestrians or cyclists in these files (normal for midnight files).")
    df["time"] = to_local_time(df["time"])
    df = df.sort_values(["track_id", "time"])

    # one row per person/bike
    g = df.groupby("track_id")
    tracks = pd.DataFrame({
        "cls": g["cls"].first(),
        "n_frames": g.size(),
        "t_start": g["time"].min(),
        "t_end": g["time"].max(),
        "x_start": g["x"].first(), "y_start": g["y"].first(),
        "x_end": g["x"].last(), "y_end": g["y"].last(),
    })
    before = len(tracks)
    tracks = tracks[tracks.n_frames >= MIN_FRAMES].copy()
    tracks["duration_s"] = (tracks.t_end - tracks.t_start).dt.total_seconds()
    print(f"Tracks: {before} raw -> {len(tracks)} after removing ghosts (< {MIN_FRAMES} frames)")

    # counts per 15 minutes (a track is counted once, in the window where it starts)
    tracks["window"] = tracks["t_start"].dt.floor("15min")
    counts = tracks.groupby(["window", "cls"]).size().unstack(fill_value=0)

    os.makedirs(OUT_DIR, exist_ok=True)
    tracks.to_csv(os.path.join(OUT_DIR, "vru_tracks.csv"))
    counts.to_csv(os.path.join(OUT_DIR, "vru_counts_15min.csv"))
    print("\nUnique individuals:")
    print(tracks.cls.value_counts())
    print("\nCounts per 15 min:")
    print(counts)
    print(f"\nSaved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
