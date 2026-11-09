"""Read Ouster BlueCity object logs (object_list+occupations.log.*.gz) into the same table layout as NSE.

Each file holds JSON lines: object lines {"timestamp": us, "objects": [...]} and occupation lines
{"timestamp": us, "occupations": [...]} (zone occupancy). File names are the UTC time the log was rotated,
not the local start time, so files are selected by the timestamps inside them.

    read_window(folder, t0, t1)   -> DataFrame with columns like track_pipeline.RAW_COLUMNS
"""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Ouster classification (+ sub classification) -> the NSE class names used everywhere else
CLASS_MAP = {"PERSON": "Pedestrian", "BICYCLE": "Cyclist", "VEHICLE": "Car", "UNKNOWN": "Unknown"}
LARGE_SUB = {"bus": "Bus", "truck": "Truck", "trailer": "Truck"}
COLUMNS = ["t", "track_id", "class_name", "x", "y", "vx", "vy", "yaw", "length", "width", "score", "file_idx",
           "ouster_class", "ouster_sub"]


def map_class(cls, sub):
    if cls == "LARGE_VEHICLE":
        return LARGE_SUB.get(sub or "", "Truck")
    return CLASS_MAP.get(cls, "Unknown")


def files(folder):
    return sorted(Path(folder).glob("object_list+occupations.log.*.gz"))


def file_span(path):
    """(first, last) object timestamp in seconds, reading the whole file (they are small)."""
    first = last = None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if "objects" in d and d["objects"]:
                t = d["timestamp"] / 1e6
                first = t if first is None else first
                last = t
    return first, last


def read_window(folder, t0, t1, spans=None):
    """All Ouster objects with t0 <= t < t1 (epoch seconds)."""
    rows = []
    for i, f in enumerate(files(folder)):
        if spans is not None:
            a, b = spans.get(f.name, (None, None))
            if a is None or b < t0 or a >= t1:
                continue
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                if "objects" not in d:
                    continue
                t = d["timestamp"] / 1e6
                if not (t0 <= t < t1):
                    continue
                for o in d["objects"]:
                    p, v, dim = o["position"], o["velocity"], o["dimensions"]
                    rows.append((t, o["id"], map_class(o["classification"], o.get("sub_classification")),
                                 p["x"], p["y"], v["x"], v["y"], np.radians(o.get("heading") or 0.0),
                                 dim["length"], dim["width"], o.get("classification_confidence", 1.0), i,
                                 o["classification"], o.get("sub_classification") or ""))
    df = pd.DataFrame(rows, columns=COLUMNS)
    if len(df):
        df = df.astype({c: "float32" for c in ["x", "y", "vx", "vy", "yaw", "length", "width", "score"]})
        df["class_name"] = df["class_name"].astype("category")
    return df
