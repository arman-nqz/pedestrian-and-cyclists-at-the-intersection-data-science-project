"""Job 1 + 2: clean VRU tracks, export spatial points, and count per 15 minutes.

Supports either:
  - A directory of 5-minute JSON files, OR
  - A .zip archive containing the 5-minute JSON files (no extraction needed).

Run from the repo's main folder:  python vru_prepare.py
"""
import glob
import json
import os
import zipfile

import numpy as np
import pandas as pd

# Point DATA_SOURCE to either a folder of JSONs or a .zip archive:
# - Local path if downloaded to database/:
#DATA_SOURCE = "database/k305_object_list_2026-10-29_aggregation_5min.zip"
DATA_SOURCE = "/content/drive/MyDrive/k305_object_list_2026-10-29_aggregation_5min.zip"
# - Google Colab path (if running via Google Drive shortcut):
# DATA_SOURCE = "/content/drive/MyDrive/k305_object_list_2026-10-29_aggregation_5min.zip"
# - Legacy sample folder (3 midnight files):
# DATA_SOURCE = "database/k305_object_list_2026-10-14_aggregation_5min"

OUT_DIR = "output/vru_analysis"
VRU_CLASSES = {"Pedestrian", "Cyclist"}
VEHICLE_CLASSES = {"Car", "Van", "Truck", "Bus", "Motorcycle"}
MIN_FRAMES = 5       # tracks shorter than 0.5 s at 10 Hz are sensor noise
MIN_SCORE = 0.25     # ML confidence threshold (legacy 14.10 data has score=1.0)
VEHICLE_STRIDE = 10  # keep every 10th frame (1 Hz) for vehicles to keep overlap CSV small


def extract_rows_from_json(data):
    """Parse one 5-minute JSON dict into VRU rows and downsampled vehicle rows."""
    vru_rows = []
    veh_rows = []
    for frame_idx, frame in enumerate(data.get("frames", [])):
        t = frame.get("timestamp_local")
        if t is None:
            ts = frame["frame_timestamp"]
            t = ts["seconds"] + ts["nanosec"] / 1e9

        keep_vehicle_frame = (frame_idx % VEHICLE_STRIDE == 0)

        for o in frame.get("objects", []):
            if o.get("score", 1.0) < MIN_SCORE:
                continue
            cls = o["class_name"]
            pos = o["bounding_box"]["position"]

            if cls in VRU_CLASSES:
                vru_rows.append((t, o["track_id"], cls, pos["x"], pos["y"]))
            elif keep_vehicle_frame and cls in VEHICLE_CLASSES:
                veh_rows.append((t, o["track_id"], cls, pos["x"], pos["y"]))

    return vru_rows, veh_rows


def load_all_data(source):
    """Load JSON chunks from either a directory or a .zip archive."""
    vru_rows = []
    veh_rows = []

    if os.path.isfile(source) and source.lower().endswith(".zip"):
        with zipfile.ZipFile(source, "r") as zf:
            names = sorted(n for n in zf.namelist() if n.endswith(".json"))
            if not names:
                raise SystemExit(f"No JSON files inside {source}")
            print(f"Found {len(names)} JSON file(s) inside zip")
            for i, name in enumerate(names, 1):
                with zf.open(name) as f:
                    v_r, m_r = extract_rows_from_json(json.load(f))
                    vru_rows.extend(v_r)
                    veh_rows.extend(m_r)
                if i % 20 == 0 or i == len(names):
                    print(f"  loaded {i}/{len(names)}")
    else:
        files = sorted(glob.glob(os.path.join(source, "*.json")))
        if not files:
            raise SystemExit(f"No JSON files found in {source}. Check DATA_SOURCE path.")
        print(f"Found {len(files)} JSON file(s) in folder")
        for i, path in enumerate(files, 1):
            with open(path) as f:
                v_r, m_r = extract_rows_from_json(json.load(f))
                vru_rows.extend(v_r)
                veh_rows.extend(m_r)
            if i % 20 == 0 or i == len(files):
                print(f"  loaded {i}/{len(files)}")

    return vru_rows, veh_rows


def to_local_time(series):
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="s", utc=True).dt.tz_convert("Europe/Berlin")
    return pd.to_datetime(series, format="ISO8601", utc=True).dt.tz_convert("Europe/Berlin")


def majority_class(series):
    """Resolve class flickering by picking the most frequent class for a track."""
    return series.mode().iloc[0]


def main():
    vru_rows, veh_rows = load_all_data(DATA_SOURCE)

    df = pd.DataFrame(vru_rows, columns=["time", "track_id", "cls", "x", "y"])
    if df.empty:
        raise SystemExit("No pedestrians or cyclists found.")

    df["time"] = to_local_time(df["time"])
    df = df.sort_values(["track_id", "time"]).reset_index(drop=True)

    # One summary row per unique person/cyclist
    g = df.groupby("track_id")
    tracks = pd.DataFrame({
        "cls": g["cls"].agg(majority_class),
        "n_frames": g.size(),
        "t_start": g["time"].min(),
        "t_end": g["time"].max(),
        "x_start": g["x"].first(),
        "y_start": g["y"].first(),
        "x_end": g["x"].last(),
        "y_end": g["y"].last(),
    })

    before = len(tracks)
    tracks = tracks[tracks.n_frames >= MIN_FRAMES].copy()
    tracks["duration_s"] = (tracks.t_end - tracks.t_start).dt.total_seconds()
    tracks["dwell_s"] = tracks["n_frames"] * 0.1  # 10 Hz -> 0.1 s per observation
    tracks["displacement_m"] = np.hypot(
        tracks["x_end"] - tracks["x_start"],
        tracks["y_end"] - tracks["y_start"],
    )
    tracks["mean_speed_mps"] = np.where(
        tracks["duration_s"] > 0,
        tracks["displacement_m"] / tracks["duration_s"],
        0.0,
    )
    print(f"Tracks: {before} raw -> {len(tracks)} after removing ghosts (< {MIN_FRAMES} frames)")

    # Keep only cleaned track IDs and attach majority class to point-level trajectories
    valid_cls_map = tracks["cls"]
    df_clean = df[df["track_id"].isin(tracks.index)].copy()
    df_clean["cls"] = df_clean["track_id"].map(valid_cls_map)

    # Counts and dwell time per 15 minutes (counted once in the window where track starts)
    tracks["window"] = tracks["t_start"].dt.floor("15min")
    counts_15min = tracks.groupby(["window", "cls"]).size().unstack(fill_value=0)
    dwell_15min = tracks.groupby(["window", "cls"])["dwell_s"].sum().unstack(fill_value=0.0)

    os.makedirs(OUT_DIR, exist_ok=True)
    tracks.to_csv(os.path.join(OUT_DIR, "vru_tracks.csv"))
    counts_15min.to_csv(os.path.join(OUT_DIR, "vru_counts_15min.csv"))
    dwell_15min.to_csv(os.path.join(OUT_DIR, "vru_dwell_15min.csv"))
    df_clean.to_csv(os.path.join(OUT_DIR, "vru_points.csv"), index=False)

    if veh_rows:
        veh_df = pd.DataFrame(veh_rows, columns=["time", "track_id", "cls", "x", "y"])
        veh_df["time"] = to_local_time(veh_df["time"])
        veh_df.to_csv(os.path.join(OUT_DIR, "vehicle_points.csv"), index=False)

    print("\nUnique individuals:")
    print(tracks.cls.value_counts())
    print("\nCounts per 15 min (first 10 windows):")
    print(counts_15min.head(10))
    print(f"\nSaved outputs to {OUT_DIR}/")


if __name__ == "__main__":
    main()
