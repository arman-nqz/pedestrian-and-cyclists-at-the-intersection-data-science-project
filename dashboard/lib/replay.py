"""Replay: merge prebuilt 5-minute chunks into one window and build the player HTML (assets/player.html)."""
import gzip
import json
from pathlib import Path

import numpy as np
import streamlit as st

from lib import data, plots

CHUNK_S = 300
TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "player.html"


def chunk_path(variant, local_s):
    c = int(local_s) // CHUNK_S * CHUNK_S
    return data.DATA / "replay" / variant / f"{c // 3600:02d}{c % 3600 // 60:02d}.json.gz"


@st.cache_data(max_entries=6)
def window(variant, start_s, minutes):
    """Frames of [start_s, start_s + minutes) local time, times relative to start_s. None if no chunk exists."""
    T, F, M, C, lim = [], [], {}, None, plots.LIM
    for k in range(minutes * 60 // CHUNK_S):
        p = chunk_path(variant, start_s + k * CHUNK_S)
        if not p.exists():
            continue
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            d = json.load(fh)
        shift = d["local0"] - start_s
        T += [round(t + shift, 2) for t in d["T"]]
        F += d["F"]
        M.update(d["M"])
        C, lim = d["C"], d.get("lim", lim)
    if not T:
        return None
    return {"T": T, "F": F, "M": M, "C": C, "lim": lim, "local0": start_s}


@st.cache_data
def map_layer():
    """OSM roads, footways, buildings, crossings and street names for the canvas (sensor meters)."""
    osm, z = data.osm_map(), data.zones()
    if not osm:
        return None
    roads = [f for f in osm["roads"] if f["highway"] in plots.ROAD_STYLE]
    crossings = []
    for c in (z or {}).get("crossings", []):
        cx, cy = np.mean(c["polygon"], axis=0)
        crossings.append({"id": c["id"], "xy": c["polygon"], "cx": float(cx), "cy": float(cy)})
    return {"roads": [{"xy": f["xy"], "w": plots._width(f)} for f in roads],
            "footways": [f["xy"] for f in osm["footways"]],
            "buildings": [f["xy"] for f in osm.get("buildings", [])],
            "crossings": crossings,
            "labels": plots._labels(osm["roads"])}


def player_html(win, start_in_window, video_offset, event=None):
    """`video_offset`: seconds into the video file at the window start (None = no video sync).
    `event`: {local_s, local_end, x, y, ids, label} to highlight, from the Conflicts page."""
    ev = None
    if event and win["local0"] <= event["local_s"] < win["local0"] + win["T"][-1] + 1:
        ev = {"t": event["local_s"] - win["local0"], "t_end": event["local_end"] - win["local0"],
              "x": event["x"], "y": event["y"], "ids": event["ids"], "label": event["label"]}
    d = dict(win, start=start_in_window, video_offset=video_offset, map=map_layer(), event=ev)
    return TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", json.dumps(d, separators=(",", ":")))
