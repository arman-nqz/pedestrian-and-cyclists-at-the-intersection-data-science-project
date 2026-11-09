"""Loaders for the files written by build_dashboard_data.py (cached by Streamlit)."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "config"
CONTENT = ROOT / "content"

VARIANTS = ["clean", "stitched", "segmented"]
VARIANT_HELP = {
    "clean": "stitched, then tracks with < 3 frames or < 2 m of movement removed (default)",
    "stitched": "pieces of the same object joined, nothing removed",
    "segmented": "tracks split at gaps > 1 s, not stitched (control)",
}
CLASSES = ["Pedestrian", "Cyclist", "Motorcycle", "Car", "Van", "Truck", "Bus"]
VRU = ["Pedestrian", "Cyclist", "Motorcycle"]
COLORS = {"Pedestrian": "#2b7bd6", "Cyclist": "#e8791b", "Motorcycle": "#8e5bd0",
          "Car": "#7f8c99", "Van": "#95a3b0", "Truck": "#5f6b77", "Bus": "#4a5560"}
UTC_OFFSET_S = 7200


class MissingData(Exception):
    pass


def _need(path):
    if not path.exists():
        raise MissingData(f"`{path.relative_to(ROOT.parent)}` is missing. Build the data with "
                          "`python build_dashboard_data.py --data-dir <folder with the 288 json files>`.")
    return path


@st.cache_data
def meta():
    return json.loads(_need(DATA / "meta.json").read_text(encoding="utf-8"))


@st.cache_data
def quality():
    return json.loads(_need(DATA / "quality.json").read_text(encoding="utf-8"))


@st.cache_data
def tracks(variant):
    return pd.read_parquet(_need(DATA / f"tracks_{variant}.parquet"))


@st.cache_data
def counts(variant):
    return pd.read_parquet(_need(DATA / f"counts_15min_{variant}.parquet"))


@st.cache_data
def density(variant):
    return pd.read_parquet(_need(DATA / f"density_{variant}.parquet"))


@st.cache_data
def passes(variant):
    return pd.read_parquet(_need(DATA / f"passes_{variant}.parquet"))


@st.cache_data
def osm_map():
    p = CONFIG / "k305_map.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@st.cache_data
def zones():
    p = CONFIG / "zones.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def content(name):
    p = CONTENT / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def bin_label(b):
    """15-minute bin index -> 'HH:MM'"""
    return f"{(b * 15) // 60:02d}:{(b * 15) % 60:02d}"
