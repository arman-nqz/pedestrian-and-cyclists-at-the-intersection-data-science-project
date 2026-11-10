"""
=============================================================================
TRAFFIC NEAR-MISS ANALYSIS PIPELINE — Vectorised Edition
Intersection K305 | Default dataset: 2026-10-29 (multi-modal)
=============================================================================

Academic References:
  - TTC: Hayward (1972); Minderhoud & Bovy (2001)
  - PET: Allen et al. (1978); Laureshyn et al. (2010)
  - Safety Triangle: Heinrich (1931)

Design: Streaming per 5-min chunk; all TTC computed with NumPy broadcasting.
=============================================================================
"""

import argparse
import json, os, glob, sys, math, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    missing = exc.name or "a required package"
    raise SystemExit(
        f"Missing dependency: {missing}. Create an environment and install requirements:\n"
        "  python -m venv .venv\n"
        "  .venv/bin/python -m pip install -r requirements.txt\n"
        "  .venv/bin/python near_miss_analysis.py"
    ) from exc

# =============================================================================
# GLOBAL CONFIGURATION — easily adjustable for future datasets
# =============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent
MULTIMODAL_DATA_ROOT = PROJECT_ROOT / "database" / "Data from date of 28.10, 29.10."
DATASET_DIRS = {
    "2026-10-28": MULTIMODAL_DATA_ROOT / "newsense" / "object_list" /
                  "k305_object_list_2026-10-28_aggregation_5min",
    "2026-10-29": MULTIMODAL_DATA_ROOT / "newsense" / "object_list" /
                  "k305_object_list_2026-10-29_aggregation_5min",
}

CONFIG = {
    "TTC_THRESHOLD_SEC":        1.5,
    "PET_THRESHOLD_SEC":        1.5,
    "SMOOTHING_WINDOW":         5,
    "MIN_TRACK_LENGTH":         5,
    "MAX_VELOCITY_MS":          50.0,
    "INTERACTION_RADIUS_M":     25.0,
    "TTC_LOOKAHEAD_SEC":        5.0,
    "TTC_MIN_CLOSING_SPEED":    0.1,
    "PET_MAX_GAP_SEC":          10.0,
    "PET_VISIT_GAP_SEC":        0.25,
    "EVENT_GAP_SEC":            0.25,
    "INCLUDE_NON_VRU":          False,
    "MOTORIZED_CLASSES":  {"Car","Truck","Bus","Van","Motorcycle"},
    "VULNERABLE_CLASSES": {"Pedestrian","Cyclist"},
    "DATA_DIR":   str(DATASET_DIRS["2026-10-29"]),
    "DATASET_DATE": "2026-10-29",
    "MIN_DETECTION_SCORE":      0.25,
    "OUTPUT_DIR": "output",
    "BOUNDARY_BUFFER_SEC":      10.0,
}

# Canonical source: the requested 07:34 LiDAR configuration.  Its geometry is
# byte-identical to the 08:18, 09:04, and archived 07:34 copies; the 10:24
# configuration has a changed zone set and is intentionally not used.
EVENT_ZONES_PATH = (MULTIMODAL_DATA_ROOT / "ouster" / "10_29_7_34_29" /
                    "10_29__7_34_29_configuration" / "settings" / "event_zones.json")
PRIMARY_PET_CONFLICT_ZONES = ("CW-NB", "CW-SB", "CW-WB", "Bike-EB")
PET_FALLBACK_ZONE = "PET"
PET_EVENT_COLUMNS = [
    "zone_name", "zone_id", "zone_center_x", "zone_center_y", "ts", "tsl",
    "tid1", "tid2", "cls1", "cls2", "cat1", "cat2",
    "entry_ts1", "exit_ts1", "entry_ts2", "exit_ts2",
    "entry_tsl1", "exit_tsl1", "entry_tsl2", "exit_tsl2",
    "pet", "nm", "itype",
]

# Numeric category codes for vectorised logic
CAT_MOTOR = 1; CAT_VUL = 2; CAT_OTHER = 0
DEFAULTS_RADIUS = {
    "Car":1.5,"Truck":2.5,"Bus":3.5,"Van":1.8,
    "Motorcycle":0.8,"Pedestrian":0.4,"Cyclist":0.7,
}

# =============================================================================
# MODULE 1: PARSING
# =============================================================================

def parse_chunk(chunk:Dict) -> pd.DataFrame:
    rows = []
    for frame in chunk.get("frames",[]):
        ts  = frame["frame_timestamp"]["seconds"] + frame["frame_timestamp"]["nanosec"]*1e-9
        tsl = frame.get("timestamp_local","")
        for obj in frame.get("objects",[]):
            # The enhanced ITS classifier supplies a continuous detection
            # confidence.  Discard low-confidence edge reflections before
            # they can enter smoothing, TTC, or PET calculations.
            try:
                score = float(obj.get("score", 1.0))
            except (TypeError, ValueError):
                score = 0.0
            if score < CONFIG["MIN_DETECTION_SCORE"]:
                continue
            bb  = obj.get("bounding_box",{})
            pos = bb.get("position",{})
            vel = obj.get("velocity",{})
            sc  = bb.get("scale",{})
            L   = sc.get("x",np.nan); W = sc.get("y",np.nan)
            r   = (0.5*math.sqrt(L*L+W*W) if not (math.isnan(L) or math.isnan(W))
                   else DEFAULTS_RADIUS.get(obj.get("class_name","Car"),1.5))
            cn  = obj.get("class_name","Unknown")
            if cn in CONFIG["MOTORIZED_CLASSES"]:  cat = CAT_MOTOR
            elif cn in CONFIG["VULNERABLE_CLASSES"]: cat = CAT_VUL
            else: cat = CAT_OTHER
            rows.append((ts, tsl, int(obj["track_id"]), cn, cat,
                         pos.get("x",np.nan), pos.get("y",np.nan),
                         vel.get("x",np.nan), vel.get("y",np.nan), r, score))
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows, columns=["ts","tsl","tid","cls","cat","x","y","vx","vy","r","score"])


def map_timestamp_to_video(ts_local_str: str) -> Dict[str, object]:
    """Map a local ISO-8601 event timestamp to its Miovision video segments.

    ISO offsets are deliberately parsed from the value itself, so CET (+01:00)
    and CEST (+02:00) input timestamps are both handled without conversion to
    UTC.  The recordings cover local time from 06:00 inclusive to 13:00
    exclusive; each returned playback offset is relative to its one-hour file.
    """
    unavailable = "No recording (video active 06:00-13:00)"
    result: Dict[str, object] = {
        "has_video": False,
        "video_available": False,
        "video_playback_offset": "",
        "video_file_scu3k2": unavailable,
        "video_file_scu4yv": unavailable,
        "video_path_scu3k2": unavailable,
        "video_path_scu4yv": unavailable,
    }
    if not ts_local_str:
        return result

    try:
        # fromisoformat accepts +01:00/+02:00; normalising Z also supports
        # standard UTC ISO strings should a future export contain one.
        local_dt = datetime.fromisoformat(str(ts_local_str).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return result

    if not 6 <= local_dt.hour < 13:
        return result

    date_dash = local_dt.date().isoformat()
    date_underscore = local_dt.strftime("%Y_%m_%d")
    part_idx = f"{local_dt.hour - 6 + 1:03d}"
    offset_seconds = local_dt.minute * 60 + local_dt.second
    offset_mm_ss = f"{offset_seconds // 60:02d}:{offset_seconds % 60:02d}"
    base3 = f"Standard_SCU3K2_{date_dash}_0600.{part_idx}.mp4"
    base4 = f"Standard_SCU4YV_{date_dash}_0600.{part_idx}.mp4"
    video_dir = Path("database") / "Data from date of 28.10, 29.10." / "mio vision" / "miovision" / "K305" / date_underscore
    result.update({
        "has_video": True,
        "video_available": True,
        "video_playback_offset": offset_mm_ss,
        "video_file_scu3k2": base3,
        "video_file_scu4yv": base4,
        "video_path_scu3k2": str(video_dir / f"Standard_SCU3K2_{date_dash}_0600" / base3),
        "video_path_scu4yv": str(video_dir / f"Standard_SCU4YV_{date_dash}_0600" / base4),
    })
    return result


def _attach_video_columns(events: pd.DataFrame, timestamp_column: str = "timestamp_local") -> pd.DataFrame:
    """Return a copy of events enriched with the CSV video-validation fields."""
    video_columns = ["video_available", "video_playback_offset", "video_file_scu3k2", "video_file_scu4yv"]
    if events.empty:
        return events.reindex(columns=[*events.columns, *[c for c in video_columns if c not in events]])
    mapped = events[timestamp_column].fillna("").map(map_timestamp_to_video)
    video_df = pd.DataFrame(mapped.tolist(), index=events.index)
    result = events.copy()
    for column in video_columns:
        result[column] = video_df[column]
    return result

# =============================================================================
# MODULE 2: PREPROCESSING (vectorised per-track smoothing)
# =============================================================================

def rolling_mean_1d(arr:np.ndarray, w:int) -> np.ndarray:
    """Centre-aligned rolling mean without pandas overhead."""
    hw = w//2
    out = np.empty_like(arr, dtype=float)
    n = len(arr)
    for i in range(n):
        lo = max(0,i-hw); hi = min(n,i+hw+1)
        out[i] = np.nanmean(arr[lo:hi])
    return out


def extract_boundary_tail(df: pd.DataFrame, buffer_sec: float) -> pd.DataFrame:
    """Return raw rows from the tail of df within buffer_sec of the last timestamp.

    These rows are passed to the next chunk's preprocess_chunk() call as a
    carry-over prefix so that boundary-straddling tracks are not truncated.
    """
    if df.empty:
        return pd.DataFrame()
    cutoff = df["ts"].max() - buffer_sec
    return df[df["ts"] >= cutoff].copy()


def _chunks_are_consecutive(path_a: Path, path_b: Path) -> bool:
    """Return True if path_b immediately follows path_a in the 5-minute grid."""
    import re
    pat = re.compile(r'_(\d{2})-(\d{2})_to_(\d{2})-(\d{2})\.json$')
    ma = pat.search(path_a.name)
    mb = pat.search(path_b.name)
    if not ma or not mb:
        return False
    end_a   = int(ma.group(3)) * 60 + int(ma.group(4))
    start_b = int(mb.group(1)) * 60 + int(mb.group(2))
    return end_a == start_b


def preprocess_chunk(df: pd.DataFrame, quality: Optional[Dict[str,int]] = None,
                     boundary_tail: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if df.empty:
        return df
    W = CONFIG["SMOOTHING_WINDOW"]; VMAX = CONFIG["MAX_VELOCITY_MS"]; MINLEN = CONFIG["MIN_TRACK_LENGTH"]

    # Record the maximum timestamp of the carry-over tail (used to strip it back out later)
    tail_ts_max: Optional[float] = None
    if boundary_tail is not None and not boundary_tail.empty:
        tail_ts_max = float(boundary_tail["ts"].max())
        # Prepend tail rows to give boundary-straddling tracks their missing history.
        # Tail rows are raw (unsmoothed); they are stripped from the output after smoothing.
        df = pd.concat([boundary_tail, df], ignore_index=True)

    # Keep direct callers and deterministic tests using the legacy row schema
    # compatible with score-aware de-duplication.
    if "score" not in df.columns:
        df = df.copy()
        df["score"] = 1.0

    # Dedup: retain the highest-confidence detection for each (timestamp, track).
    before_dedup = len(df)
    df = df.sort_values(["tid", "ts", "score"], ascending=[True, True, False]).drop_duplicates(subset=["ts", "tid"])
    if quality is not None:
        quality["duplicate_rows_removed"] += before_dedup - len(df)

    # Outlier velocity
    spd = np.sqrt(df["vx"] ** 2 + df["vy"] ** 2)
    bad = spd > VMAX
    if quality is not None:
        quality["velocity_outliers_removed"] += int(bad.sum())
    df.loc[bad, "vx"] = np.nan
    df.loc[bad, "vy"] = np.nan

    # Per-track smoothing — using pandas groupby but only for short arrays
    parts = []
    for tid, g in df.groupby("tid", sort=False):
        g = g.sort_values("ts")
        if len(g) < MINLEN:
            if quality is not None:
                quality["short_tracks_removed"] += 1
            continue
        arr = g[["x", "y", "vx", "vy"]].values.astype(float)
        # Linear interpolation over NaN
        for col in range(4):
            a = arr[:, col]
            nans = np.isnan(a)
            if nans.any() and (~nans).any():
                xp = np.where(~nans)[0]; fp = a[~nans]
                a[nans] = np.interp(np.where(nans)[0], xp, fp)
            arr[:, col] = rolling_mean_1d(a, W)
        g = g.copy()
        g["x"]  = arr[:, 0]; g["y"]  = arr[:, 1]
        g["vx"] = arr[:, 2]; g["vy"] = arr[:, 3]
        g["spd"] = np.sqrt(g["vx"] ** 2 + g["vy"] ** 2)
        parts.append(g)

    if not parts:
        return pd.DataFrame()
    result = pd.concat(parts, ignore_index=True)

    # Strip the carry-over tail rows so they are not double-counted in global stats.
    if tail_ts_max is not None:
        result = result[result["ts"] > tail_ts_max]

    return result

# =============================================================================
# MODULE 3: VECTORISED TTC
# =============================================================================

def compute_ttc_vectorised(frame_df:pd.DataFrame) -> List[Dict]:
    """
    Compute TTC for all pairs in one frame using numpy broadcasting.
    O(N²) pairs evaluated simultaneously as array operations.

    Math:
      Δr = r2-r1,  Δv = v1-v2  (closing velocity)
      d²(t) = |Δr - Δv·t|² = R²
      → a·t²+b·t+c=0 where
          a = |Δv|²
          b = -2(Δr·Δv)
          c = |Δr|²-R²
      TTC = smallest positive real root.

    Ref: Hayward (1972)
    """
    recs = frame_df.to_dict("records")
    n = len(recs)
    if n < 2: return []

    xs  = np.array([r["x"]  for r in recs])
    ys  = np.array([r["y"]  for r in recs])
    vxs = np.array([r["vx"] for r in recs])
    vys = np.array([r["vy"] for r in recs])
    rs  = np.array([r["r"]  for r in recs])
    cats= np.array([r["cat"] for r in recs])
    spds= np.array([r["spd"] for r in recs])

    # Pairwise differences using broadcasting
    dx  = xs[:,None] - xs[None,:]     # (n,n)
    dy  = ys[:,None] - ys[None,:]
    dvx = vxs[:,None] - vxs[None,:]  # closing velocity
    dvy = vys[:,None] - vys[None,:]
    R   = rs[:,None] + rs[None,:]     # combined radii

    a = dvx**2 + dvy**2
    # Relative position at time t is d(t) = d(0) + (v1-v2)t.
    # A positive TTC therefore requires objects to be approaching, not separating.
    b = 2.0*(dx*dvx + dy*dvy)
    c = dx**2 + dy**2 - R**2
    disc = b**2 - 4.0*a*c

    VMIN2 = CONFIG["TTC_MIN_CLOSING_SPEED"]**2
    MAXTTC = CONFIG["TTC_LOOKAHEAD_SEC"]
    THRESH  = CONFIG["TTC_THRESHOLD_SEC"]
    RMAX2   = CONFIG["INTERACTION_RADIUS_M"]**2

    # Masks
    dist2 = dx**2+dy**2
    motor_vru = (((cats[:,None] == CAT_MOTOR) & (cats[None,:] == CAT_VUL))
                 | ((cats[:,None] == CAT_VUL) & (cats[None,:] == CAT_MOTOR)))
    category_mask = ((cats[:,None]!=CAT_OTHER) | (cats[None,:]!=CAT_OTHER)) if CONFIG["INCLUDE_NON_VRU"] else motor_vru
    valid = (np.triu(np.ones((n,n),bool),k=1)          # upper-triangle only
             & (dist2 <= RMAX2)                          # spatial filter
             & category_mask                              # motorised-vulnerable by default
             & (a >= VMIN2)                              # has relative motion
             & (disc >= 0)                               # real solution
             & (c >= 0))                                 # not already overlapping

    results = []
    if not valid.any(): return results

    ii, jj = np.where(valid)
    sq   = np.sqrt(disc[ii,jj])
    a_   = a[ii,jj]; b_ = b[ii,jj]
    t1   = (-b_ - sq)/(2*a_)
    t2   = (-b_ + sq)/(2*a_)
    # Smallest positive root
    t1_pos = np.where(t1>0, t1, np.inf)
    t2_pos = np.where(t2>0, t2, np.inf)
    ttc_arr = np.minimum(t1_pos, t2_pos)

    keep = (ttc_arr > 0) & (ttc_arr <= MAXTTC)
    for k in np.where(keep)[0]:
        i,j = int(ii[k]), int(jj[k])
        ttc = float(ttc_arr[k])
        o1  = recs[i]; o2 = recs[j]
        results.append({
            "ts":    o1["ts"],
            "tsl":   o1.get("tsl",""),
            "tid1":  o1["tid"],
            "tid2":  o2["tid"],
            "cls1":  o1["cls"],
            "cls2":  o2["cls"],
            "cat1":  o1["cat"],
            "cat2":  o2["cat"],
            "xmid":  (o1["x"]+o2["x"])*0.5,
            "ymid":  (o1["y"]+o2["y"])*0.5,
            "spd1":  float(spds[i]),
            "spd2":  float(spds[j]),
            "dist":  float(math.sqrt(float(dist2[i,j]))),
            "ttc":   ttc,
            "nm":    ttc < THRESH,
            "itype": f"{o1['cls']}_vs_{o2['cls']}",
        })
    return results


def run_ttc_on_chunk(df:pd.DataFrame) -> List[Dict]:
    results = []
    for ts, frame in df.groupby("ts"):
        if len(frame) >= 2:
            results.extend(compute_ttc_vectorised(frame))
    return results

# =============================================================================
# MODULE 4: PET ACCUMULATOR
# =============================================================================

def _point_in_polygon(x: float, y: float, vertices: Tuple[Tuple[float, float], ...]) -> bool:
    """Return whether a LiDAR-frame point lies in a polygon (including edges)."""
    inside = False
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        # Treat a point on an official zone boundary as inside that zone.
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            return True
        if (y1 > y) != (y2 > y):
            x_cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_cross:
                inside = not inside
    return inside


def load_pet_conflict_zones(path: Path = EVENT_ZONES_PATH) -> Dict[str, Dict]:
    """Load official LiDAR x/y polygons used for polygon-based PET.

    Only mapped crosswalk/bike conflict zones are primary.  The broad official
    ``PET`` polygon is retained as a fallback for points outside those primary
    polygons, so sidewalk, queue, and vehicle-corridor zones cannot create PET
    candidates by themselves.
    """
    with Path(path).open(encoding="utf-8") as fh:
        raw_zones = json.load(fh).get("zones", [])
    by_name = {zone.get("name"): zone for zone in raw_zones}
    required = (*PRIMARY_PET_CONFLICT_ZONES, PET_FALLBACK_ZONE)
    missing = [name for name in required if name not in by_name]
    if missing:
        raise ValueError(f"Official event-zone file is missing PET zones: {missing}")
    zones = {}
    for name in required:
        zone = by_name[name]
        vertices = tuple((float(v["x"]), float(v["y"])) for v in zone.get("vertices", []))
        if len(vertices) < 3:
            raise ValueError(f"Official PET zone {name!r} has fewer than three vertices")
        zones[name] = {"id": zone.get("id"), "vertices": vertices,
                       "center_x": float(np.mean([v[0] for v in vertices])),
                       "center_y": float(np.mean([v[1] for v in vertices]))}
    return zones


class PETAccumulator:
    """Streaming polygon-based PET accumulator using official LiDAR event zones."""

    def __init__(self, zone_path: Path = EVENT_ZONES_PATH):
        self.zones = load_pet_conflict_zones(zone_path)
        # tid → official conflict-zone name → [timestamps]
        self.data: Dict[int,Dict[Tuple,List[float]]] = defaultdict(lambda: defaultdict(list))
        self.meta: Dict[int,Dict] = {}
        # Exact frame-time to local ISO timestamp lookup for video validation.
        self.local_timestamps: Dict[float,str] = {}

    def _zone_names_for_point(self, x: float, y: float) -> List[str]:
        """Assign a trajectory point to primary polygons, or the PET fallback."""
        primary = [name for name in PRIMARY_PET_CONFLICT_ZONES
                   if _point_in_polygon(x, y, self.zones[name]["vertices"])]
        if primary:
            return primary
        return [PET_FALLBACK_ZONE] if _point_in_polygon(
            x, y, self.zones[PET_FALLBACK_ZONE]["vertices"]) else []

    def update(self, df:pd.DataFrame):
        for row in df.itertuples(index=False):
            tid=row.tid
            if tid not in self.meta:
                self.meta[tid]={"cls":row.cls,"cat":row.cat}
            if not (np.isfinite(row.x) and np.isfinite(row.y)):
                continue
            # Assignment uses the trajectory's native LiDAR x/y coordinates.
            for zone_name in self._zone_names_for_point(float(row.x), float(row.y)):
                self.data[tid][zone_name].append(float(row.ts))
            self.local_timestamps[float(row.ts)] = getattr(row, "tsl", "")

    def compute(self) -> List[Dict]:
        """Return polygon-based PET events between motorized users and VRUs.

        A visit is a contiguous sequence of observations in one polygon; a
        gap above 0.25 s starts a new visit, preventing later re-entry from
        being mistaken for continuous encroachment.  PET is the gap between
        two visits to the same physical conflict polygon (or zero if they
        overlap), which is preferable to an arbitrary 2 m grid-cell proxy.
        """
        THRESH = CONFIG["PET_THRESHOLD_SEC"]
        MAXGAP = CONFIG["PET_MAX_GAP_SEC"]
        VISITGAP = CONFIG["PET_VISIT_GAP_SEC"]
        zone_visits: Dict[str,List[Dict]] = defaultdict(list)
        for tid,zones in self.data.items():
            for zone_name,times in zones.items():
                times=np.sort(np.asarray(times, dtype=float))
                for visit in np.split(times, np.where(np.diff(times) > VISITGAP)[0] + 1):
                    if len(visit):
                        zone_visits[zone_name].append({"tid":tid, "times":visit, **self.meta[tid]})

        results=[]
        for zone_name,visits in zone_visits.items():
            if len(visits)<2: continue
            for i in range(len(visits)):
                for j in range(i+1,len(visits)):
                    v1,v2=visits[i],visits[j]
                    if v1["tid"] == v2["tid"]: continue
                    c1,c2=v1["cat"],v2["cat"]
                    motor_vru=(c1,c2) in {(CAT_MOTOR,CAT_VUL),(CAT_VUL,CAT_MOTOR)}
                    if not CONFIG["INCLUDE_NON_VRU"] and not motor_vru: continue
                    if CONFIG["INCLUDE_NON_VRU"] and c1==CAT_OTHER and c2==CAT_OTHER: continue
                    a1,a2=v1["times"],v2["times"]
                    if min(abs(a1.mean()-a2.mean()), abs(a1.min()-a2.max()), abs(a2.min()-a1.max())) > MAXGAP: continue
                    pet=_calc_pet(a1,a2)
                    if pet is None: continue
                    c1s,c2s=v1["cls"],v2["cls"]
                    entry1,exit1=float(a1.min()),float(a1.max())
                    entry2,exit2=float(a2.min()),float(a2.max())
                    event_ts=min(entry1, entry2)
                    zone=self.zones[zone_name]
                    results.append({
                        "zone_name":zone_name,"zone_id":zone["id"],
                        "zone_center_x":zone["center_x"],"zone_center_y":zone["center_y"],
                        "ts":event_ts,"tsl":self.local_timestamps.get(event_ts, ""),
                        "tid1":v1["tid"],"tid2":v2["tid"],
                        "cls1":c1s,"cls2":c2s,
                        "cat1":c1,"cat2":c2,
                        "entry_ts1":entry1,"exit_ts1":exit1,
                        "entry_ts2":entry2,"exit_ts2":exit2,
                        "entry_tsl1":self.local_timestamps.get(entry1, ""),
                        "exit_tsl1":self.local_timestamps.get(exit1, ""),
                        "entry_tsl2":self.local_timestamps.get(entry2, ""),
                        "exit_tsl2":self.local_timestamps.get(exit2, ""),
                        "pet":round(pet,4),
                        "nm": pet<THRESH,
                        "itype":f"{c1s}_vs_{c2s}",
                    })
        return results


def _calc_pet(a1:np.ndarray, a2:np.ndarray) -> Optional[float]:
    """Calculate PET between two occupancy time-arrays at a shared zone."""
    e1,x1 = a1.min(),a1.max()
    e2,x2 = a2.min(),a2.max()
    if not (x1<e2 or x2<e1): return 0.0  # simultaneous
    return float(e2-x1) if x1<e2 else float(e1-x2)

# =============================================================================
# MODULE 5: SVG PLOTS (zero external dependencies)
# =============================================================================

class SVG:
    C={"bg":"#f8f9fa","grid":"#dee2e6","ax":"#212529",
       "red":"#e74c3c","blue":"#2980b9","green":"#27ae60",
       "grey":"#95a5a6","orange":"#e67e22","purple":"#8e44ad"}

    def __init__(self,w,h,title=""):
        self.w=w;self.h=h;self.t=title
        self.pl=88;self.pr=42;self.pt=68;self.pb=78
        self.e=[]

    def _px(self,x,xmn,xmx):
        return self.pl+(x-xmn)/max(xmx-xmn,1e-9)*(self.w-self.pl-self.pr)
    def _py(self,y,ymn,ymx):
        return self.h-self.pb-(y-ymn)/max(ymx-ymn,1e-9)*(self.h-self.pt-self.pb)

    def _e(self,s): self.e.append(s)

    def rect(self,x,y,w,h,f,op=1,st="none",sw=0,rx=0):
        self._e(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{f}" opacity="{op}" stroke="{st}" stroke-width="{sw}" rx="{rx}"/>')
    def circ(self,cx,cy,r,f,op=0.75):
        self._e(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{f}" opacity="{op}"/>')
    def ln(self,x1,y1,x2,y2,st="#333",sw=1.5,dash=""):
        d=f' stroke-dasharray="{dash}"' if dash else ""
        self._e(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{st}" stroke-width="{sw}"{d}/>')
    def txt(self,x,y,s,an="middle",sz=12,bold=False,fill="#212529",rot=None):
        fw="bold" if bold else "normal"
        r=f' transform="rotate({rot},{x:.1f},{y:.1f})"' if rot else ""
        self._e(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{an}" font-size="{sz}" font-family="Arial,sans-serif" font-weight="{fw}" fill="{fill}"{r}>{s}</text>')

    def axes(self,xmn,xmx,ymn,ymx,xl,yl,nt=6):
        pw=self.w-self.pl-self.pr; ph=self.h-self.pt-self.pb
        x0=self.pl; x1=x0+pw; y0=self.h-self.pb; y1=self.pt
        self.rect(x0,y1,pw,ph,self.C["bg"],st=self.C["grid"],sw=1)
        for i in range(nt+1):
            gx=x0+pw*i/nt; gy=y0-ph*i/nt
            self.ln(gx,y1,gx,y0,self.C["grid"],0.6)
            self.ln(x0,gy,x1,gy,self.C["grid"],0.6)
            self.txt(gx,y0+20,f"{xmn+(xmx-xmn)*i/nt:.2g}",sz=10)
            self.txt(x0-10,gy+4,f"{ymn+(ymx-ymn)*i/nt:.2g}",an="end",sz=10)
        self.ln(x0,y0,x1,y0,self.C["ax"])
        self.ln(x0,y0,x0,y1,self.C["ax"])
        self.txt((x0+x1)/2,self.h-12,xl,sz=13,bold=True)
        self.txt(16,(y0+y1)/2+4,yl,sz=13,bold=True,rot=-90)
        self.txt(self.w/2,34,self.t,sz=15,bold=True)
        return xmn,xmx,ymn,ymx

    def scatter(self,xs,ys,xmn,xmx,ymn,ymx,c,sz=5,op=0.72):
        for x,y in zip(xs,ys):
            self.circ(self._px(x,xmn,xmx),self._py(y,ymn,ymx),sz,c,op)

    def vline(self,xv,xmn,xmx,ymn,ymx,c="red",d="6,3"):
        px=self._px(xv,xmn,xmx); self.ln(px,self.pt,px,self.h-self.pb,c,1.8,d)
    def hline(self,yv,xmn,xmx,ymn,ymx,c="red",d="6,3"):
        py=self._py(yv,ymn,ymx); self.ln(self.pl,py,self.w-self.pr,py,c,1.8,d)

    def bars(self,xs,counts,bw,ymx):
        ph=self.h-self.pt-self.pb; y0=self.h-self.pb
        for x,cnt,c in xs:
            bh=cnt/max(ymx,1)*ph
            self.rect(x,y0-bh,bw-1,bh,c,0.85)

    def legend(self,items,lx=None,ly=None):
        lx=lx or self.w-self.pr-185; ly=ly or self.pt+10
        self.rect(lx-5,ly-5,192,len(items)*24+14,"white",st="#ccc",sw=1,rx=5)
        for i,(col,lbl) in enumerate(items):
            cy=ly+14+i*24
            self.circ(lx+10,cy,9,col,0.85)
            self.txt(lx+24,cy+5,lbl,an="start",sz=11)

    def save(self,path):
        os.makedirs(os.path.dirname(path),exist_ok=True)
        hdr=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'
             f'<rect width="{self.w}" height="{self.h}" fill="white"/>\n')
        with open(path,"w") as f:
            f.write(hdr+"\n".join(self.e)+"\n</svg>")
        print(f"  [plot] {os.path.basename(path)}")


def _hist(vals,nbins,vmin,vmax):
    edges=np.linspace(vmin,vmax,nbins+1)
    counts,_=np.histogram(vals,bins=edges)
    return counts,edges

def mk_ttc_hist(ttc_df,out):
    if ttc_df.empty: return
    vals=ttc_df["ttc"].dropna().values
    n=25; vmin,vmax=0,CONFIG["TTC_LOOKAHEAD_SEC"]
    counts,edges=_hist(vals,n,vmin,vmax)
    cv=SVG(820,520,"TTC Distribution — All Interactions (K305)")
    ymax=float(counts.max())*1.15 or 10
    cv.axes(vmin,vmax,0,ymax,"TTC (seconds)","Count")
    pw=cv.w-cv.pl-cv.pr; bw=pw/n
    th=CONFIG["TTC_THRESHOLD_SEC"]
    xs=[(cv.pl+i*bw,counts[i],cv.C["red"] if (edges[i]+edges[i+1])/2<th else cv.C["blue"]) for i in range(n)]
    cv.bars(xs,counts,bw,ymax)
    cv.vline(th,vmin,vmax,0,ymax,cv.C["ax"])
    cv.legend([(cv.C["red"],f"Near-miss TTC<{th}s"),(cv.C["blue"],"Safe")])
    cv.save(os.path.join(out,"plot_ttc_histogram.svg"))

def mk_pet_hist(pet_df,out):
    if pet_df.empty: return
    vals=pet_df["pet"].dropna().values
    n=25; vmin,vmax=0,CONFIG["PET_MAX_GAP_SEC"]
    counts,edges=_hist(vals,n,vmin,vmax)
    cv=SVG(820,520,"Polygon-Based PET Distribution — Official Conflict Zones (K305)")
    ymax=float(counts.max())*1.15 or 10
    cv.axes(vmin,vmax,0,ymax,"PET (seconds)","Count")
    pw=cv.w-cv.pl-cv.pr; bw=pw/n
    th=CONFIG["PET_THRESHOLD_SEC"]
    xs=[(cv.pl+i*bw,counts[i],cv.C["red"] if (edges[i]+edges[i+1])/2<th else cv.C["green"]) for i in range(n)]
    cv.bars(xs,counts,bw,ymax)
    cv.vline(th,vmin,vmax,0,ymax,cv.C["ax"])
    cv.legend([(cv.C["red"],f"Near-miss PET<{th}s"),(cv.C["green"],"Safe")])
    cv.save(os.path.join(out,"plot_pet_histogram.svg"))

def mk_heatmap(traj_xs,traj_ys,cx,cy,out):
    if len(traj_xs)==0: return
    xmn=float(np.percentile(traj_xs,1)); xmx=float(np.percentile(traj_xs,99))
    ymn=float(np.percentile(traj_ys,1)); ymx=float(np.percentile(traj_ys,99))
    cv=SVG(820,700,"Spatial Conflict Heatmap — Intersection K305")
    cv.axes(xmn,xmx,ymn,ymx,"X Position (m)","Y Position (m)")
    np.random.seed(42)
    idx=np.random.choice(len(traj_xs),min(4000,len(traj_xs)),replace=False)
    cv.scatter(traj_xs[idx],traj_ys[idx],xmn,xmx,ymn,ymx,cv.C["grey"],sz=2,op=0.25)
    if cx:
        cv.scatter(cx,cy,xmn,xmx,ymn,ymx,cv.C["red"],sz=9,op=0.8)
    cv.legend([(cv.C["grey"],"All trajectories"),(cv.C["red"],f"Near-misses (N={len(cx)})")])
    cv.save(os.path.join(out,"plot_conflict_heatmap.svg"))

def mk_ttc_vs_pet(ttc_df,pet_df,out):
    if ttc_df.empty or pet_df.empty: return
    nm_t=ttc_df[ttc_df["nm"]].copy(); nm_p=pet_df[pet_df["nm"]].copy()
    if nm_t.empty or nm_p.empty: return
    nm_t["pair"]=nm_t.apply(lambda r:tuple(sorted([r["tid1"],r["tid2"]])),axis=1)
    nm_p["pair"]=nm_p.apply(lambda r:tuple(sorted([r["tid1"],r["tid2"]])),axis=1)
    mg=pd.merge(nm_t[["pair","ttc","cat1","cat2"]],nm_p[["pair","pet"]],on="pair",how="inner")
    if mg.empty: return
    xmn,xmx=0,CONFIG["TTC_LOOKAHEAD_SEC"]; ymn,ymx=0,CONFIG["PET_MAX_GAP_SEC"]
    cv=SVG(820,620,"TTC vs PET — Near-Miss Events (K305)")
    cv.axes(xmn,xmx,ymn,ymx,"TTC (seconds)","PET (seconds)")
    CM={(CAT_MOTOR,CAT_VUL):cv.C["red"],(CAT_VUL,CAT_MOTOR):cv.C["red"],
        (CAT_MOTOR,CAT_MOTOR):cv.C["blue"],(CAT_VUL,CAT_VUL):cv.C["green"]}
    for _,r in mg.iterrows():
        c=CM.get((r["cat1"],r["cat2"]),cv.C["purple"])
        cv.circ(cv._px(r["ttc"],xmn,xmx),cv._py(r["pet"],ymn,ymx),7,c,0.75)
    cv.vline(CONFIG["TTC_THRESHOLD_SEC"],xmn,xmx,ymn,ymx,cv.C["ax"])
    cv.hline(CONFIG["PET_THRESHOLD_SEC"],xmn,xmx,ymn,ymx,cv.C["ax"])
    cv.legend([(cv.C["red"],"Motor vs Vulnerable"),(cv.C["blue"],"Motor vs Motor"),(cv.C["green"],"Vul vs Vul")])
    cv.save(os.path.join(out,"plot_ttc_vs_pet.svg"))

def mk_hourly(ttc_df,pet_df,out):
    counts=[0]*24
    def add(df,flag):
        if df.empty: return
        nm=df[df[flag]].copy()
        nm["dt"]=pd.to_datetime(nm["tsl" if "tsl" in nm.columns else "ts"],utc=False,errors="coerce")
        for h in nm["dt"].dt.hour.dropna().astype(int):
            if 0<=h<24: counts[h]+=1
    add(ttc_df,"nm"); add(pet_df,"nm")
    if sum(counts)==0: return
    ymax=max(counts)*1.15
    cv=SVG(900,520,"Near-Miss Events by Hour of Day — K305")
    cv.axes(0,23,0,ymax,"Hour of Day","Near-Miss Count",nt=8)
    pw=cv.w-cv.pl-cv.pr; bw=pw/24; peak={7,8,9,16,17,18}
    xs=[(cv.pl+h*bw,counts[h],cv.C["red"] if h in peak else cv.C["blue"]) for h in range(24)]
    cv.bars(xs,counts,bw,ymax)
    cv.legend([(cv.C["red"],"Peak rush hours"),(cv.C["blue"],"Off-peak")])
    cv.save(os.path.join(out,"plot_hourly_conflicts.svg"))

def mk_breakdown(ttc_df,pet_df,out):
    rows=[]
    if not ttc_df.empty:
        for t,g in ttc_df[ttc_df["nm"]].groupby("itype"):
            rows.append({"type":t,"metric":"TTC","count":len(g)})
    if not pet_df.empty:
        for t,g in pet_df[pet_df["nm"]].groupby("itype"):
            rows.append({"type":t,"metric":"PET","count":len(g)})
    if not rows: return
    bd=pd.DataFrame(rows)
    types=sorted(bd["type"].unique())
    tc={t:int(bd[(bd["type"]==t)&(bd["metric"]=="TTC")]["count"].sum()) for t in types}
    pc={t:int(bd[(bd["type"]==t)&(bd["metric"]=="PET")]["count"].sum()) for t in types}
    n=len(types); h=max(450,n*55+150)
    cv=SVG(900,h,"Near-Miss Breakdown by Interaction Type (K305)")
    xmax=max(list(tc.values())+list(pc.values()))*1.15 or 10
    cv.axes(0,xmax,0,n,"Count","Interaction Type",nt=5)
    pw=cv.w-cv.pl-cv.pr; ph=cv.h-cv.pt-cv.pb
    rh=ph/max(n,1); bh=rh*0.36
    for i,itype in enumerate(types):
        gyc=cv.h-cv.pb-(i+0.5)*rh
        bw=tc.get(itype,0)/xmax*pw; bw2=pc.get(itype,0)/xmax*pw
        cv.rect(cv.pl,gyc-bh,bw,bh,cv.C["blue"],0.85)
        cv.rect(cv.pl,gyc,bw2,bh,cv.C["red"],0.85)
        cv.txt(cv.pl-6,gyc+bh/4,itype[:38],an="end",sz=10)
    cv.legend([(cv.C["blue"],"TTC near-miss"),(cv.C["red"],"PET near-miss")])
    cv.save(os.path.join(out,"plot_interaction_breakdown.svg"))

# =============================================================================
# MODULE 6: SUMMARY
# =============================================================================

def summary(cls_dist,ttc_df,pet_df,n_frames,n_tracks,ttc_events=None,quality=None):
    s={"intersection":"K305","date":CONFIG["DATASET_DATE"],"total_frames":n_frames,
       "total_tracks":n_tracks,"class_distribution":cls_dist,"ttc":{},"pet":{}}
    if not ttc_df.empty:
        nm=ttc_df[ttc_df["nm"]]
        s["ttc"]={"total_frame_interactions":len(ttc_df),"near_miss_frame_observations":int(len(nm)),
                  "near_miss_rate_pct":round(100*len(nm)/max(len(ttc_df),1),2),
                  "min_ttc_sec":round(float(ttc_df["ttc"].min()),4),
                  "mean_ttc_sec":round(float(ttc_df["ttc"].mean()),4),
                  "by_type":nm["itype"].value_counts().to_dict()}
        if ttc_events is not None:
            s["ttc"]["near_miss_events"]=int(len(ttc_events))
    if not pet_df.empty:
        nm=pet_df[pet_df["nm"]]
        s["pet"]={"total_crossings":len(pet_df),"near_misses":int(len(nm)),
                  "near_miss_rate_pct":round(100*len(nm)/max(len(pet_df),1),2),
                  "min_pet_sec":round(float(pet_df["pet"].min()),4),
                  "mean_pet_sec":round(float(pet_df["pet"].mean()),4),
                  "by_type":nm["itype"].value_counts().to_dict()}
    if quality is not None: s["data_quality"]=dict(quality)
    return s

def print_report(s, ttc_events: Optional[pd.DataFrame] = None):
    SEP="="*72
    print(f"\n{SEP}\n  FINAL NEAR-MISS ANALYSIS REPORT — K305 | {s['date']}\n{SEP}")
    print(f"  Frames Analysed : {s['total_frames']:,}")
    print(f"  Unique Tracks   : {s['total_tracks']:,}")
    print("  Class Distribution:")
    for k,v in sorted(s["class_distribution"].items(),key=lambda x:-x[1]):
        print(f"    {k:<15}: {v:>8,}")

    def sec(title,d):
        print(f"\n  ── {title} ──")
        if not d: print("  (no data)"); return
        for k,v in d.items():
            if k=="by_type":
                print("  Near-misses by type:")
                for t,c in sorted(v.items(),key=lambda x:-x[1]):
                    print(f"    {t:<40}: {c:>5,}")
            else:
                print(f"  {k:<35}: {v}")

    sec("TIME-TO-COLLISION (TTC)",s.get("ttc",{}))
    sec("POST-ENCROACHMENT TIME (PET)",s.get("pet",{}))
    if ttc_events is not None:
        targets = ttc_events[(ttc_events["min_ttc_sec"] < 1.0) & ttc_events["video_available"]]
        print("\n  ── VIDEO VALIDATION TARGETS (TOP NEAR-MISSES < 1.0s) ──")
        if targets.empty:
            print("  (no video-available TTC events below 1.0 s)")
        else:
            for rank, (_, event) in enumerate(targets.sort_values("min_ttc_sec").head(10).iterrows(), 1):
                timestamp = str(event["timestamp_local"]).replace("T", " ")
                # Each video is one hour long, so the playback offset is MM:SS.
                offset = f"00:{event['video_playback_offset']}"
                print(f"  Rank {rank}: Min TTC = {event['min_ttc_sec']:.2f}s | {timestamp} | "
                      f"{event['class_1']} vs {event['class_2']}")
                print(f"    Camera SCU3K2: {event['video_file_scu3k2']} @ {offset}")
                print(f"    Camera SCU4YV: {event['video_file_scu4yv']} @ {offset}")
    print(f"\n{SEP}\n")

# =============================================================================
# MAIN
# =============================================================================

def legacy_main():
    np.random.seed(42)
    OUT=CONFIG["OUTPUT_DIR"]; os.makedirs(OUT,exist_ok=True)
    files=sorted(glob.glob(os.path.join(CONFIG["DATA_DIR"],"*.json")))
    if not files: raise FileNotFoundError("No JSON files found")
    N=len(files)

    print("="*72)
    print(f"  NEAR-MISS PIPELINE v3  |  K305  |  2026-10-14  |  {N} chunks")
    print("="*72)

    ttc_rows: List[Dict]=[]
    pet_acc=PETAccumulator()
    cls_set: Dict[str,set]=defaultdict(set)
    n_frames=0
    xs_samp,ys_samp=[],[]

    for fi,fpath in enumerate(files):
        bname=os.path.basename(fpath)
        print(f"  [{fi+1:>3}/{N}] {bname}",end=" ",flush=True)

        with open(fpath) as fh:
            chunk=json.load(fh)

        df=parse_chunk(chunk)
        if df.empty: print("empty"); continue
        df=preprocess_chunk(df)
        if df.empty: print("empty (preprocessed)"); continue

        n_frames+=df["ts"].nunique()
        for _,r in df.drop_duplicates("tid").iterrows():
            cls_set[r["cls"]].add(r["tid"])

        # Trajectory sample (1 in 6 points for heatmap)
        xs_samp.extend(df["x"].values[::6].tolist())
        ys_samp.extend(df["y"].values[::6].tolist())

        # TTC
        chunk_ttc=run_ttc_on_chunk(df)
        ttc_rows.extend(chunk_ttc)
        n_nm=sum(1 for r in chunk_ttc if r["nm"])

        # PET accumulation
        pet_acc.update(df)

        print(f"frames={df['ts'].nunique():>4}  TTC={len(chunk_ttc):>5}  NM={n_nm:>4}")

    # ── Build DataFrames ──────────────────────────────────────────────────
    print("\n[A] Building TTC DataFrame...")
    ttc_df=pd.DataFrame(ttc_rows)
    if not ttc_df.empty:
        print(f"  TTC interactions : {len(ttc_df):,}  |  near-misses : {ttc_df['nm'].sum():,}")

    print("[B] Computing PET...")
    pet_rows=pet_acc.compute()
    pet_df=pd.DataFrame(pet_rows, columns=PET_EVENT_COLUMNS)
    if not pet_df.empty:
        print(f"  Zone crossings   : {len(pet_df):,}  |  near-misses : {pet_df['nm'].sum():,}")

    # ── Save CSVs ─────────────────────────────────────────────────────────
    print("[C] Saving tables...")
    rename_ttc={"ts":"timestamp","tsl":"timestamp_local","tid1":"track_id_1","tid2":"track_id_2",
                "cls1":"class_1","cls2":"class_2","cat1":"category_1","cat2":"category_2",
                "xmid":"x_mid","ymid":"y_mid","spd1":"speed_1","spd2":"speed_2",
                "dist":"distance_m","ttc":"ttc_sec","nm":"is_near_miss_ttc","itype":"interaction_type"}
    rename_pet={"ts":"timestamp","tsl":"timestamp_local","zone_id":"polygon_id",
                "zone_center_x":"zone_center_x_m","zone_center_y":"zone_center_y_m",
                "tid1":"track_id_1","tid2":"track_id_2","cls1":"class_1","cls2":"class_2",
                "entry_ts1":"entry_timestamp_1","exit_ts1":"exit_timestamp_1",
                "entry_ts2":"entry_timestamp_2","exit_ts2":"exit_timestamp_2",
                "entry_tsl1":"entry_timestamp_local_1","exit_tsl1":"exit_timestamp_local_1",
                "entry_tsl2":"entry_timestamp_local_2","exit_tsl2":"exit_timestamp_local_2",
                "cat1":"category_1","cat2":"category_2","pet":"pet_sec","nm":"is_near_miss_pet","itype":"interaction_type"}

    if not ttc_df.empty:
        out=ttc_df.rename(columns=rename_ttc)
        out.to_csv(os.path.join(OUT,"all_ttc_interactions.csv"),index=False)
        nm=out[out["is_near_miss_ttc"]].sort_values("ttc_sec")
        nm.to_csv(os.path.join(OUT,"near_misses_ttc.csv"),index=False)
        print(f"  near_misses_ttc.csv  → {len(nm):,} rows")

    if not pet_df.empty:
        outp=pet_df.rename(columns=rename_pet)
        outp.to_csv(os.path.join(OUT,"all_pet_interactions.csv"),index=False)
        nmp=outp[outp["is_near_miss_pet"]].sort_values("pet_sec")
        nmp.to_csv(os.path.join(OUT,"near_misses_pet.csv"),index=False)
        print(f"  near_misses_pet.csv  → {len(nmp):,} rows")

    # ── Plots ─────────────────────────────────────────────────────────────
    print("[D] Generating plots...")
    traj_xs=np.array(xs_samp); traj_ys=np.array(ys_samp)
    cx,cy=[],[]
    if not ttc_df.empty:
        nm=ttc_df[ttc_df["nm"]]; cx+=nm["xmid"].tolist(); cy+=nm["ymid"].tolist()
    if not pet_df.empty:
        nm=pet_df[pet_df["nm"]]; cx+=nm["zone_center_x"].tolist(); cy+=nm["zone_center_y"].tolist()

    mk_ttc_hist(ttc_df,OUT)
    mk_pet_hist(pet_df,OUT)
    mk_heatmap(traj_xs,traj_ys,cx,cy,OUT)
    mk_ttc_vs_pet(ttc_df,pet_df,OUT)
    mk_hourly(ttc_df,pet_df,OUT)
    mk_breakdown(ttc_df,pet_df,OUT)

    # ── Report ────────────────────────────────────────────────────────────
    print("[E] Summary report...")
    n_tracks=sum(len(v) for v in cls_set.values())
    cld={k:len(v) for k,v in cls_set.items()}
    stats=summary(cld,ttc_df,pet_df,n_frames,n_tracks)
    print_report(stats)

    import json as _json
    def ser(o):
        if isinstance(o,(np.integer,)): return int(o)
        if isinstance(o,(np.floating,)): return float(o)
        return str(o)
    with open(os.path.join(OUT,"summary_stats.json"),"w") as f:
        _json.dump(stats,f,indent=2,default=ser)

    print(f"\n[DONE] Outputs → {OUT}\n")
    return ttc_df, pet_df, stats

if __name__=="__main__":
    pass  # The command-line entry point is defined below.


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description="K305 TTC and polygon-based PET analysis")
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument("--all", action="store_true", help="analyse every JSON chunk")
    scope.add_argument("--files", nargs="+", help="specific JSON filenames or paths")
    parser.add_argument("--date", choices=sorted(DATASET_DIRS), default="2026-10-29",
                        help="new dataset date (default: 2026-10-29); ignored when --data-dir is supplied")
    parser.add_argument("--data-dir", default=None,
                        help=f"override input directory (default: {CONFIG['DATA_DIR']})")
    parser.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--save-all", action="store_true", help="write all frame-level interactions")
    parser.add_argument("--include-non-vru", action="store_true")
    parser.add_argument("--ttc-threshold", type=float, default=CONFIG["TTC_THRESHOLD_SEC"])
    parser.add_argument("--pet-threshold", type=float, default=CONFIG["PET_THRESHOLD_SEC"])
    parser.add_argument("--min-score", type=float, default=CONFIG["MIN_DETECTION_SCORE"],
                        help="minimum continuous object-detection confidence (default: 0.25)")
    parser.add_argument("--self-test", action="store_true", help="run deterministic TTC tests and exit")
    args = parser.parse_args(argv)
    if args.data_dir is None:
        args.data_dir = str(DATASET_DIRS[args.date])
    return args


def select_files(args):
    data_dir=Path(args.data_dir)
    available=sorted(data_dir.glob("*.json"))
    if not available: raise FileNotFoundError(f"No JSON files found in {data_dir}")
    if args.files:
        files=[]
        for item in args.files:
            path=Path(item)
            path=path if path.is_file() else data_dir/path
            if not path.is_file(): raise FileNotFoundError(f"Input file not found: {item}")
            files.append(path)
        return sorted(files), "custom"
    if args.all: return available, "full_day"
    preferred=[p for p in available if any(f"_08-{m:02d}_to_08-" in p.name for m in (0,5,10))]
    return (preferred[:3] if len(preferred)>=3 else available[:3]), "sample_08-00_to_08-14"


def consolidate_ttc_events(ttc_df):
    """Collapse consecutive TTC alarms and attach video-validation metadata."""
    cols=["event_start_timestamp","event_end_timestamp","duration_sec","frames_in_event","min_ttc_sec","track_id_1","track_id_2","class_1","class_2","interaction_type","x_mid","y_mid","timestamp_local","video_available","video_playback_offset","video_file_scu3k2","video_file_scu4yv"]
    if ttc_df.empty or not ttc_df["nm"].any(): return pd.DataFrame(columns=cols)
    data=ttc_df[ttc_df["nm"]].copy()
    data["lo"]=data[["tid1","tid2"]].min(axis=1); data["hi"]=data[["tid1","tid2"]].max(axis=1)
    rows=[]
    for _, group in data.groupby(["lo","hi"], sort=False):
        group=group.sort_values("ts")
        episode=np.cumsum(np.r_[True,np.diff(group["ts"].to_numpy())>CONFIG["EVENT_GAP_SEC"]])
        for _, event in group.groupby(episode, sort=False):
            worst=event.loc[event["ttc"].idxmin()]
            rows.append({"event_start_timestamp":float(event.ts.min()),"event_end_timestamp":float(event.ts.max()),"duration_sec":round(float(event.ts.max()-event.ts.min()),4),"frames_in_event":len(event),"min_ttc_sec":round(float(worst.ttc),4),"track_id_1":int(worst.tid1),"track_id_2":int(worst.tid2),"class_1":worst.cls1,"class_2":worst.cls2,"interaction_type":worst.itype,"x_mid":round(float(worst.xmid),4),"y_mid":round(float(worst.ymid),4),"timestamp_local":worst.tsl})
    events = pd.DataFrame(rows).sort_values("min_ttc_sec", ignore_index=True)
    return _attach_video_columns(events).reindex(columns=cols)


def _test_boundary_spanning():
    """Boundary spanning test: near-miss that straddles a chunk seam.

    Two objects on a collision course. Object 1 (motor) moves right at 3 m/s
    starting from x=-10. Object 2 (VRU) moves left at 3 m/s starting from x=+10.
    They approach each other; combined radius = 1.0 m.
    Collision (gap=1.0) occurs at t = (20-1)/6 ≈ 3.167 s.

    Chunk N: t = 0.0 to 2.0 s (21 frames at 0.1 s intervals)
    Chunk N+1: t = 2.1 to 4.0 s (20 frames at 0.1 s intervals)

    Without stitching: chunk N+1 has 20 frames (≥ MINLEN), so both chunks
    process fine BUT the minimum TTC would be calculated only within each
    chunk, missing the true minimum just after the boundary.
    With stitching: the two chunks' TTC rows are combined and consolidate_ttc_events
    produces exactly 1 event spanning the seam.

    Also tests short-track stitching: if chunk N+1 starts with only 2 frames
    before the near-miss peak, without boundary tail those 2 frames would be
    dropped (< MINLEN=5).
    """
    MINLEN = CONFIG["MIN_TRACK_LENGTH"]
    BUFFER = CONFIG["BOUNDARY_BUFFER_SEC"]

    fps = 10.0  # 10 Hz
    dt = 1.0 / fps

    def make_frames(t_start, t_end):
        """Generate synthetic raw DataFrame for two objects over a time range."""
        times = np.arange(t_start, t_end + dt / 2, dt)
        rows = []
        for t in times:
            x1 = -10.0 + 3.0 * t
            x2 =  10.0 - 3.0 * t
            rows.append((round(t, 2), "", 1, "Car",        CAT_MOTOR, x1, 0.0, 3.0, 0.0, 0.5))
            rows.append((round(t, 2), "", 2, "Pedestrian", CAT_VUL,   x2, 0.0, -3.0, 0.0, 0.5))
        return pd.DataFrame(rows, columns=["ts", "tsl", "tid", "cls", "cat", "x", "y", "vx", "vy", "r"])

    # Chunk N: t=0 to t=2.0 (21 frames × 2 objects = 42 rows)
    raw_n = make_frames(0.0, 2.0)

    # Chunk N+1: only 3 frames (< MINLEN=5) — tests short-track rescue via stitching
    raw_n1_short = make_frames(2.1, 2.3)  # 3 frames per obj = 6 rows total

    # Process chunk N normally (no boundary tail)
    q_n = defaultdict(int)
    df_n = preprocess_chunk(raw_n, q_n)

    # Compute boundary tail from raw chunk N data
    tail = extract_boundary_tail(raw_n, BUFFER)

    # Without stitching: chunk N+1 short tracks should be dropped
    q_no_stitch = defaultdict(int)
    df_n1_no_stitch = preprocess_chunk(raw_n1_short, q_no_stitch)
    assert df_n1_no_stitch.empty, "Without stitching, short tracks should be dropped"

    # With stitching: chunk N+1 short tracks should be rescued
    q_stitch = defaultdict(int)
    df_n1_stitched = preprocess_chunk(raw_n1_short, q_stitch, boundary_tail=tail)
    assert not df_n1_stitched.empty, "With stitching, short tracks should be retained"

    # TTC from both chunks combined should consolidate to 1 event
    ttc_n  = run_ttc_on_chunk(df_n)
    ttc_n1 = run_ttc_on_chunk(df_n1_stitched)
    all_ttc = pd.DataFrame(ttc_n + ttc_n1)
    assert not all_ttc.empty and all_ttc["nm"].any(), "Should have near-miss frames"

    events = consolidate_ttc_events(all_ttc)
    assert len(events) == 1, f"Expected 1 consolidated event, got {len(events)}"

    # The minimum TTC should be less than TTC_THRESHOLD_SEC
    assert events.iloc[0]["min_ttc_sec"] < CONFIG["TTC_THRESHOLD_SEC"], \
        "Event min TTC should be below threshold"

    print("  ✓ boundary_spanning: 1 consolidated event, short-track rescue confirmed")


def run_ttc_self_tests():
    def make(rows): return pd.DataFrame(rows,columns=["ts","tsl","tid","cls","cat","x","y","vx","vy","r","spd"])
    def obj(tid,x,vx,cat): return (0.,"",tid,"Car" if cat==CAT_MOTOR else "Pedestrian",cat,x,0.,vx,0.,.5,abs(vx))
    cases={"approaching":(make([obj(1,-5,1,CAT_MOTOR),obj(2,5,-1,CAT_VUL)]),1,4.5,False),"separating":(make([obj(1,-5,-1,CAT_MOTOR),obj(2,5,1,CAT_VUL)]),0,None,None),"parallel":(make([obj(1,0,1,CAT_MOTOR),obj(2,5,1,CAT_VUL)]),0,None,None),"overlapping":(make([obj(1,0,1,CAT_MOTOR),obj(2,.5,-1,CAT_VUL)]),0,None,None),"threshold_boundary":(make([obj(1,-2,1,CAT_MOTOR),obj(2,2,-1,CAT_VUL)]),1,1.5,False)}
    for name,(df,count,ttc,nm) in cases.items():
        result=compute_ttc_vectorised(df); assert len(result)==count, name
        if result: assert abs(result[0]["ttc"]-ttc)<1e-9 and result[0]["nm"] is nm, name
    # --- Boundary-spanning near-miss test ---
    _test_boundary_spanning()
    print("TTC self-tests passed: approaching, separating, parallel, overlapping, threshold boundary, boundary_spanning.")


def main(argv=None):
    args=parse_args(argv)
    if args.self_test: run_ttc_self_tests(); return
    if args.ttc_threshold<=0 or args.pet_threshold<=0 or not 0 <= args.min_score <= 1:
        raise ValueError("thresholds must be positive and min-score must be between 0 and 1")
    CONFIG.update(TTC_THRESHOLD_SEC=args.ttc_threshold, PET_THRESHOLD_SEC=args.pet_threshold,
                  MIN_DETECTION_SCORE=args.min_score, INCLUDE_NON_VRU=args.include_non_vru,
                  DATA_DIR=args.data_dir, DATASET_DATE=args.date)
    files,label=select_files(args)
    def run_token(value: float) -> str:
        """Filesystem-friendly threshold token; e.g. 0.25 becomes 0p25."""
        return f"{value:.2f}".replace(".", "p")

    run_id = (
        f"k305_{args.date}_{label}_score-{run_token(args.min_score)}_"
        f"ttc-{run_token(args.ttc_threshold)}_pet-{run_token(args.pet_threshold)}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    )
    run_dir=Path(args.output_dir)/run_id; run_dir.mkdir(parents=True)
    (run_dir / "RUN_INFO.txt").write_text(
        "K305 Near-Miss Analysis Run\n"
        f"Run folder: {run_id}\n"
        f"Dataset date: {args.date}\n"
        f"Run scope: {label}\n"
        f"Input directory: {Path(args.data_dir).resolve()}\n"
        f"Selected files: {len(files)}\n"
        f"Minimum detection score: {args.min_score}\n"
        f"TTC threshold (strictly below): {args.ttc_threshold} s\n"
        f"PET threshold (strictly below): {args.pet_threshold} s\n"
        f"Created local time: {datetime.now().astimezone().isoformat()}\n"
    )
    started=time.perf_counter(); np.random.seed(42)
    print(f"NEAR-MISS PIPELINE | {label} | {len(files)} chunk(s)\nOutput: {run_dir}")
    ttc_rows=[]; pet_acc=PETAccumulator(); cls_set=defaultdict(set); quality=defaultdict(int); n_frames=0; xs=[]; ys=[]
    boundary_tail: Optional[pd.DataFrame] = None
    for i,path in enumerate(files,1):
        with open(path) as fh: raw=parse_chunk(json.load(fh))
        quality["raw_rows"]+=len(raw)
        df=preprocess_chunk(raw,quality,boundary_tail=boundary_tail)
        # Compute raw tail for the NEXT chunk (from original parsed data, before smoothing)
        # Only carry over if the next file is consecutive in the 5-min grid
        if i < len(files) and _chunks_are_consecutive(path, files[i]):
            boundary_tail = extract_boundary_tail(raw, CONFIG["BOUNDARY_BUFFER_SEC"])
        else:
            boundary_tail = None
        if df.empty: print(f"[{i}/{len(files)}] {path.name}: no retained tracks"); continue
        n_frames+=df.ts.nunique()
        for cls,tid in df[["cls","tid"]].drop_duplicates().itertuples(index=False): cls_set[cls].add(tid)
        xs.extend(df.x.values[::6]); ys.extend(df.y.values[::6])
        chunk_ttc=run_ttc_on_chunk(df); ttc_rows.extend(chunk_ttc); pet_acc.update(df)
        print(f"[{i}/{len(files)}] {path.name}: frames={df.ts.nunique()} TTC={len(chunk_ttc)} near-miss frames={sum(r['nm'] for r in chunk_ttc)}")
    ttc_df=pd.DataFrame(ttc_rows); pet_df=pd.DataFrame(pet_acc.compute(), columns=PET_EVENT_COLUMNS); ttc_events=consolidate_ttc_events(ttc_df)
    rename_ttc={"ts":"timestamp","tsl":"timestamp_local","tid1":"track_id_1","tid2":"track_id_2","cls1":"class_1","cls2":"class_2","cat1":"category_1","cat2":"category_2","xmid":"x_mid","ymid":"y_mid","spd1":"speed_1","spd2":"speed_2","dist":"distance_m","ttc":"ttc_sec","nm":"is_near_miss_ttc","itype":"interaction_type"}
    rename_pet={"ts":"timestamp","tsl":"timestamp_local","zone_id":"polygon_id","zone_center_x":"zone_center_x_m","zone_center_y":"zone_center_y_m","tid1":"track_id_1","tid2":"track_id_2","cls1":"class_1","cls2":"class_2","entry_ts1":"entry_timestamp_1","exit_ts1":"exit_timestamp_1","entry_ts2":"entry_timestamp_2","exit_ts2":"exit_timestamp_2","entry_tsl1":"entry_timestamp_local_1","exit_tsl1":"exit_timestamp_local_1","entry_tsl2":"entry_timestamp_local_2","exit_tsl2":"exit_timestamp_local_2","cat1":"category_1","cat2":"category_2","pet":"pet_sec","nm":"is_near_miss_pet","itype":"interaction_type"}
    ttc_events.to_csv(run_dir/"near_miss_ttc_events.csv",index=False)
    pet_out=_attach_video_columns(pet_df.rename(columns=rename_pet), "timestamp_local")
    if pet_out.empty:
        pet_out.to_csv(run_dir/"near_miss_pet_events.csv",index=False)
    else:
        pet_out[pet_out.is_near_miss_pet].sort_values("pet_sec").to_csv(run_dir/"near_miss_pet_events.csv",index=False)
    if args.save_all: ttc_df.rename(columns=rename_ttc).to_csv(run_dir/"all_ttc_frame_interactions.csv",index=False); pet_out.to_csv(run_dir/"all_pet_interactions.csv",index=False)
    if not args.no_plots:
        cx=[] if ttc_df.empty else ttc_df.loc[ttc_df.nm,"xmid"].tolist(); cy=[] if ttc_df.empty else ttc_df.loc[ttc_df.nm,"ymid"].tolist()
        if not pet_df.empty: cx+=pet_df.loc[pet_df.nm,"zone_center_x"].tolist(); cy+=pet_df.loc[pet_df.nm,"zone_center_y"].tolist()
        mk_ttc_hist(ttc_df,run_dir); mk_pet_hist(pet_df,run_dir); mk_heatmap(np.asarray(xs),np.asarray(ys),cx,cy,run_dir); mk_ttc_vs_pet(ttc_df,pet_df,run_dir); mk_hourly(ttc_df,pet_df,run_dir); mk_breakdown(ttc_df,pet_df,run_dir)
    quality["retained_rows"]=int(sum(len(t) for cells in pet_acc.data.values() for t in cells.values()))
    stats=summary({k:len(v) for k,v in cls_set.items()},ttc_df,pet_df,n_frames,sum(len(v) for v in cls_set.values()),ttc_events,quality)
    stats.update({"run_id":run_id,"run_scope":label,"selected_files":[p.name for p in files],"output_directory":str(run_dir),"runtime_sec":round(time.perf_counter()-started,2),"pet_method":"polygon-based PET using official LiDAR conflict zones (CW-NB, CW-SB, CW-WB, Bike-EB; PET fallback)","pet_zone_source":str(EVENT_ZONES_PATH)})
    with open(run_dir/"run_report.json","w") as fh: json.dump(stats,fh,indent=2,default=lambda o:int(o) if isinstance(o,np.integer) else float(o) if isinstance(o,np.floating) else str(o))
    print_report(stats, ttc_events); print(f"TTC near-miss events: {len(ttc_events):,}\nPolygon-based PET near-miss events: {0 if pet_df.empty else int(pet_df.nm.sum()):,}\nDone in {stats['runtime_sec']} s. Share {run_dir/'run_report.json'} for review.")
    return ttc_df,pet_df,stats


if __name__=="__main__": main()
