"""NSE and Ouster detections around one moment, both moved into the NSE frame of the dashboard maps.

Used by the Video check page: one player, Ouster on the left, NSE on the right. NSE comes from the raw cache that
build_dashboard_data.py writes (all scores, so the low-score tracks the review asks about are there); Ouster from its
object-list logs (object_list+occupations.log.*.gz).
"""
import gzip
import json
import math
import re

import numpy as np
import pandas as pd
import streamlit as st

from lib import data

ROOT = data.ROOT.parent
NSE_RAW = data.DATA / "cache" / "raw_2026-10-29.parquet"
OUSTER_DIRS = [ROOT / "database" / "ouster",
               ROOT / "database" / "new data" / "drive-download-20261103T131231Z-1-001" / "Object_list_THA"]
UTC_OFFSET = 3600  # CET
# NSE frame -> Ouster frame, (rotation deg, shift x, shift y), from comparingDataFromBothSensors/sensor_compare.py.
# Ouster was recalibrated 08:13 to 08:15 CET: before that its frame is "A", after it "B" (= the comparison's common frame).
NS_TO_OU_A = (170.8, -18.15, 4.67)
NS_TO_OU_B = (95.8, -12.72, 6.10)
SWITCH_LOCAL = 8 * 3600 + 14 * 60
GROUPS = ["Pedestrian", "Cyclist", "Motorcycle", "Vehicle", "Unknown"]
NSE_GROUP = {"Pedestrian": "Pedestrian", "Cyclist": "Cyclist", "Motorcycle": "Motorcycle"}  # everything else: Vehicle
OU_GROUP = {"PERSON": "Pedestrian", "BICYCLE": "Cyclist", "VEHICLE": "Vehicle", "LARGE_VEHICLE": "Vehicle"}
LOW_SCORE = 0.25
_OU_NAME = re.compile(r"object_list\+occupations\.log\.\d{4}-\d{2}-\d{2}_(\d{2})-(\d{2})-(\d{2})\.000\.gz$")


def to_nse(x, y, local_s):
    """Ouster coordinates at local time `local_s` -> NSE frame. Arrays or scalars."""
    deg, tx, ty = NS_TO_OU_A if local_s < SWITCH_LOCAL else NS_TO_OU_B
    t = math.radians(deg)
    dx, dy = np.asarray(x) - tx, np.asarray(y) - ty
    return math.cos(t) * dx + math.sin(t) * dy, -math.sin(t) * dx + math.cos(t) * dy


def common_to_nse(x, y):
    """The comparison's common frame (epoch-B Ouster frame, used in results.csv) -> NSE frame."""
    return to_nse(x, y, SWITCH_LOCAL + 3600)


def _local(ts):
    return (np.asarray(ts) + UTC_OFFSET) % 86400


@st.cache_data(max_entries=4)
def _ouster_file(path):
    rows = []
    with gzip.open(path, "rt") as fh:
        last = None
        for line in fh:
            if '"occupations":' in line[:70] or not line.strip():
                continue
            d = json.loads(line)
            ts = d.get("timestamp", 0) * 1e-6
            if ts == last:  # duplicate frame: keep the first
                continue
            last = ts
            for o in d.get("objects") or []:
                p, v = o["position"], o.get("velocity") or {}
                dm = o.get("dimensions") or {}
                rows.append((ts, int(o["id"]), OU_GROUP.get(o.get("classification"), "Unknown"), p["x"], p["y"],
                             v.get("x", 0.0), v.get("y", 0.0), o.get("heading", 0.0), dm.get("length", 0.5),
                             dm.get("width", 0.5), o.get("classification", "UNKNOWN")))
            if not d.get("objects"):
                rows.append((ts, -1, "", np.nan, np.nan, 0.0, 0.0, 0.0, 0.0, 0.0, ""))  # keep empty frames
    return pd.DataFrame(rows, columns=["t", "id", "grp", "x", "y", "vx", "vy", "heading_deg", "length", "width", "cls_raw"])


def ouster_files():
    """{path: window end, local seconds}. File names carry the window END in UTC; windows are 5 or 10 minutes."""
    out = {}
    for d in OUSTER_DIRS:
        for p in d.glob("object_list+occupations.log.*.gz") if d.exists() else []:
            m = _OU_NAME.search(p.name)
            if m:
                out[str(p)] = (int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + UTC_OFFSET) % 86400
    return out


def _frames(df, t0, has_low):
    """Group detections by frame time -> {T: [s from t0], F: [[[id, x, y, heading or null, group idx, low], ...]]}."""
    T, F = [], []
    for t, g in df.groupby("t", sort=True):
        T.append(round(t - t0, 2))
        g = g[g["id"] >= 0]
        sp = np.hypot(g["vx"], g["vy"]).to_numpy()
        hd = np.where(sp > 0.3, np.arctan2(g["vy"], g["vx"]), np.nan)
        low = g["low"].to_numpy() if has_low else np.zeros(len(g), bool)
        F.append([[int(i), round(float(x), 2), round(float(y), 2), None if np.isnan(h) else round(float(h), 2),
                   GROUPS.index(c), int(lw)] for i, x, y, h, c, lw in zip(g["id"], g["x"], g["y"], hd, g["grp"], low)])
    return {"T": T, "F": F}


@st.cache_data(max_entries=4)
def window(t0_local, t1_local, cx, cy, radius=32.0):
    """Both sensors in [t0_local, t1_local) (CET seconds), within `radius` m of (cx, cy) in the NSE frame.
    Returns {"nse": frames or None, "ouster": frames or None, "groups": GROUPS, "note": text}."""
    day0 = pd.Timestamp("2026-10-29", tz="UTC").timestamp() - UTC_OFFSET  # epoch of 00:00 CET
    a, b = day0 + t0_local, day0 + t1_local
    out = {"groups": GROUPS, "nse": None, "ouster": None, "note": []}
    if NSE_RAW.exists():
        n = pd.read_parquet(NSE_RAW, columns=["t", "track_id", "class_name", "x", "y", "vx", "vy", "score"],
                            filters=[("t", ">=", a), ("t", "<", b)])
        n = n[np.hypot(n["x"] - cx, n["y"] - cy) < radius]
        n = n.assign(id=n["track_id"], grp=n["class_name"].astype(str).map(NSE_GROUP).fillna("Vehicle"),
                     low=n["score"] < LOW_SCORE)
        out["nse"] = _frames(n, a, True) if len(n) else None
    else:
        out["note"].append(f"NSE raw cache `{NSE_RAW.name}` missing: run build_dashboard_data.py once.")
    files = [p for p, end in ouster_files().items() if t0_local <= end <= t1_local + 600]
    if files:
        o = pd.concat([_ouster_file(p) for p in sorted(files)])
        o = o[(o["t"] >= a) & (o["t"] < b)].copy()
        if len(o):
            x, y = to_nse(o["x"], o["y"], t0_local)
            th = math.radians(NS_TO_OU_A[0] if t0_local < SWITCH_LOCAL else NS_TO_OU_B[0])
            vx, vy = o["vx"].to_numpy(), o["vy"].to_numpy()
            o["x"], o["y"] = x, y
            o["vx"], o["vy"] = math.cos(th) * vx + math.sin(th) * vy, -math.sin(th) * vx + math.cos(th) * vy
            keep = (o["id"] < 0) | (np.hypot(o["x"] - cx, o["y"] - cy) < radius)
            out["ouster"] = _frames(o[keep], a, False)
    if out["ouster"] is None:
        out["note"].append("No Ouster object list for this time on this computer (here: up to 08:35 CET). "
                           "Copy the remaining `object_list+occupations.log.*.gz` files into `database/ouster/`.")
    out["note"] = " ".join(out["note"])
    return out


def player_html(win, local0, check, cx, cy, video_offset, half=32.0):
    """Two-pane player (assets/pair_player.html). `check` = (start, end) of the check, seconds from local0;
    `video_offset` = seconds into the video file at local0 (None = no sync)."""
    from pathlib import Path
    from lib import replay
    d = dict(win, local0=local0, check=list(check), cx=cx, cy=cy, half=half, video_offset=video_offset,
             start=max(0, check[0] - 3), dur=max(max(s["T"][-1] for s in (win["nse"], win["ouster"]) if s) if
                                                   (win["nse"] or win["ouster"]) else 0, check[1]),
             map=replay.map_layer())
    tpl = Path(__file__).resolve().parents[1] / "assets" / "pair_player.html"
    return tpl.read_text(encoding="utf-8").replace("__DATA__", json.dumps(d, separators=(",", ":")))


OU_REPLAY_CLASS = {"PERSON": "Pedestrian", "BICYCLE": "Cyclist", "VEHICLE": "Car", "LARGE_VEHICLE": "Truck"}


@st.cache_data(max_entries=4)
def ouster_replay(start_s, minutes):
    """Ouster frames of [start_s, start_s + minutes) local time in the Replay player's format (see
    build_dashboard_data.write_replay), moved into the NSE frame. None if no Ouster file covers the window."""
    from lib import plots
    end_s = start_s + minutes * 60
    files = [p for p, end in ouster_files().items() if start_s < end <= end_s + 600]
    if not files:
        return None
    day0 = pd.Timestamp("2026-10-29", tz="UTC").timestamp() - UTC_OFFSET
    o = pd.concat([_ouster_file(p) for p in sorted(files)])
    o = o[(o["t"] >= day0 + start_s) & (o["t"] < day0 + end_s) & (o["id"] >= 0)].copy()
    if o.empty:
        return None
    th = math.radians(NS_TO_OU_A[0] if start_s < SWITCH_LOCAL else NS_TO_OU_B[0])
    o["x"], o["y"] = to_nse(o["x"], o["y"], start_s)
    o["yaw"] = np.radians(o["heading_deg"]) - th  # heading is degrees counter-clockwise from x in the Ouster frame
    classes = data.CLASSES + ["Unknown"]
    o["cls"] = o["cls_raw"].map(OU_REPLAY_CLASS).fillna("Unknown")
    known = o[o["cls"] != "Unknown"]
    cls = known.groupby("id")["cls"].agg(lambda c: c.mode().iat[0])  # new tracks start UNKNOWN: use the majority class
    dims = o.groupby("id")[["length", "width"]].median()
    M = {str(i): [classes.index(cls.get(i, "Unknown")), round(float(max(r.length, 0.5)), 1), round(float(max(r.width, 0.5)), 1)]
         for i, r in dims.iterrows()}
    o = o.sort_values(["t", "id"])
    t0 = day0 + start_s
    T, F = [], []
    for t, g in o.groupby("t", sort=True):
        T.append(round(t - t0, 2))
        F.append([[int(i), round(float(x), 1), round(float(y), 1), round(float(a), 2)]
                  for i, x, y, a in zip(g["id"], g["x"], g["y"], g["yaw"])])
    return {"T": T, "F": F, "M": M, "C": classes, "lim": plots.LIM, "local0": start_s}
