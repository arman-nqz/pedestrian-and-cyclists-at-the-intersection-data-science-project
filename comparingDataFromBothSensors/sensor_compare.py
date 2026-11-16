"""NewSense vs Ouster object-list comparison at intersection K305.

All loaders, transforms, matching and metric functions live here so that the
notebook (sensor_comparison.py / .ipynb) only calls them. Worker functions for
ProcessPoolExecutor must live in this module (forkserver start method).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

# --------------------------------------------------------------------------
# Paths and constants
# --------------------------------------------------------------------------
ROOT = Path("/home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project")
HERE = ROOT / "comparingDataFromBothSensors"
NS_DIR = ROOT / "database" / "Data from date of 28.10, 29.10." / "newsense" / "object_list"
OU_DIR = ROOT / "database" / "new data" / "drive-download-20261103T131231Z-1-001" / "Object_list_THA"
CACHE_DIR = HERE / "output" / "cache"

ANALYSIS_START = 1793254800  # 29.10 06:20:00 UTC = 07:20 CET
SWITCH_START = 1793257980    # 29.10 07:13:00 UTC = 08:13 CET
SWITCH_END = 1793258100      # 29.10 07:15:00 UTC = 08:15 CET
ANALYSIS_END = 1793269500    # 29.10 10:25:00 UTC = 11:25 CET
DAY = 86400
CET_OFFSET = 3600            # CET = UTC + 1 h
WINDOW = 300                 # 5-minute windows
FRAME_HZ = 10.0
OU_SKIP_FILES = {"object_list+occupations.log.2026-10-29_06-20-00.000.gz"}

CLOCK_OFFSET = 0.08          # ouster_ts ~= newsense_ts + 0.08 s
PAIR_TOL = 0.06              # max |dt| for frame pairing
MATCH_MAX_DIST = 2.0         # detection matching gate (m)
NS_SCORE_MIN = 0.25
GRID = 2.0                   # common-region / night grid cell size (m)
REGION_MIN_SPEED = 1.0

# Gate thresholds (never tune to make a gate pass)
GATE_ALIGN_MEDIAN_MIN = 0.70
GATE_ALIGN_B_WINDOW_MIN = 0.50
GATE_ALIGN_SPEED = 4.0
GATE_ALIGN_DIST = 1.0
GATE_OFFSETS = np.round(np.arange(-0.30, 0.3001, 0.05), 2) + 0.0
GATE_OFFSET_RANGE = (0.0, 0.15)

# Metric parameters
FLICKER_S = 1.0
TRACK_SPLIT_GAP = 30.0       # same tid reappearing after this silence (s) is treated as a new track
MOVING_DISP = 3.0
STATIC_MIN_S = 10.0
STATIC_RADIUS = 1.0
HANDOVER_DT = 2.0
HANDOVER_DIST = 1.5
SPEED_LIMIT = {"ped": 4.0, "bike": 15.0, "veh": 30.0}
FRAG_MIN_MATCHED = 30
FRAG_MIN_FRAMES_PER_ID = 5
UNCONFIRMED_SHARE = 0.10
TRAVERSAL_MIN_S = 2.0

# Scorecard decision rule
TIE_REL = 0.05               # relative difference below which a row is a tie
CLEAR_MAJORITY = 2 / 3       # share of comparable VRU rows a sensor must win
MIN_TRACKS_FOR_ROW = 10      # rows with fewer tracks on either side are unscored

GROUPS = ["ped", "bike", "veh", "unk"]
VRU = ["ped", "bike"]
SENSORS = ["newsense", "ouster"]
COLORS = {"newsense": "#2a78d6", "ouster": "#eb6834"}  # fixed per sensor in every figure
LABELS = {"newsense": "NewSense", "ouster": "Ouster"}

NS_GROUP = {"Pedestrian": "ped", "Cyclist": "bike", "Car": "veh", "Van": "veh",
            "Truck": "veh", "Bus": "veh", "Motorcycle": "veh"}
OU_GROUP = {"PERSON": "ped", "BICYCLE": "bike", "VEHICLE": "veh",
            "LARGE_VEHICLE": "veh", "UNKNOWN": "unk"}


def log(msg: str) -> None:
    """Progress line visible in the terminal even under nbconvert."""
    print(msg, flush=True)
    try:
        if sys.__stderr__ is not None and sys.stdout is not sys.__stdout__:
            print(msg, file=sys.__stderr__, flush=True)
    except Exception:
        pass


def to_cet(ts):
    return pd.to_datetime(np.asarray(ts) + CET_OFFSET, unit="s")


# --------------------------------------------------------------------------
# Run-mode configuration (the ONLY place where sample and full differ)
# --------------------------------------------------------------------------
NIGHT_START = 1793235600  # 29.10 01:00 UTC = 02:00 CET


def mode_config(mode: str) -> dict:
    if mode == "sample":
        epochs = {"A": (1793257200, 1793257800), "B": (1793261700, 1793262300)}
        night = {"N": (NIGHT_START, NIGHT_START + 300)}
        day28 = {"B": (1793261700 - DAY, 1793262300 - DAY)}
        region_min = 5
    elif mode == "full":
        epochs = {"A": (ANALYSIS_START, SWITCH_START), "B": (SWITCH_END, ANALYSIS_END)}
        night = {"N": (NIGHT_START, NIGHT_START + 1800)}
        day28 = {"A": (ANALYSIS_START - DAY, SWITCH_START - DAY),
                 "B": (SWITCH_END - DAY, ANALYSIS_END - DAY)}
        region_min = 30
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return dict(mode=mode, epochs=epochs, night=night, day28=day28, region_min=region_min,
                out=HERE / "output" / mode)


# --------------------------------------------------------------------------
# File catalogue (names only, never opened)
# --------------------------------------------------------------------------
_NS_RE = re.compile(r"k305_object_list_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})_to_(\d{2})-(\d{2})\.json$")
_OU_RE = re.compile(r"object_list\+occupations\.log\.(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})\.000\.gz$")


def _epoch_of(date: str, hh: int, mm: int, ss: int = 0) -> int:
    return int(pd.Timestamp(f"{date} {hh:02d}:{mm:02d}:{ss:02d}", tz="UTC").timestamp())


def catalog_newsense(date: str) -> pd.DataFrame:
    d = NS_DIR / f"k305_object_list_{date}_aggregation_5min"
    rows = []
    for p in sorted(d.glob("*.json")):
        m = _NS_RE.search(p.name)
        if not m:
            continue
        start = _epoch_of(m.group(1), int(m.group(2)), int(m.group(3))) - CET_OFFSET  # names are CET
        rows.append(dict(path=p, sensor="newsense", start=start, end=start + WINDOW))
    return pd.DataFrame(rows)


def catalog_ouster() -> pd.DataFrame:
    rows = []
    for p in sorted(OU_DIR.glob("*.gz")):
        m = _OU_RE.search(p.name)
        if not m:
            continue
        end = _epoch_of(m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)))  # names are window END in UTC
        rows.append(dict(path=p, sensor="ouster", end=end))
    df = pd.DataFrame(rows).sort_values("end").reset_index(drop=True)
    df["start"] = df["end"].shift(1).fillna(df["end"].iloc[0] - WINDOW).astype(int)
    df["skip"] = df["path"].map(lambda p: p.name in OU_SKIP_FILES)
    return df[["path", "sensor", "start", "end", "skip"]]


def select_files(cat: pd.DataFrame, ranges) -> list[Path]:
    """Files whose [start, end) overlaps any of the (t0, t1) ranges."""
    ranges = list(ranges)
    keep = np.zeros(len(cat), bool)
    for t0, t1 in ranges:
        keep |= (cat["start"].values < t1) & (cat["end"].values > t0)
    if "skip" in cat:
        keep &= ~cat["skip"].values
    return list(cat.loc[keep, "path"])


def files_for_mode(mode: str) -> dict[str, list[Path]]:
    cfg = mode_config(mode)
    ou = catalog_ouster()
    ns29 = catalog_newsense("2026-10-29")
    ns28 = catalog_newsense("2026-10-28")
    return {
        "ouster": select_files(ou, cfg["epochs"].values()),
        "newsense_29": select_files(ns29, cfg["epochs"].values()),
        "newsense_night": select_files(ns29, cfg["night"].values()),
        "newsense_28": select_files(ns28, cfg["day28"].values()),
    }


def check_full_mode_files() -> pd.DataFrame:
    """List the files full mode would load and check they exist, without opening them."""
    files = files_for_mode("full")
    expected = {"newsense_29": 49, "ouster": 47, "newsense_night": 6, "newsense_28": 49}
    rows = []
    for k, v in files.items():
        rows.append(dict(set=k, n_files=len(v), expected=expected[k], all_exist=all(p.exists() for p in v),
                     first=v[0].name if v else "", last=v[-1].name if v else ""))
    df = pd.DataFrame(rows)
    bad = df[(df.n_files != df.expected) | ~df.all_exist]
    if len(bad):
        raise RuntimeError(f"full-mode file check failed:\n{bad}")
    return df


# --------------------------------------------------------------------------
# Parsing and caching (native coordinates)
# --------------------------------------------------------------------------
DET_COLS = ["ts", "tid", "cls_raw", "grp", "score", "x", "y", "vx", "vy",
            "length", "width", "height", "npts"]


def cache_paths(src: Path) -> tuple[Path, Path]:
    stem = src.name.replace(".json", "").replace(".000.gz", "")
    return CACHE_DIR / f"{stem}.det.parquet", CACHE_DIR / f"{stem}.frames.parquet"


def _finish(det_rows: dict, frame_ts: list, frame_n: list, frame_dup: list, det_path: Path, fr_path: Path, sensor: str):
    det = pd.DataFrame(det_rows)
    if len(det) == 0:
        det = pd.DataFrame({c: pd.Series(dtype="float64") for c in DET_COLS})
    det["tid"] = det["tid"].astype("int64")
    for c in ["score", "x", "y", "vx", "vy", "length", "width", "height"]:
        det[c] = det[c].astype("float32")
    det["npts"] = det["npts"].astype("float32")
    det["cls_raw"] = det["cls_raw"].astype("category")
    det["grp"] = det["grp"].astype("category")
    fr = pd.DataFrame({"ts": np.asarray(frame_ts, float), "nobj": np.asarray(frame_n, np.int32),
                       "dup_after": np.asarray(frame_dup, np.int32)})
    det = det[DET_COLS]
    tmp_d, tmp_f = det_path.with_suffix(".tmp"), fr_path.with_suffix(".tmp")
    det.to_parquet(tmp_d, index=False)
    fr.to_parquet(tmp_f, index=False)
    os.replace(tmp_f, fr_path)   # frames first: the det file marks completion
    os.replace(tmp_d, det_path)
    return dict(src=det_path.name, sensor=sensor, n_det=len(det), n_frames=len(fr), n_dup=int(fr.dup_after.sum()))


def _new_rows():
    return {c: [] for c in DET_COLS}


def parse_newsense_file(src) -> dict:
    src = Path(src)
    det_path, fr_path = cache_paths(src)
    with open(src, "r") as f:
        doc = json.load(f)
    rows = _new_rows()
    frame_ts, frame_n, frame_dup = [], [], []
    last_ts = None
    for fr in doc["frames"]:
        t = fr["frame_timestamp"]
        ts = t["seconds"] + t["nanosec"] * 1e-9
        if last_ts is not None and ts == last_ts:
            frame_dup[-1] += 1   # keep the first frame, drop and count the second
            continue
        last_ts = ts
        objs = fr.get("objects") or []
        frame_ts.append(ts); frame_n.append(len(objs)); frame_dup.append(0)
        for o in objs:
            bb = o["bounding_box"]; pos = bb["position"]; sc = bb["scale"]; v = o.get("velocity") or {}
            cls = o.get("class_name")
            rows["ts"].append(ts); rows["tid"].append(int(o["track_id"]))
            rows["cls_raw"].append(cls); rows["grp"].append(NS_GROUP.get(cls, "unk"))
            rows["score"].append(o.get("score", np.nan))
            rows["x"].append(pos["x"]); rows["y"].append(pos["y"])
            rows["vx"].append(v.get("x", np.nan)); rows["vy"].append(v.get("y", np.nan))
            rows["length"].append(sc["x"]); rows["width"].append(sc["y"]); rows["height"].append(sc["z"])
            rows["npts"].append(np.nan)
    del doc
    return _finish(rows, frame_ts, frame_n, frame_dup, det_path, fr_path, "newsense")


def parse_ouster_lines(lines, det_path: Path, fr_path: Path) -> dict:
    rows = _new_rows()
    frame_ts, frame_n, frame_dup = [], [], []
    last_ts = None
    for line in lines:
        if '"occupations":' in line[:70]:
            continue
        if not line.strip():
            continue
        d = json.loads(line)
        if "objects" not in d:
            continue
        ts = d["timestamp"] * 1e-6
        if last_ts is not None and ts == last_ts:
            frame_dup[-1] += 1
            continue
        last_ts = ts
        objs = d["objects"] or []
        frame_ts.append(ts); frame_n.append(len(objs)); frame_dup.append(0)
        for o in objs:
            pos = o["position"]; v = o.get("velocity") or {}; dm = o.get("dimensions") or {}
            cls = o.get("classification", "UNKNOWN")
            rows["ts"].append(ts); rows["tid"].append(int(o["id"]))
            rows["cls_raw"].append(cls); rows["grp"].append(OU_GROUP.get(cls, "unk"))
            rows["score"].append(o.get("classification_confidence", np.nan))
            rows["x"].append(pos["x"]); rows["y"].append(pos["y"])
            rows["vx"].append(v.get("x", np.nan)); rows["vy"].append(v.get("y", np.nan))
            rows["length"].append(dm.get("length", np.nan)); rows["width"].append(dm.get("width", np.nan))
            rows["height"].append(dm.get("height", np.nan))
            rows["npts"].append(o.get("num_points", np.nan))
    return _finish(rows, frame_ts, frame_n, frame_dup, det_path, fr_path, "ouster")


def parse_ouster_file(src) -> dict:
    src = Path(src)
    det_path, fr_path = cache_paths(src)
    with gzip.open(src, "rt") as f:   # streamed line by line
        return parse_ouster_lines(f, det_path, fr_path)


def _parse_worker(src: str) -> dict:
    t0 = time.time()
    p = Path(src)
    info = parse_ouster_file(p) if p.name.endswith(".gz") else parse_newsense_file(p)
    info["seconds"] = round(time.time() - t0, 1)
    return info


def build_cache(files, max_workers: int = 6) -> pd.DataFrame:
    """Parse every source file not yet cached. One progress line per file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    files = [Path(f) for f in files]
    todo = [f for f in files if not cache_paths(f)[0].exists()]
    log(f"cache: {len(files) - len(todo)} of {len(files)} files already cached, {len(todo)} to parse")
    out = []
    if todo:
        # big Ouster files first for better load balance
        todo.sort(key=lambda p: (not p.name.endswith(".gz"), p.name))
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_parse_worker, str(f)): f for f in todo}
            from concurrent.futures import as_completed
            for i, fut in enumerate(as_completed(futs), 1):
                info = fut.result()
                out.append(info)
                log(f"  [{i}/{len(todo)}] {info['src']}: {info['n_frames']} frames, {info['n_det']} detections, "
                    f"{info['n_dup']} duplicate ts, {info['seconds']} s (elapsed {time.time() - t0:.0f} s)")
    return pd.DataFrame(out)


def cache_size_mb() -> float:
    return sum(p.stat().st_size for p in CACHE_DIR.glob("*.parquet")) / 1e6 if CACHE_DIR.exists() else 0.0


# --------------------------------------------------------------------------
# Transforms
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rigid2D:
    theta: float  # radians
    tx: float
    ty: float

    @staticmethod
    def deg(theta_deg: float, tx: float, ty: float) -> "Rigid2D":
        return Rigid2D(math.radians(theta_deg), tx, ty)

    def compose(self, other: "Rigid2D") -> "Rigid2D":
        """self ∘ other: apply other first, then self."""
        c, s = math.cos(self.theta), math.sin(self.theta)
        tx = c * other.tx - s * other.ty + self.tx
        ty = s * other.tx + c * other.ty + self.ty
        return Rigid2D(self.theta + other.theta, tx, ty)

    def inverse(self) -> "Rigid2D":
        c, s = math.cos(-self.theta), math.sin(-self.theta)
        return Rigid2D(-self.theta, -(c * self.tx - s * self.ty), -(s * self.tx + c * self.ty))

    def apply(self, x, y):
        c, s = math.cos(self.theta), math.sin(self.theta)
        return c * x - s * y + self.tx, s * x + c * y + self.ty

    def rotate(self, vx, vy):
        c, s = math.cos(self.theta), math.sin(self.theta)
        return c * vx - s * vy, s * vx + c * vy


NS_TO_B = Rigid2D.deg(95.8, -12.72, 6.10)
NS_TO_A = Rigid2D.deg(170.8, -18.15, 4.67)
OU_A_TO_B = NS_TO_B.compose(NS_TO_A.inverse())
IDENTITY = Rigid2D(0.0, 0.0, 0.0)


def _apply_inplace(df: pd.DataFrame, T: Rigid2D, mask=None):
    if mask is None:
        mask = np.ones(len(df), bool)
    if not mask.any():
        return
    x, y = T.apply(df.loc[mask, "x"].values.astype(float), df.loc[mask, "y"].values.astype(float))
    vx, vy = T.rotate(df.loc[mask, "vx"].values.astype(float), df.loc[mask, "vy"].values.astype(float))
    df.loc[mask, "x"] = x; df.loc[mask, "y"] = y
    df.loc[mask, "vx"] = vx; df.loc[mask, "vy"] = vy


def to_common_frame(det: pd.DataFrame, sensor: str) -> pd.DataFrame:
    """Transform to the epoch-B Ouster frame (the common frame), in memory."""
    det = det.copy()
    for c in ["x", "y", "vx", "vy"]:
        det[c] = det[c].astype("float64")
    if sensor == "newsense":
        _apply_inplace(det, NS_TO_B)
    else:
        # Ouster positions before the recalibration are in the epoch-A frame
        _apply_inplace(det, OU_A_TO_B, det["ts"].values < SWITCH_START)
    return det


# --------------------------------------------------------------------------
# Loading into memory
# --------------------------------------------------------------------------
@dataclass
class SensorData:
    sensor: str
    day: str
    det: pd.DataFrame      # detections in common frame, with epoch, trk, fidx
    frames: pd.DataFrame   # emitted frames: ts, nobj, dup_after, epoch, fidx
    ranges: dict
    n_id_reuse_splits: int = 0


def load_sensor(sensor: str, files, ranges: dict, day: str = "29") -> SensorData:
    """Load cached files, drop data outside `ranges` (epoch label -> (t0, t1)), transform to the common frame."""
    dets, frs = [], []
    for f in files:
        dp, fp = cache_paths(Path(f))
        if not dp.exists():
            raise FileNotFoundError(f"not cached: {f}; run build_cache first")
        dets.append(pd.read_parquet(dp)); frs.append(pd.read_parquet(fp))
    det = pd.concat(dets, ignore_index=True)
    fr = pd.concat(frs, ignore_index=True).sort_values("ts", kind="stable")
    # duplicate timestamps across file boundaries (same rule: keep first)
    dup_mask = fr["ts"].duplicated(keep="first")
    if dup_mask.any():
        fr = fr[~dup_mask]
    fr = fr.reset_index(drop=True)
    for c in ["cls_raw", "grp"]:
        det[c] = det[c].astype(str).astype("category")
    det = det.drop_duplicates(["ts", "tid"], keep="first")

    def label(ts):
        lab = np.full(len(ts), "", dtype=object)
        for k, (t0, t1) in ranges.items():
            lab[(ts >= t0) & (ts < t1)] = k
        return lab

    fr["epoch"] = label(fr["ts"].values)
    fr = fr[fr["epoch"] != ""].reset_index(drop=True)
    fr["fidx"] = np.arange(len(fr), dtype=np.int64)  # index in this sensor's emitted frame list
    det["epoch"] = label(det["ts"].values)
    det = det[det["epoch"] != ""]
    det = det[np.isin(det["ts"].values, fr["ts"].values)]
    det["epoch"] = det["epoch"].astype("category")
    det = to_common_frame(det, sensor)
    det["fidx"] = np.searchsorted(fr["ts"].values, det["ts"].values).astype(np.int64)
    # a track never spans epochs or days; a tid reused after a long silence starts a new track
    det = det.sort_values(["epoch", "tid", "ts"], kind="stable").reset_index(drop=True)
    ep = det["epoch"].cat.codes.values; tid = det["tid"].values; ts = det["ts"].values
    split = np.r_[False, (ep[1:] == ep[:-1]) & (tid[1:] == tid[:-1]) & (np.diff(ts) > TRACK_SPLIT_GAP)]
    newtrk = np.r_[True, (ep[1:] != ep[:-1]) | (tid[1:] != tid[:-1])] | split
    det["trk"] = (np.cumsum(newtrk) - 1).astype(np.int64)
    det["speed"] = np.hypot(det["vx"].values, det["vy"].values)
    return SensorData(sensor, day, det, fr, dict(ranges), int(split.sum()))


def track_group(det: pd.DataFrame) -> pd.Series:
    """Most frequent non-unk group per track; 'unk' if always unk."""
    known = det[det["grp"] != "unk"]
    if len(known):
        cnt = known.groupby(["trk", "grp"]).size().reset_index(name="n")
        cnt = cnt.sort_values(["trk", "n", "grp"], ascending=[True, False, True])
        g = cnt.drop_duplicates("trk").set_index("trk")["grp"]
    else:
        g = pd.Series(dtype=object)
    return g.reindex(det["trk"].unique()).fillna("unk")


def make_variant(sd: SensorData, variant: str) -> SensorData:
    det = sd.det
    if variant == "filtered":
        if sd.sensor == "newsense":
            det = det[det["score"] >= NS_SCORE_MIN]
        else:
            g = track_group(det)
            det = det[det["trk"].map(g).values != "unk"]
    elif variant != "raw":
        raise ValueError(variant)
    det = det.copy()
    det["tgrp"] = pd.Categorical(det["trk"].map(track_group(det)).values, categories=GROUPS)
    return SensorData(sd.sensor, sd.day, det.reset_index(drop=True), sd.frames, sd.ranges, sd.n_id_reuse_splits)


# --------------------------------------------------------------------------
# Frame pairing and alignment gates
# --------------------------------------------------------------------------
def pair_frames(ns_ts: np.ndarray, ou_ts: np.ndarray, offset: float = CLOCK_OFFSET, tol: float = PAIR_TOL) -> np.ndarray:
    """For each NewSense frame the index of the nearest Ouster frame to ts+offset, or -1."""
    target = ns_ts + offset
    j = np.searchsorted(ou_ts, target)
    j0 = np.clip(j - 1, 0, len(ou_ts) - 1); j1 = np.clip(j, 0, len(ou_ts) - 1)
    d0 = np.abs(ou_ts[j0] - target); d1 = np.abs(ou_ts[j1] - target)
    best = np.where(d1 < d0, j1, j0)
    dbest = np.minimum(d0, d1)
    out = np.where(dbest <= tol, best, -1)
    # one-to-one: if two NewSense frames pick the same Ouster frame, keep the nearer one
    acc = np.flatnonzero(out >= 0)
    order = acc[np.lexsort((dbest[acc], out[acc]))]
    dup = np.r_[False, out[order][1:] == out[order][:-1]]
    out[order[dup]] = -1
    return out


def pair_conflicts(ns_ts: np.ndarray, ou_ts: np.ndarray, offset: float = CLOCK_OFFSET, tol: float = PAIR_TOL) -> int:
    """NewSense frames left unpaired only because a nearer NewSense frame took their Ouster frame."""
    target = ns_ts + offset
    j = np.searchsorted(ou_ts, target)
    j0 = np.clip(j - 1, 0, len(ou_ts) - 1); j1 = np.clip(j, 0, len(ou_ts) - 1)
    within = np.minimum(np.abs(ou_ts[j0] - target), np.abs(ou_ts[j1] - target)) <= tol
    return int(within.sum() - (pair_frames(ns_ts, ou_ts, offset, tol) >= 0).sum())


def _window_of(ts):
    return (np.floor(np.asarray(ts) / WINDOW) * WINDOW).astype(np.int64)


def alignment_share(ns: SensorData, ou: SensorData, offset: float = CLOCK_OFFSET, by_window=True) -> pd.DataFrame:
    """Share of NewSense veh detections > 4 m/s with an Ouster veh detection within 1 m in the paired frame.
    Denominator: detections in paired frames only."""
    nf, of = ns.frames, ou.frames
    pair = pair_frames(nf["ts"].values, of["ts"].values, offset)
    q = ns.det[(ns.det["grp"] == "veh") & (ns.det["speed"] > GATE_ALIGN_SPEED)]
    pj = pair[q["fidx"].values]
    q = q[pj >= 0]; pj = pj[pj >= 0]
    r = ou.det[ou.det["grp"] == "veh"]
    big = 1e4  # frame index embedded as a far-apart third coordinate
    tree = cKDTree(np.c_[r["x"].values, r["y"].values, r["fidx"].values * big])
    d, _ = tree.query(np.c_[q["x"].values, q["y"].values, pj * big], k=1, distance_upper_bound=GATE_ALIGN_DIST)
    hit = np.isfinite(d)
    out = pd.DataFrame({"window": _window_of(q["ts"].values), "epoch": q["epoch"].values, "hit": hit})
    if not by_window:
        return pd.DataFrame({"share": [hit.mean() if len(hit) else np.nan], "n": [len(hit)]})
    g = out.groupby(["epoch", "window"]).agg(share=("hit", "mean"), n=("hit", "size")).reset_index()
    g["window_cet"] = pd.to_datetime(g["window"] + CET_OFFSET, unit="s")
    return g


def gate_alignment(tab: pd.DataFrame) -> dict:
    med = float(tab["share"].median())
    b_min = float(tab.loc[tab.epoch == "B", "share"].min())
    ok = med >= GATE_ALIGN_MEDIAN_MIN and b_min >= GATE_ALIGN_B_WINDOW_MIN
    res = dict(gate="alignment", median_share=round(med, 3), min_epochB_window=round(b_min, 3), passed=ok)
    if not ok:
        raise RuntimeError(f"GATE 1 (alignment) FAILED: {res}")
    return res


def clock_offset_scan(ns: SensorData, ou: SensorData, windows) -> pd.DataFrame:
    rows = []
    for w in windows:
        nsw = SensorData(ns.sensor, ns.day, ns.det[_window_of(ns.det["ts"]) == w], ns.frames, ns.ranges)
        for off in GATE_OFFSETS:
            s = alignment_share(nsw, ou, float(off), by_window=False)
            rows.append(dict(window=w, offset=float(off), share=float(s["share"].iloc[0]), n=int(s["n"].iloc[0])))
    df = pd.DataFrame(rows)
    df["window_cet"] = pd.to_datetime(df["window"] + CET_OFFSET, unit="s")
    return df


def gate_clock(scan: pd.DataFrame) -> dict:
    mean = scan.groupby("offset")["share"].mean()
    best = float(mean.idxmax())
    ok = GATE_OFFSET_RANGE[0] - 1e-9 <= best <= GATE_OFFSET_RANGE[1] + 1e-9
    res = dict(gate="clock_offset", best_offset_s=best, share_at_best=round(float(mean.max()), 3),
               passed=ok)
    if not ok:
        raise RuntimeError(f"GATE 2 (clock offset) FAILED: {res}")
    return res


def expected_windows(ranges: dict) -> pd.DataFrame:
    rows = []
    for ep, (t0, t1) in ranges.items():
        w = (t0 // WINDOW) * WINDOW
        while w < t1:
            lo, hi = max(w, t0), min(w + WINDOW, t1)
            rows.append(dict(epoch=ep, window=w, duration=hi - lo))
            w += WINDOW
    return pd.DataFrame(rows)


def gate_coverage(variants: dict, ranges: dict) -> pd.DataFrame:
    """variants: {sensor: SensorData (filtered)}. Every 5-minute window of each epoch must have data."""
    exp = expected_windows(ranges)
    out = exp.copy()
    for s, sd in variants.items():
        cnt = sd.det.groupby(_window_of(sd.det["ts"])).size()
        out[f"n_det_{s}"] = out["window"].map(cnt).fillna(0).astype(int)
    out["window_cet"] = pd.to_datetime(out["window"] + CET_OFFSET, unit="s")
    missing = out[(out[[f"n_det_{s}" for s in variants]] == 0).any(axis=1)]
    if len(missing):
        raise RuntimeError(f"GATE 3 (coverage) FAILED, windows without data:\n{missing}")
    return out


# --------------------------------------------------------------------------
# Common region
# --------------------------------------------------------------------------
def cell_of(x, y):
    return np.floor(np.asarray(x) / GRID).astype(np.int64), np.floor(np.asarray(y) / GRID).astype(np.int64)


def _cell_key(ix, iy):
    return ix * 100003 + iy


@dataclass
class Region:
    keys: np.ndarray  # sorted cell keys
    counts: pd.DataFrame

    def contains(self, x, y) -> np.ndarray:
        k = _cell_key(*cell_of(x, y))
        return np.isin(k, self.keys)


def build_region(ns: SensorData, ou: SensorData, epoch: str, min_count: int) -> Region:
    cnts = []
    for sd in (ns, ou):
        d = sd.det[(sd.det["epoch"] == epoch) & (sd.det["speed"] >= REGION_MIN_SPEED)]
        ix, iy = cell_of(d["x"], d["y"])
        c = pd.Series(_cell_key(ix, iy)).value_counts()
        cnts.append(c.rename(sd.sensor))
    df = pd.concat(cnts, axis=1).fillna(0).astype(int)
    keep = (df["newsense"] >= min_count) & (df["ouster"] >= min_count)
    return Region(np.sort(df.index[keep].values), df)


def add_region(sd: SensorData, region: Region) -> SensorData:
    det = sd.det.copy()
    det["in_region"] = region.contains(det["x"].values, det["y"].values)
    share = det.groupby("trk")["in_region"].mean()
    det["trk_in_region"] = det["trk"].map(share).values >= 0.5
    return SensorData(sd.sensor, sd.day, det, sd.frames, sd.ranges, sd.n_id_reuse_splits)


# --------------------------------------------------------------------------
# Track table
# --------------------------------------------------------------------------
def track_table(sd: SensorData) -> pd.DataFrame:
    d = sd.det
    g = d.groupby("trk", sort=True)
    t = pd.DataFrame({
        "epoch": g["epoch"].first().astype(str), "tid": g["tid"].first(), "tgrp": g["tgrp"].first().astype(str),
        "t0": g["ts"].min(), "t1": g["ts"].max(), "n": g.size(),
        "f0": g["fidx"].min(), "f1": g["fidx"].max(),
        "x0": g["x"].first(), "y0": g["y"].first(), "x1": g["x"].last(), "y1": g["y"].last(),
        "vx1": g["vx"].last(), "vy1": g["vy"].last(),
        "xm": g["x"].median(), "ym": g["y"].median(),
        "n_known_groups": d[d["grp"] != "unk"].groupby("trk")["grp"].nunique(),
        "n_unk": (d["grp"] == "unk").groupby(d["trk"]).sum(),
    })
    t["n_known_groups"] = t["n_known_groups"].fillna(0)
    t["dur"] = t["t1"] - t["t0"]
    t["disp"] = np.hypot(t["x1"] - t["x0"], t["y1"] - t["y0"])
    t["moving"] = t["disp"] >= MOVING_DISP
    t["span"] = t["f1"] - t["f0"] + 1
    t["missing"] = t["span"] - t["n"]
    if "trk_in_region" in d:
        t["in_region"] = g["trk_in_region"].first()
    # max distance to median position (static check)
    dm = np.hypot(d["x"].values - d["trk"].map(t["xm"]).values, d["y"].values - d["trk"].map(t["ym"]).values)
    t["max_r"] = pd.Series(dm).groupby(d["trk"].values).max()
    t["static_long"] = (t["dur"] >= STATIC_MIN_S) & (t["max_r"] <= STATIC_RADIUS)
    return t


# --------------------------------------------------------------------------
# Section 5: single-sensor metrics
# --------------------------------------------------------------------------
def stream_health(sd: SensorData) -> pd.DataFrame:
    fr = sd.frames
    exp = expected_windows(sd.ranges)
    rows = []
    for ep, sub in fr.groupby("epoch"):
        ts = sub["ts"].values
        gaps = np.diff(ts)
        w = _window_of(ts)
        cnt = pd.Series(w).value_counts()
        e = exp[exp.epoch == ep].set_index("window")
        ratio = (e.index.map(cnt).fillna(0).values / (e["duration"].values * FRAME_HZ))
        rows.append(dict(sensor=sd.sensor, day=sd.day, epoch=ep, n_frames=len(ts),
                         frames_per_5min=float(np.mean(e.index.map(cnt).fillna(0).values * WINDOW / e["duration"].values)),
                         min_window_frame_ratio=float(ratio.min()),
                         gap_share_gt_0p15s=float((gaps > 0.15).mean()) if len(gaps) else np.nan,
                         gaps_ge_0p2s=int((gaps >= 0.2).sum()),
                         duplicate_ts=int(sub["dup_after"].sum()),
                         longest_gap_s=float(gaps.max()) if len(gaps) else np.nan))
    return pd.DataFrame(rows)


def stream_health_windows(sd: SensorData) -> pd.DataFrame:
    exp = expected_windows(sd.ranges)
    cnt = pd.Series(_window_of(sd.frames["ts"].values)).value_counts()
    exp["n_frames"] = exp["window"].map(cnt).fillna(0).astype(int)
    exp["expected"] = exp["duration"] * FRAME_HZ
    exp["sensor"] = sd.sensor
    exp["window_cet"] = pd.to_datetime(exp["window"] + CET_OFFSET, unit="s")
    return exp


def _steps(d: pd.DataFrame):
    """Consecutive-frame steps within tracks. Returns mask over rows i (step from i-1 to i) and step speeds."""
    trk = d["trk"].values; f = d["fidx"].values; ts = d["ts"].values
    x = d["x"].values; y = d["y"].values
    same = np.r_[False, (trk[1:] == trk[:-1]) & (f[1:] - f[:-1] == 1)]
    dt = np.r_[np.nan, np.diff(ts)]
    dist = np.r_[np.nan, np.hypot(np.diff(x), np.diff(y))]
    with np.errstate(divide="ignore", invalid="ignore"):
        sp = dist / dt
    return same & (dt > 0), sp


def _jitter(d: pd.DataFrame, moving_trk: np.ndarray) -> tuple[float, int]:
    trk = d["trk"].values; f = d["fidx"].values; x = d["x"].values; y = d["y"].values
    if len(d) < 3:
        return np.nan, 0
    ok = (trk[2:] == trk[:-2]) & (trk[1:-1] == trk[:-2]) & (f[2:] - f[1:-1] == 1) & (f[1:-1] - f[:-2] == 1)
    ok &= np.isin(trk[1:-1], moving_trk)
    ax = x[2:] - 2 * x[1:-1] + x[:-2]; ay = y[2:] - 2 * y[1:-1] + y[:-2]
    a2 = (ax ** 2 + ay ** 2)[ok]
    return (float(np.sqrt(a2.mean())) if len(a2) else np.nan), int(ok.sum())


def handovers(tt: pd.DataFrame, ranges: dict) -> pd.Series:
    """For each track (index of tt): True if it hands over to a new track. NaN if its end is in the last 2 s of the epoch."""
    res = pd.Series(np.nan, index=tt.index, dtype=object)
    for ep, sub in tt.groupby("epoch"):
        t_end_ep = ranges[ep][1]
        starts = sub.sort_values("t0")
        st0 = starts["t0"].values; sx = starts["x0"].values; sy = starts["y0"].values
        sg = starts["tgrp"].values; sidx = starts.index.values
        for i, r in sub.iterrows():
            if r.t1 > t_end_ep - HANDOVER_DT:
                continue
            lo = np.searchsorted(st0, r.t1, side="right"); hi = np.searchsorted(st0, r.t1 + HANDOVER_DT, side="right")
            found = False
            if hi > lo:
                dt = st0[lo:hi] - r.t1
                vx = 0.0 if not np.isfinite(r.vx1) else r.vx1
                vy = 0.0 if not np.isfinite(r.vy1) else r.vy1
                px = r.x1 + vx * dt; py = r.y1 + vy * dt
                ok = (np.hypot(sx[lo:hi] - px, sy[lo:hi] - py) <= HANDOVER_DIST) & \
                     ((sg[lo:hi] == r.tgrp) | (sg[lo:hi] == "unk")) & (sidx[lo:hi] != i)
                found = bool(ok.any())
            res.loc[i] = found
    return res


def single_sensor_metrics(sd: SensorData, variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per group and epoch. Restricted to tracks with >= half of their detections in the common region."""
    tt_all = track_table(sd)
    tt_all["handover"] = handovers(tt_all, sd.ranges)
    tt = tt_all[tt_all["in_region"]] if "in_region" in tt_all else tt_all
    d = sd.det[sd.det["trk"].isin(tt.index)]
    step_ok, step_sp = _steps(d)
    rows = []
    for (ep, grp), sub in tt.groupby(["epoch", "tgrp"]):
        dd = d[d["trk"].isin(sub.index)]
        so, ss = step_ok[d["trk"].isin(sub.index).values], step_sp[d["trk"].isin(sub.index).values]
        steps = ss[so]
        lim = SPEED_LIMIT.get(grp, np.nan)
        short = sub["dur"] < FLICKER_S
        jit, njit = _jitter(dd, sub.index[sub["moving"]].values)
        hv = sub["handover"].dropna().astype(float)
        rows.append(dict(
            sensor=sd.sensor, day=sd.day, variant=variant, epoch=ep, group=grp,
            n_tracks=len(sub), n_det=int(sub["n"].sum()),
            flicker_track_share=float(short.mean()),
            flicker_det_share=float(sub.loc[short, "n"].sum() / sub["n"].sum()),
            gap_track_share=float((sub["missing"] > 0).mean()),
            gap_mean_missing_share=float((sub["missing"] / sub["span"]).mean()),
            class_multi_share=float((sub["n_known_groups"] > 1).mean()),
            unk_det_share=float(sub["n_unk"].sum() / sub["n"].sum()),
            implausible_step_share=float((steps > lim).mean()) if len(steps) and np.isfinite(lim) else np.nan,
            step_speed_p99=float(np.percentile(steps, 99)) if len(steps) else np.nan,
            n_steps=int(len(steps)),
            jitter_rms_m=jit, n_jitter=njit,
            static_long_count=int(sub["static_long"].sum()),
            static_long_det_share=float(sub.loc[sub["static_long"], "n"].sum() / sub["n"].sum()),
            handovers_per_100=float(100 * hv.mean()) if len(hv) else np.nan,
            n_handover_tracks=int(len(hv)),
        ))
    return pd.DataFrame(rows), tt_all


# --------------------------------------------------------------------------
# Section 6: cross-sensor matching
# --------------------------------------------------------------------------
def match_params_hash(extra: str = "") -> str:
    s = f"{NS_TO_B}|{NS_TO_A}|{CLOCK_OFFSET}|{PAIR_TOL}|{MATCH_MAX_DIST}|{NS_SCORE_MIN}|{TRACK_SPLIT_GAP}|v3-one2one|{extra}"
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def match_detections(ns: SensorData, ou: SensorData, mode: str, tag: str) -> tuple[pd.DataFrame, dict]:
    """One-to-one matching per paired frame (Hungarian on centre distance, class ignored, <= 2 m).
    Returns pairs with row indices into ns.det / ou.det plus stable keys; cached as Parquet."""
    nf, of = ns.frames, ou.frames
    pair = pair_frames(nf["ts"].values, of["ts"].values)
    pstats = dict(ns_frames=len(nf), ns_unpaired=int((pair < 0).sum()),
                  ns_unpaired_by_conflict=pair_conflicts(nf["ts"].values, of["ts"].values),
                  ou_frames=len(of), ou_unpaired=int(len(of) - len(np.unique(pair[pair >= 0]))))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    epochs = "".join(sorted(ns.ranges))
    cpath = CACHE_DIR / f"matches_{mode}_{tag}_{epochs}_{match_params_hash()}.parquet"
    if cpath.exists():
        m = pd.read_parquet(cpath)
    else:
        a = ns.det; b = ou.det
        pa = pair[a["fidx"].values]
        a_ok = np.where(pa >= 0)[0]
        big = 1e4
        ta = cKDTree(np.c_[a["x"].values[a_ok], a["y"].values[a_ok], pa[a_ok] * big])
        tb = cKDTree(np.c_[b["x"].values, b["y"].values, b["fidx"].values * big])
        sp = ta.sparse_distance_matrix(tb, MATCH_MAX_DIST, output_type="ndarray")
        ia = a_ok[sp["i"]]; ib = sp["j"]; dist = sp["v"]
        frame = pa[ia]
        order = np.lexsort((dist, frame))
        ia, ib, dist, frame = ia[order], ib[order], dist[order], frame[order]
        keep_a, keep_b, keep_d = [], [], []
        bounds = np.flatnonzero(np.r_[True, frame[1:] != frame[:-1], True])
        for s, e in zip(bounds[:-1], bounds[1:]):
            fa, fb, fd = ia[s:e], ib[s:e], dist[s:e]
            ua, inva = np.unique(fa, return_inverse=True); ub, invb = np.unique(fb, return_inverse=True)
            if len(ua) == len(fa) and len(ub) == len(fb):
                keep_a.append(fa); keep_b.append(fb); keep_d.append(fd)
                continue
            cost = np.full((len(ua), len(ub)), 1e6)
            cost[inva, invb] = fd
            r, c = linear_sum_assignment(cost)
            ok = cost[r, c] <= MATCH_MAX_DIST
            keep_a.append(ua[r[ok]]); keep_b.append(ub[c[ok]]); keep_d.append(cost[r[ok], c[ok]])
        ia = np.concatenate(keep_a) if keep_a else np.array([], int)
        ib = np.concatenate(keep_b) if keep_b else np.array([], int)
        dd = np.concatenate(keep_d) if keep_d else np.array([], float)
        m = pd.DataFrame({"ns_ts": a["ts"].values[ia], "ns_tid": a["tid"].values[ia],
                          "ou_ts": b["ts"].values[ib], "ou_tid": b["tid"].values[ib], "dist": dd})
        m.to_parquet(cpath, index=False)
    # map stable keys back to row indices
    ka = pd.Series(np.arange(len(ns.det)), index=pd.MultiIndex.from_arrays([ns.det["ts"].values, ns.det["tid"].values]))
    kb = pd.Series(np.arange(len(ou.det)), index=pd.MultiIndex.from_arrays([ou.det["ts"].values, ou.det["tid"].values]))
    m["ia"] = ka.reindex(pd.MultiIndex.from_arrays([m["ns_ts"].values, m["ns_tid"].values])).values
    m["ib"] = kb.reindex(pd.MultiIndex.from_arrays([m["ou_ts"].values, m["ou_tid"].values])).values
    if m[["ia", "ib"]].isna().any().any():
        raise RuntimeError("matched-pairs cache does not fit the loaded data; delete it and rerun")
    m["ia"] = m["ia"].astype(np.int64); m["ib"] = m["ib"].astype(np.int64)
    m["epoch"] = ns.det["epoch"].values[m["ia"].values]
    m["ns_trk"] = ns.det["trk"].values[m["ia"].values]; m["ou_trk"] = ou.det["trk"].values[m["ib"].values]
    m["ns_grp"] = ns.det["tgrp"].values[m["ia"].values]; m["ou_grp"] = ou.det["tgrp"].values[m["ib"].values]
    pstats["n_pairs"] = len(m)
    return m, pstats, pair


def mark_matched(ns: SensorData, ou: SensorData, m: pd.DataFrame, pair: np.ndarray):
    """Adds columns 'paired' (detection in a paired frame) and 'matched' to both det tables."""
    a = ns.det; b = ou.det
    a["paired"] = pair[a["fidx"].values] >= 0
    paired_b = np.zeros(len(ou.frames), bool); paired_b[pair[pair >= 0]] = True
    b["paired"] = paired_b[b["fidx"].values]
    a["matched"] = False; b["matched"] = False
    a.loc[m["ia"].values, "matched"] = True
    b.loc[m["ib"].values, "matched"] = True


def confirmation_rates(sd: SensorData, tt: pd.DataFrame) -> pd.DataFrame:
    d = sd.det[sd.det["paired"] & sd.det["in_region"]]
    d = d.assign(moving=d["trk"].map(tt["moving"]).values.astype(bool))
    rows = []
    for (ep, grp), sub in d.groupby(["epoch", "tgrp"]):
        mv = sub["moving"].values
        for label, mask in (("all", np.ones(len(sub), bool)), ("moving", mv), ("static", ~mv)):
            s = sub[mask]
            rows.append(dict(sensor=sd.sensor, epoch=ep, group=grp, motion=label, n_det=len(s),
                             n_tracks=s["trk"].nunique(),
                             confirmation_rate=float(s["matched"].mean()) if len(s) else np.nan))
    return pd.DataFrame(rows)


def class_confusion(m: pd.DataFrame, epoch: str) -> pd.DataFrame:
    sub = m[m["epoch"] == epoch]
    cm = pd.crosstab(sub["ns_grp"].rename("NewSense group"), sub["ou_grp"].rename("Ouster group"))
    return cm.reindex(index=GROUPS, columns=GROUPS, fill_value=0)


def fragmentation(m: pd.DataFrame, direction: str, tt_a: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """direction 'ns->ou': for each NewSense track, distinct Ouster IDs over its matched detections.
    That measures OUSTER fragmentation. 'ou->ns' measures NEWSENSE fragmentation."""
    if direction == "ns->ou":
        a_trk, b_trk, ts, measured = "ns_trk", "ou_trk", "ns_ts", "ouster"
    else:
        a_trk, b_trk, ts, measured = "ou_trk", "ns_trk", "ou_ts", "newsense"
    mm = m[m[a_trk].isin(tt_a.index[tt_a["in_region"]])].sort_values([a_trk, ts])
    per = []
    for trk, sub in mm.groupby(a_trk, sort=False):
        if len(sub) < FRAG_MIN_MATCHED:
            continue
        seq = sub[b_trk].values
        cnt = pd.Series(seq).value_counts()
        n_ids = max(1, int((cnt >= FRAG_MIN_FRAMES_PER_ID).sum()))
        changes = int((seq[1:] != seq[:-1]).sum())
        minutes = (sub[ts].iloc[-1] - sub[ts].iloc[0]) / 60
        per.append(dict(trk=trk, epoch=tt_a.loc[trk, "epoch"], group=tt_a.loc[trk, "tgrp"], n_matched=len(sub),
                        n_ids=n_ids, changes=changes, minutes=minutes))
    per = pd.DataFrame(per, columns=["trk", "epoch", "group", "n_matched", "n_ids", "changes", "minutes"])
    if len(per) == 0:
        return pd.DataFrame(columns=["direction", "measures_fragmentation_of", "epoch", "group"]), per
    agg = per.groupby(["epoch", "group"]).agg(
        n_tracks=("n_ids", "size"), mean_n_ids=("n_ids", "mean"),
        share_n_ids_ge2=("n_ids", lambda v: float((v >= 2).mean())),
        changes=("changes", "sum"), minutes=("minutes", "sum")).reset_index()
    agg["id_changes_per_min"] = agg["changes"] / agg["minutes"].where(agg["minutes"] > 0)
    agg.insert(0, "measures_fragmentation_of", measured)
    agg.insert(0, "direction", direction)
    per["direction"] = direction
    return agg, per


def unconfirmed_tracks(sd: SensorData, tt: pd.DataFrame) -> pd.DataFrame:
    d = sd.det[sd.det["paired"]]
    share = d.groupby("trk")["matched"].mean()
    t = tt[tt["in_region"]].copy()
    t["matched_share"] = share.reindex(t.index)
    t = t[t["matched_share"].notna()]
    t["unconfirmed"] = t["matched_share"] < UNCONFIRMED_SHARE
    t["sensor"] = sd.sensor
    return t


def unconfirmed_summary(un: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (s, ep, grp), sub in un.groupby(["sensor", "epoch", "tgrp"]):
        u = sub[sub["unconfirmed"]]
        rows.append(dict(sensor=s, epoch=ep, group=grp, n_tracks=len(sub), n_unconfirmed=len(u),
                         unconfirmed_share=len(u) / len(sub) if len(sub) else np.nan,
                         unconfirmed_moving=int(u["moving"].sum()), unconfirmed_static=int((~u["moving"]).sum()),
                         median_duration_s=float(u["dur"].median()) if len(u) else np.nan,
                         total_duration_s=float(u["dur"].sum())))
    return pd.DataFrame(rows)


def video_candidates(un_all: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    rows = []
    for s, sub in un_all.groupby("sensor"):
        u = sub[sub["unconfirmed"] & sub["tgrp"].isin(VRU)].sort_values("dur", ascending=False).head(n)
        rows.append(pd.DataFrame({
            "sensor": s, "epoch": u["epoch"].values, "track_id": u["tid"].values, "group": u["tgrp"].values,
            "start_cet": pd.to_datetime(u["t0"].values + CET_OFFSET, unit="s").strftime("%Y-%m-%d %H:%M:%S.%f").str[:-5],
            "end_cet": pd.to_datetime(u["t1"].values + CET_OFFSET, unit="s").strftime("%Y-%m-%d %H:%M:%S.%f").str[:-5],
            "duration_s": u["dur"].round(1).values, "moving": u["moving"].values,
            "x_common_m": u["xm"].round(1).values, "y_common_m": u["ym"].round(1).values,
            "matched_share": u["matched_share"].round(3).values}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def vru_counts(tt: pd.DataFrame, sensor: str) -> pd.DataFrame:
    t = tt[tt["in_region"] & tt["tgrp"].isin(VRU) & (tt["dur"] >= TRAVERSAL_MIN_S) & tt["moving"]]
    c = t.groupby([t["epoch"], _window_of(t["t0"].values), t["tgrp"]]).size().rename("n").reset_index()
    c.columns = ["epoch", "window", "group", "n"]
    c["sensor"] = sensor
    return c


# --------------------------------------------------------------------------
# Section 7: night check
# --------------------------------------------------------------------------
def night_static_cells(night: SensorData) -> tuple[np.ndarray, pd.DataFrame]:
    tt = track_table(night)
    st = tt[tt["static_long"] & tt["tgrp"].isin(VRU)]
    d = night.det[night.det["trk"].isin(st.index)]
    keys = np.unique(_cell_key(*cell_of(d["x"].values, d["y"].values)))
    return keys, st


def night_overlap(ns: SensorData, tt: pd.DataFrame, night_keys: np.ndarray) -> pd.DataFrame:
    """Share of daytime static-VRU NewSense detections (unmatched vs matched) in cells that held a static VRU track at night."""
    d = ns.det[ns.det["paired"] & ns.det["in_region"] & ns.det["tgrp"].isin(VRU)]
    static = ~d["trk"].map(tt["moving"]).values.astype(bool)
    d = d[static]
    inn = np.isin(_cell_key(*cell_of(d["x"].values, d["y"].values)), night_keys)
    rows = []
    for ep in sorted(d["epoch"].unique()):
        for label, mk in (("unconfirmed (unmatched)", ~d["matched"].values), ("confirmed (matched)", d["matched"].values)):
            sel = (d["epoch"].values == ep) & mk
            rows.append(dict(epoch=ep, detections=label, n_det=int(sel.sum()),
                             share_in_night_static_cells=float(inn[sel].mean()) if sel.any() else np.nan))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Section 9: scorecard
# --------------------------------------------------------------------------
# metric -> (direction, scored, note). direction: "lower" or "higher" is better.
SCORE_SPEC = {
    "flicker_track_share": ("lower", True, "share of tracks shorter than 1 s"),
    "flicker_det_share": ("lower", True, "share of detections in tracks shorter than 1 s"),
    "gap_track_share": ("lower", True, "share of tracks with at least one missing frame"),
    "gap_mean_missing_share": ("lower", True, "mean share of missing frames inside tracks"),
    "class_multi_share": ("lower", True, "share of tracks spanning more than one known group"),
    "implausible_step_share": ("lower", True, "share of frame steps above the group speed limit"),
    "jitter_rms_m": ("lower", True, "RMS second difference of position, moving tracks"),
    "handovers_per_100": ("lower", True, "ID handovers per 100 tracks"),
    "frag_mean_n_ids": ("lower", True, "mean distinct IDs of this sensor per track of the other sensor"),
    "frag_share_n_ids_ge2": ("lower", True, "share of the other sensor's tracks split into >= 2 IDs of this sensor"),
    "frag_id_changes_per_min": ("lower", True, "ID changes of this sensor per minute of matched time"),
    "confirmation_rate_moving": ("higher", True, "share of moving-track detections matched by the other sensor (miss vs false is ambiguous)"),
    "confirmation_rate_static": ("higher", False, "static detections: waiting people vs ghosts is ambiguous; context"),
    "step_speed_p99": ("lower", False, "99th percentile step speed; context"),
    "static_long_count": ("lower", False, "static tracks >= 10 s; context"),
    "static_long_det_share": ("lower", False, "share of detections in static long tracks; context"),
    "unk_det_share": ("lower", False, "share of unk detections; context (NewSense has no unk class)"),
    "n_tracks": ("lower", False, "tracks in region; context"),
    "vru_traversals": ("lower", False, "valid VRU traversals; a fragmenting sensor counts higher; context"),
}


def _better(direction, a, b):
    if not (np.isfinite(a) and np.isfinite(b)):
        return "n/a"
    scale = max(abs(a), abs(b))
    if scale == 0 or abs(a - b) / scale < TIE_REL:
        return "tie"
    lower_wins_a = a < b
    return ("newsense" if lower_wins_a else "ouster") if direction == "lower" else ("ouster" if lower_wins_a else "newsense")


def build_scorecard(single: pd.DataFrame, frag: pd.DataFrame, conf: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    s29 = single[single["day"] == "29"]
    for (variant, ep, grp), sub in s29.groupby(["variant", "epoch", "group"]):
        a = sub[sub.sensor == "newsense"]; b = sub[sub.sensor == "ouster"]
        for metric in ["flicker_track_share", "flicker_det_share", "gap_track_share", "gap_mean_missing_share",
                       "class_multi_share", "implausible_step_share", "jitter_rms_m", "handovers_per_100",
                       "step_speed_p99", "static_long_count", "static_long_det_share", "unk_det_share", "n_tracks"]:
            va = float(a[metric].iloc[0]) if len(a) else np.nan
            vb = float(b[metric].iloc[0]) if len(b) else np.nan
            na = int(a["n_tracks"].iloc[0]) if len(a) else 0
            nb = int(b["n_tracks"].iloc[0]) if len(b) else 0
            rows.append(dict(metric=metric, group=grp, epoch=ep, variant=variant, newsense=va, ouster=vb,
                             n_newsense=na, n_ouster=nb))
    # fragmentation: value for sensor X = how much X fragments (measured from the other sensor's tracks)
    for (ep, grp), sub in frag.groupby(["epoch", "group"]):
        for metric, col in (("frag_mean_n_ids", "mean_n_ids"), ("frag_share_n_ids_ge2", "share_n_ids_ge2"),
                            ("frag_id_changes_per_min", "id_changes_per_min")):
            r = {}
            n = {}
            for s in SENSORS:
                x = sub[sub["measures_fragmentation_of"] == s]
                r[s] = float(x[col].iloc[0]) if len(x) else np.nan
                n[s] = int(x["n_tracks"].iloc[0]) if len(x) else 0
            rows.append(dict(metric=metric, group=grp, epoch=ep, variant="filtered", newsense=r["newsense"],
                             ouster=r["ouster"], n_newsense=n["newsense"], n_ouster=n["ouster"]))
    for (ep, grp, motion), sub in conf[conf.motion.isin(["moving", "static"])].groupby(["epoch", "group", "motion"]):
        r = {s: sub.loc[sub.sensor == s, "confirmation_rate"] for s in SENSORS}
        n = {s: sub.loc[sub.sensor == s, "n_tracks"] for s in SENSORS}
        rows.append(dict(metric=f"confirmation_rate_{motion}", group=grp, epoch=ep, variant="filtered",
                         newsense=float(r["newsense"].iloc[0]) if len(r["newsense"]) else np.nan,
                         ouster=float(r["ouster"].iloc[0]) if len(r["ouster"]) else np.nan,
                         n_newsense=int(n["newsense"].iloc[0]) if len(n["newsense"]) else 0,
                         n_ouster=int(n["ouster"].iloc[0]) if len(n["ouster"]) else 0))
    tot = counts.groupby(["epoch", "group", "sensor"])["n"].sum().unstack("sensor")
    for (ep, grp), r in tot.iterrows():
        rows.append(dict(metric="vru_traversals", group=grp, epoch=ep, variant="filtered",
                         newsense=float(r.get("newsense", np.nan)), ouster=float(r.get("ouster", np.nan)),
                         n_newsense=int(np.nan_to_num(r.get("newsense", 0))), n_ouster=int(np.nan_to_num(r.get("ouster", 0)))))
    sc = pd.DataFrame(rows)
    sc["direction"] = sc["metric"].map(lambda m: SCORE_SPEC[m][0])
    sc["scored"] = sc["metric"].map(lambda m: SCORE_SPEC[m][1])
    sc["note"] = sc["metric"].map(lambda m: SCORE_SPEC[m][2])
    # flag metrics where one sensor is exactly zero in every row: likely structural, not a quality signal
    for m, sub in sc.groupby("metric"):
        for s in SENSORS:
            v = sub[s].dropna()
            if len(v) > 1 and (v == 0).all() and SCORE_SPEC[m][1]:
                sc.loc[sc.metric == m, "note"] += (f"; {LABELS[s]} is exactly 0 in every row, which may be structural "
                                                   f"(e.g. one class per track, no gaps reported), not measured quality")
    better = []
    for r in sc.itertuples():
        if not r.scored:
            better.append("n/a (context)")
        elif min(r.n_newsense, r.n_ouster) < MIN_TRACKS_FOR_ROW:
            better.append("n/a (too few tracks)")
        else:
            better.append(_better(r.direction, r.newsense, r.ouster))
    sc["better"] = better
    order = {g: i for i, g in enumerate(GROUPS)}
    sc["_g"] = sc["group"].map(order)
    sc = sc.sort_values(["variant", "epoch", "_g", "metric"], ascending=[True, False, True, True]).drop(columns="_g")
    return sc.reset_index(drop=True)


STRUCTURAL_METRICS = ["gap_track_share", "gap_mean_missing_share", "class_multi_share"]
# NewSense keeps one class and one score per track and never reports gaps inside a track, so it cannot lose
# these rows; the decision must hold both with and without them.


def _tally(rows: pd.DataFrame) -> dict:
    comparable = rows[rows.better.isin(["newsense", "ouster", "tie"])]
    wins = comparable["better"].value_counts()
    fw = comparable[comparable.metric.str.startswith("frag_")]["better"].value_counts()
    n = len(comparable)
    winner = None
    for s in SENSORS:
        other = [o for o in SENSORS if o != s][0]
        if n and wins.get(s, 0) / n >= CLEAR_MAJORITY and fw.get(s, 0) >= fw.get(other, 0):
            winner = s
    return dict(n=n, wins=wins, fw=fw, winner=winner, comparable=comparable, skipped=len(rows) - n)


def decide(sc: pd.DataFrame, mode: str) -> str:
    rows = sc[(sc.variant == "filtered") & (sc.epoch == "B") & sc.group.isin(VRU) & sc.scored]
    full = _tally(rows)
    nostruct = _tally(rows[~rows.metric.isin(STRUCTURAL_METRICS)])
    lines = []
    if mode == "sample":
        lines.append("PROVISIONAL: sample mode, based on 10 minutes per epoch. Not a basis for a decision.")
    lines.append(f"Run mode: {mode}. Decision rows: filtered variant, epoch B, ped and bike, scored metrics.")
    lines.append(f"Comparable rows: {full['n']} (rows skipped as n/a: {full['skipped']}).")
    for s in SENSORS:
        won = full["comparable"][full["comparable"].better == s]
        lines.append(f"{LABELS[s]} better on {len(won)} rows: " +
                     (", ".join(f"{r.metric}[{r.group}]" for r in won.itertuples()) or "none"))
    lines.append(f"Ties: {int(full['wins'].get('tie', 0))}")

    def split(t):
        return (f"NewSense {t['wins'].get('newsense', 0)}, Ouster {t['wins'].get('ouster', 0)}, "
                f"ties {t['wins'].get('tie', 0)} of {t['n']}; fragmentation rows NewSense {t['fw'].get('newsense', 0)}, "
                f"Ouster {t['fw'].get('ouster', 0)}")
    lines.append(f"Tally with all rows: {split(full)}.")
    lines.append(f"Tally without {', '.join(STRUCTURAL_METRICS)} (rows NewSense cannot lose by design): {split(nostruct)}.")

    def hl(metric, grp):
        r = sc[(sc.metric == metric) & (sc.group == grp) & (sc.epoch == "B") & (sc.variant == "filtered")]
        if not len(r):
            return f"  {metric} [{grp}]: n/a"
        r = r.iloc[0]
        return (f"  {metric} [{grp}]: NewSense {r.newsense:.3f} vs Ouster {r.ouster:.3f} "
                f"(n tracks {r.n_newsense}/{r.n_ouster}; better: {r.better})")
    lines.append("Headline numbers (epoch B, filtered):")
    for g in VRU:
        for metric in ["frag_mean_n_ids", "frag_share_n_ids_ge2", "flicker_track_share", "handovers_per_100",
                       "confirmation_rate_moving"]:
            lines.append(hl(metric, g))
    lines.append("  (frag rows: NewSense value = mean distinct NewSense IDs per Ouster track, i.e. NewSense "
                 "fragmentation; Ouster value = mean distinct Ouster IDs per NewSense track.)")
    veh = sc[(sc.variant == "filtered") & (sc.epoch == "B") & (sc.group == "veh") & sc.scored]["better"].value_counts()
    lines.append(f"Vehicle rows (context only; VRU evidence decides): NewSense {veh.get('newsense', 0)}, "
                 f"Ouster {veh.get('ouster', 0)}, ties {veh.get('tie', 0)}.")
    if full["winner"] and full["winner"] == nostruct["winner"]:
        w = full["winner"]
        rec = (f"RECOMMENDATION: {LABELS[w]}. It wins a clear majority (>= 2/3) of the comparable VRU rows, with and "
               f"without the structural rows, and does not lose the fragmentation rows.")
    else:
        reasons = []
        for name, t in (("all rows", full), ("without structural rows", nostruct)):
            lead = max(SENSORS, key=lambda s: t["wins"].get(s, 0))
            other = [o for o in SENSORS if o != lead][0]
            share = t["wins"].get(lead, 0) / t["n"] if t["n"] else float("nan")
            if t["winner"]:
                reasons.append(f"{name}: {LABELS[t['winner']]} qualifies")
            elif share >= CLEAR_MAJORITY:
                reasons.append(f"{name}: {LABELS[lead]} wins {share:.0%} of rows but loses the fragmentation rows "
                               f"({t['fw'].get(lead, 0)}-{t['fw'].get(other, 0)})")
            else:
                reasons.append(f"{name}: best is {LABELS[lead]} with {share:.0%} of rows, below the 2/3 majority")
        rec = "MIXED EVIDENCE: no sensor meets the decision rule. " + "; ".join(reasons) + "."
    if mode == "sample":
        rec = "PROVISIONAL (10 min per epoch) " + rec
    lines.append(rec)
    return "\n".join(lines)


def save_table(df: pd.DataFrame, cfg: dict, name: str, index=False):
    p = cfg["out"] / "tables"; p.mkdir(parents=True, exist_ok=True)
    df.to_csv(p / f"{name}.csv", index=index)
    return df


def save_fig(fig, cfg: dict, name: str):
    p = cfg["out"] / "figures"; p.mkdir(parents=True, exist_ok=True)
    fig.savefig(p / f"{name}.png", dpi=110, bbox_inches="tight")


def rss_mb() -> float:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return float("nan")


# --------------------------------------------------------------------------
# Plotting (one fixed colour per sensor, axes with units, epoch in titles)
# --------------------------------------------------------------------------
def plot_style():
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.dpi": 100, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.edgecolor": "#888888", "axes.titlesize": 11, "axes.labelsize": 10, "legend.frameon": False,
        "lines.linewidth": 2.0, "lines.markersize": 5,
    })


def _bars(ax, cats, vals_by_sensor, ylabel):
    x = np.arange(len(cats)); w = 0.38
    for k, s in enumerate(SENSORS):
        v = vals_by_sensor.get(s, [np.nan] * len(cats))
        ax.bar(x + (k - 0.5) * w, v, w * 0.92, color=COLORS[s], label=LABELS[s])
    ax.set_xticks(x); ax.set_xticklabels(cats); ax.set_ylabel(ylabel)


def plot_alignment(tab, title_suffix=""):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for ep, sub in tab.groupby("epoch"):
        ax.plot(sub["window_cet"], sub["share"], marker="o", color=COLORS["newsense"],
                ls="-" if ep == "B" else "--", label=f"epoch {ep}")
    ax.axhline(GATE_ALIGN_MEDIAN_MIN, color="#888888", lw=1, ls=":")
    ax.axhline(GATE_ALIGN_B_WINDOW_MIN, color="#bbbbbb", lw=1, ls=":")
    ax.axvline(pd.to_datetime(SWITCH_START + CET_OFFSET, unit="s"), color="#555555", lw=1)
    ax.text(pd.to_datetime(SWITCH_START + CET_OFFSET, unit="s"), 0.03, " recalibration 08:13", fontsize=8, color="#555555")
    ax.set_ylim(0, 1.02); ax.set_ylabel("share of NewSense vehicles >4 m/s\nwith Ouster vehicle within 1 m")
    ax.set_xlabel("5-minute window start (CET)")
    ax.set_title(f"Gate 1: alignment per window, epochs A and B {title_suffix}"); ax.legend()
    fig.autofmt_xdate()
    return fig


def plot_clock(scan, title_suffix=""):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    for w, sub in scan.groupby("window_cet"):
        ax.plot(sub["offset"], sub["share"], marker="o", color=COLORS["newsense"], alpha=0.5, lw=1.2)
    m = scan.groupby("offset")["share"].mean()
    ax.plot(m.index, m.values, color="#333333", lw=2, label="mean over windows")
    ax.axvspan(*GATE_OFFSET_RANGE, color="#eeeeee", zorder=0, label="accepted best-offset range")
    ax.axvline(CLOCK_OFFSET, color="#555555", lw=1, ls=":")
    ax.set_xlabel("offset added to NewSense time (s)"); ax.set_ylabel("alignment share")
    ax.set_title(f"Gate 2: clock offset scan, epoch B {title_suffix}"); ax.legend(fontsize=8)
    return fig


def plot_region(region: Region, ns: SensorData, ou: SensorData, epoch="B", title_suffix=""):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    k = region.keys
    ix = np.round(k / 100003).astype(np.int64); iy = k - ix * 100003
    for ax, sd in zip(axes, (ns, ou)):
        d = sd.det[(sd.det["epoch"] == epoch) & (sd.det["speed"] >= REGION_MIN_SPEED)]
        d = d.sample(min(len(d), 40000), random_state=0)
        ax.scatter(ix * GRID + GRID / 2, iy * GRID + GRID / 2, s=4, marker="s", color="#cccccc", label="common region cell")
        ax.scatter(d["x"], d["y"], s=0.3, color=COLORS[sd.sensor], alpha=0.3, label=f"{LABELS[sd.sensor]} moving detections")
        ax.set_aspect("equal"); ax.set_xlabel("x, common frame (m)")
        ax.set_title(f"{LABELS[sd.sensor]}, epoch {epoch} {title_suffix}")
        ax.legend(markerscale=6, fontsize=8, loc="upper right")
    axes[0].set_ylabel("y, common frame (m)")
    return fig


def plot_stream(win: pd.DataFrame, title_suffix=""):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for s, sub in win.groupby("sensor"):
        for ep, e in sub.groupby("epoch"):
            ax.plot(e["window_cet"], e["n_frames"] / e["expected"], marker="o", color=COLORS[s],
                    ls="-" if ep == "B" else "--", label=f"{LABELS[s]} epoch {ep}")
    ax.axhline(1.0, color="#888888", lw=1, ls=":")
    ax.set_ylabel("frames emitted / expected (10 Hz)"); ax.set_xlabel("5-minute window start (CET)")
    ax.set_ylim(0, 1.1); ax.set_title(f"Stream health: frame completeness, epochs A and B {title_suffix}")
    ax.legend(fontsize=8); fig.autofmt_xdate()
    return fig


def plot_single(single: pd.DataFrame, epoch="B", variant="filtered", title_suffix=""):
    import matplotlib.pyplot as plt
    metrics = [("flicker_track_share", "tracks < 1 s (share)"), ("gap_track_share", "tracks with gaps (share)"),
               ("class_multi_share", "tracks with >1 class (share)"), ("implausible_step_share", "implausible steps (share)"),
               ("handovers_per_100", "ID handovers per 100 tracks"), ("jitter_rms_m", "jitter RMS (m)")]
    sub = single[(single.epoch == epoch) & (single.variant == variant) & (single.day == "29")]
    cats = ["ped", "bike", "veh"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.2))
    for ax, (m, lab) in zip(axes.flat, metrics):
        vals = {s: [sub.loc[(sub.sensor == s) & (sub.group == g), m].mean() for g in cats] for s in SENSORS}
        _bars(ax, cats, vals, lab)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(f"Single-sensor track quality, epoch {epoch}, {variant} (lower is better) {title_suffix}")
    fig.tight_layout()
    return fig


def plot_confirmation(conf: pd.DataFrame, epoch="B", title_suffix=""):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    cats = ["ped", "bike", "veh"]
    for ax, motion in zip(axes, ["moving", "static"]):
        sub = conf[(conf.epoch == epoch) & (conf.motion == motion)]
        vals = {s: [sub.loc[(sub.sensor == s) & (sub.group == g), "confirmation_rate"].mean() for g in cats] for s in SENSORS}
        _bars(ax, cats, vals, "share of detections matched by the other sensor")
        ax.set_ylim(0, 1); ax.set_title(f"{motion} tracks, epoch {epoch}")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Confirmation rate (higher = more of this sensor's detections seen by the other) {title_suffix}")
    fig.tight_layout()
    return fig


def plot_fragmentation(frag: pd.DataFrame, epoch="B", title_suffix=""):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    cats = ["ped", "bike", "veh"]
    sub = frag[frag.epoch == epoch]
    for ax, (col, lab) in zip(axes, [("share_n_ids_ge2", "share of other sensor's tracks\nsplit into ≥2 IDs"),
                                     ("id_changes_per_min", "ID changes per minute of matched time")]):
        vals = {s: [sub.loc[(sub.measures_fragmentation_of == s) & (sub.group == g), col].mean() for g in cats] for s in SENSORS}
        _bars(ax, cats, vals, lab)
    axes[0].legend(title="fragmentation of", fontsize=8)
    fig.suptitle(f"Cross-sensor ID fragmentation, epoch {epoch} (lower is better) {title_suffix}")
    fig.tight_layout()
    return fig


def plot_unconfirmed_map(un: pd.DataFrame, epoch="B", title_suffix=""):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    for ax, s in zip(axes, SENSORS):
        sub = un[(un.sensor == s) & (un.epoch == epoch)]
        ok = sub[~sub["unconfirmed"]]; bad = sub[sub["unconfirmed"]]
        ax.scatter(ok["xm"], ok["ym"], s=3, color="#cccccc", label="confirmed tracks")
        for grp, mk in (("ped", "o"), ("bike", "^"), ("veh", "s")):
            b = bad[bad.tgrp == grp]
            ax.scatter(b["xm"], b["ym"], s=10, marker=mk, color=COLORS[s], alpha=0.7,
                       label=f"unconfirmed {grp} ({len(b)})")
        ax.set_aspect("equal"); ax.set_xlabel("x, common frame (m)")
        ax.set_title(f"{LABELS[s]} unconfirmed tracks, epoch {epoch}"); ax.legend(fontsize=7, loc="upper right")
    axes[0].set_ylabel("y, common frame (m)")
    fig.suptitle(f"Track median positions; unconfirmed = under 10% matched {title_suffix}")
    return fig


def plot_night(night_st: pd.DataFrame, ns: SensorData, tt: pd.DataFrame, title_suffix=""):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    d = ns.det[ns.det["paired"] & ns.det["in_region"] & ns.det["tgrp"].isin(VRU) & ~ns.det["matched"]]
    d = d[~d["trk"].map(tt["moving"]).values.astype(bool)]
    ax.scatter(d["x"], d["y"], s=1, color=COLORS["newsense"], alpha=0.3, label="day: unconfirmed static VRU detections")
    ax.scatter(night_st["xm"], night_st["ym"], s=40, facecolor="none", edgecolor="#222222",
               label=f"night: static long VRU tracks ({len(night_st)})")
    ax.set_aspect("equal"); ax.set_xlabel("x, common frame (m)"); ax.set_ylabel("y, common frame (m)")
    ax.set_title(f"NewSense night check, all day epochs {title_suffix}"); ax.legend(fontsize=8, markerscale=2)
    return fig


def plot_counts(counts: pd.DataFrame, title_suffix=""):
    import matplotlib.pyplot as plt
    c = counts.groupby(["sensor", "epoch", "window"])["n"].sum().reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [2, 1]})
    ax = axes[0]
    for (s, ep), sub in c.groupby(["sensor", "epoch"]):
        ax.plot(pd.to_datetime(sub["window"] + CET_OFFSET, unit="s"), sub["n"], marker="o", color=COLORS[s],
                ls="-" if ep == "B" else "--", label=f"{LABELS[s]} epoch {ep}")
    ax.set_ylabel("valid VRU traversals per 5 min"); ax.set_xlabel("window start (CET)")
    ax.set_title("VRU traversals over time, epochs A and B"); ax.legend(fontsize=8)
    w = c.pivot_table(index=["epoch", "window"], columns="sensor", values="n").fillna(0)
    ax = axes[1]
    for s in SENSORS:
        if s not in w:
            w[s] = 0
    ax.scatter(w["ouster"], w["newsense"], color="#555555", s=20)
    lim = max(1, float(w.values.max())) * 1.1
    ax.plot([0, lim], [0, lim], color="#aaaaaa", lw=1, ls=":")
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("Ouster traversals per 5 min"); ax.set_ylabel("NewSense traversals per 5 min")
    ax.set_title("Per-window counts, both epochs")
    fig.suptitle(f"VRU counts (ped + bike, ≥2 s, ≥3 m) {title_suffix}"); fig.tight_layout()
    return fig


def plot_day28(cmp: pd.DataFrame, title_suffix=""):
    import matplotlib.pyplot as plt
    metrics = [("flicker_track_share", "tracks < 1 s (share)"), ("gap_track_share", "tracks with gaps (share)"),
               ("handovers_per_100", "ID handovers per 100 tracks"), ("static_long_det_share", "static long det. share")]
    cats = ["ped", "bike", "veh"]
    eps = sorted(cmp["epoch"].unique(), reverse=True)
    fig, axes = plt.subplots(1, len(metrics), figsize=(14, 3.6))
    x = np.arange(len(cats)); w = 0.38
    for ax, (m, lab) in zip(axes, metrics):
        for k, (day, alpha) in enumerate((("28", 0.45), ("29", 1.0))):
            sub = cmp[(cmp.day == day) & (cmp.epoch == eps[0])]
            v = [sub.loc[sub.group == g, m].mean() for g in cats]
            ax.bar(x + (k - 0.5) * w, v, w * 0.92, color=COLORS["newsense"], alpha=alpha, label=f"{day}.10")
        ax.set_xticks(x); ax.set_xticklabels(cats); ax.set_ylabel(lab)
    axes[0].legend(fontsize=8)
    fig.suptitle(f"NewSense 28.10 vs 29.10, same clock hours, epoch {eps[0]}, filtered {title_suffix}")
    fig.tight_layout()
    return fig
