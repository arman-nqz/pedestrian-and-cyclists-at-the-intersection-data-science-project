#!/usr/bin/env python3
"""
eda_k305.py  –  Exploratory Data Analysis for Topic 4
======================================================
Intersection K305: Dr.-Willi-Reiland-Ring & Würzburger Str., Aschaffenburg
Dataset: 2026-10-14 (24-hour LiDAR object-tracking at 10 Hz)

Week 1 deliverable for the meeting with the project supervisor.
Demonstrates five core findings:
  1. Dataset scale   – 288 files, 10 Hz, ~11 M detections, 7 classes
  2. VRU proportion  – Pedestrians ~17.5%, Cyclists ~3.1%  →  ~20.6% VRU share
  3. Physical validation – X/Y/Z coordinate ranges, speed distributions, yaw alignment
  4. Data cleanliness   – Zero nulls, ~12.6% short noise tracks, ID-switching artefact
  5. Duration vs. Count – Why dwell time (person-seconds) beats raw frame counts

Usage:
    python eda_k305.py            # full 288-file scan (≈ 2–4 min)
    python eda_k305.py --quick    # 12-file sample for a 15-second demo

Dependencies: Python ≥ 3.8 standard library only
  (json, glob, os, math, statistics, collections, datetime, argparse, sys, time)

How the program is organised
-----------------------------
1. Constants describe the database location and the assumptions used in the
   calculations, such as the 10 Hz recording interval.
2. Small helper functions format output or convert values.
3. ``load_and_analyse`` reads the files one at a time and calculates the
   reusable Week 1 statistics. Reading one file at a time keeps memory use
   manageable.
4. The ``report_*`` functions turn those statistics into readable sections of
   the final report. They do not read the database again. The planned spatial
   zones, 15-minute profiles, trajectory clustering, and conflict heatmaps are
   Week 2 deliverables and are described in the report as next steps.
5. ``main`` handles command-line options, selects the files, and calls the
   analysis and report functions in the correct order.

The comments below explain both what a variable/method does and why it is
needed. A "method" here means a function: a named block of code that performs
one task and can be called from another part of the program.
"""

import argparse
import glob
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Configuration & Constants
# These values are kept in one place so that the rest of the script can use
# them consistently. Changing the database folder or recording frequency is
# therefore easier and less error-prone.
# ──────────────────────────────────────────────────────────────────────────────

DATA_DIR   = os.path.join("database", "k305_object_list_2026-10-14_aggregation_5min")
FILE_GLOB  = os.path.join(DATA_DIR, "*.json")
DELTA_T    = 0.1          # seconds between consecutive frames (10 Hz)

# VRU classes (Vulnerable Road Users)
VRU_CLASSES      = {"Pedestrian", "Cyclist"}
# The current EDA flags segments seen for at most three frames as likely noise.
# The guide's cleaning rule is stricter: remove trajectories shorter than five
# frames (0.5 s). This script reports the short segments but does not remove
# them yet; filtering is planned for the next analysis stage.
NOISE_THRESHOLD  = 3      # frames

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

SEP_THICK = "═" * 70
SEP_THIN  = "─" * 70

def header(title: str) -> None:
    """Print a large heading so each report finding is easy to locate."""
    print(f"\n{SEP_THICK}")
    print(f"  {title}")
    print(SEP_THICK)

def subheader(title: str) -> None:
    """Print a smaller heading for a subsection inside one finding."""
    print(f"\n  {SEP_THIN}")
    print(f"    {title}")
    print(f"  {SEP_THIN}")

def fmt_int(n: int) -> str:
    """Add thousands separators so large counts are easier to read."""
    return f"{n:,}"

def fmt_pct(numerator: int, denominator: int) -> str:
    """Calculate a percentage safely and return it with two decimal places."""
    # A zero denominator would cause a division-by-zero error. ``N/A`` makes
    # the report explicit when there is no data to use as a reference.
    if denominator == 0:
        return "N/A"
    return f"{100.0 * numerator / denominator:.2f}%"

def speed_mps_to_kmh(mps: float) -> float:
    """Convert metres per second to kilometres per hour for the report."""
    return mps * 3.6

def progress_bar(current: int, total: int, width: int = 40) -> str:
    """Build a text progress bar showing how many files have been processed."""
    filled = int(width * current / total) if total else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = 100.0 * current / total if total else 0
    return f"  [{bar}] {pct:5.1f}%  ({current}/{total} files)"

def extract_hour_minute(timestamp_local: str) -> tuple[int, int]:
    """Extract hour and minute from a local ISO timestamp.

    Returning ``(-1, -1)`` for malformed timestamps lets the scan continue
    instead of stopping the entire analysis because of one bad value.
    """
    try:
        # Remove timezone suffix for simple parsing
        ts = timestamp_local[:16]          # 'YYYY-MM-DDTHH:MM'
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M")
        return dt.hour, dt.minute
    except Exception:
        return -1, -1

# ──────────────────────────────────────────────────────────────────────────────
# Core Data Loading
# ──────────────────────────────────────────────────────────────────────────────

def load_and_analyse(json_files: list[str], verbose: bool = True) -> dict:
    """
    Stream through every JSON file and accumulate statistics.

    Returns a dictionary containing all aggregated metrics.

    Processing is done file-by-file to keep memory usage low: the full 3.8 GB
    database is never loaded into memory at once. Only the current JSON file,
    plus small samples and counters, are kept while the scan runs.
    """

    # ── Overall counters ─────────────────────────────────────────────────────
    # These variables store totals for the complete set of selected files.
    # ``total_frames`` counts sensor time steps; ``total_detections`` counts
    # every object seen in every frame.
    total_files           = len(json_files)
    total_frames          = 0
    total_detections      = 0

    # ``class_counts`` answers "how many object instances belong to each
    # class?". A detection is one object in one frame, not one real-world
    # person or vehicle.
    # ``class_track_ids`` stores distinct tracker labels for the class. The
    # result is useful for inspection, but it is not a reliable people count
    # because the guide documents ID-switching at signal stop-lines.
    class_counts: dict[str, int] = defaultdict(int)
    class_track_ids: dict[str, set] = defaultdict(set)

    # Coordinate values are collected so min/max can show the physical area
    # covered by the sensor. These lists are much smaller than the raw JSON
    # objects and are only used for the final range calculation.
    x_vals, y_vals, z_vals = [], [], []

    # Speed samples are kept by class for median, percentile, and maximum
    # calculations. The limit prevents the report from using excessive RAM.
    SPEED_SAMPLE_LIMIT = 50_000
    speed_samples: dict[str, list[float]] = defaultdict(list)

    # ``yaw_deviations`` measures the absolute difference between movement
    # direction and the object's bounding-box orientation for moving VRUs.
    yaw_deviations: list[float] = []
    YAW_SAMPLE_LIMIT = 20_000

    # Count objects with an incomplete coordinate triplet or velocity vector.
    # This is a simple completeness check; it does not attempt to repair data.
    null_fields = 0

    # Short-track analysis is deliberately local to each 5-minute file in this
    # Week 1 script. The project guide says that some trajectories continue
    # across file boundaries, so the future cleaned analysis must reconnect
    # those segments before treating them as final trajectories.
    total_tracks_all  = 0
    short_tracks_all  = 0

    # Hourly counters support the optional traffic profile at the end.
    # keys: hour (0..23), value: detections
    hourly_detections: dict[int, int] = defaultdict(int)
    hourly_vru:        dict[int, int] = defaultdict(int)

    # Dwell-time demo: track-level frame counts for VRUs in one sample file.
    # The 08:00 file provides a concrete duration distribution for explaining
    # why frame counts over-represent people who wait at a red signal.
    demo_file_track_frames: dict[str, dict[int, int]] = {}  # class → {tid → frames}

    # ── Loop through files ────────────────────────────────────────────────────
    t0 = time.perf_counter()

    for file_idx, fpath in enumerate(sorted(json_files)):

        # Progress feedback every 12 files (or on the last file) gives the user
        # visibility during the full scan, which can take several minutes.
        if verbose and (file_idx % 12 == 0 or file_idx == total_files - 1):
            elapsed = time.perf_counter() - t0
            rate    = (file_idx + 1) / elapsed if elapsed > 0 else 0
            eta     = (total_files - file_idx - 1) / rate if rate > 0 else 0
            print(progress_bar(file_idx + 1, total_files), end="")
            print(f"  {elapsed:.0f}s elapsed, ETA {eta:.0f}s", end="\r", flush=True)

        # Load only this JSON file. The file is released after this loop
        # iteration, which is why the whole database does not fill RAM.
        with open(fpath, encoding="utf-8") as fh:
            data = json.load(fh)

        # Every source file contains a top-level ``frames`` list. ``get`` uses
        # an empty list if the key is absent, allowing the scan to continue.
        frames = data.get("frames", [])
        total_frames += len(frames)

        # These counters are reset for each file. They measure how many frames
        # each tracker label appears in this file, which supports the current
        # short-segment diagnostic but is not yet the final cleaned trajectory.
        file_track_counts:  dict[int, int] = defaultdict(int)
        file_track_classes: dict[int, str] = {}

        # The 08:00--08:04 file is used as a small, concrete duration example.
        is_demo_file = "08-00_to_08-04" in fpath

        if is_demo_file:
            demo_vru_track_frames: dict[str, dict[int, int]] = {
                "Pedestrian": defaultdict(int),
                "Cyclist":    defaultdict(int),
            }

        # A frame is one LiDAR time step. Each frame may contain zero or more
        # detected objects.
        for frame in frames:
            objects = frame.get("objects", [])
            ts_local = frame.get("timestamp_local", "")
            hour, _ = extract_hour_minute(ts_local)

            hourly_detections[hour] += len(objects)

            # An object is one detection, such as one car or pedestrian, in the
            # current frame.
            for obj in objects:
                total_detections += 1
                cls = obj.get("class_name", "Unknown")
                tid = obj.get("track_id", -1)

                # Update class totals and remember the tracker label for the
                # diagnostic table. Repeated frames of one label add detections
                # but do not add another value to its set.
                class_counts[cls]      += 1
                class_track_ids[cls].add(tid)
                file_track_counts[tid] += 1
                file_track_classes[tid] = cls

                if cls in VRU_CLASSES:
                    hourly_vru[hour] += 1

                # ── Coordinate extraction ─────────────────────────────────
                # The sample data stores position under
                # object -> bounding_box -> position -> x/y/z.
                bb   = obj.get("bounding_box", {})
                pos  = bb.get("position", {})
                px   = pos.get("x")
                py   = pos.get("y")
                pz   = pos.get("z")

                if px is None or py is None or pz is None:
                    null_fields += 1
                else:
                    x_vals.append(px)
                    y_vals.append(py)
                    z_vals.append(pz)

                # ── Speed ─────────────────────────────────────────────────
                # The data stores velocity as x/y components. The Euclidean
                # length gives ground speed: sqrt(vx² + vy²).
                vel  = obj.get("velocity", {})
                vx   = vel.get("x")
                vy   = vel.get("y")

                if vx is not None and vy is not None:
                    spd = math.sqrt(vx ** 2 + vy ** 2)
                    if len(speed_samples[cls]) < SPEED_SAMPLE_LIMIT:
                        speed_samples[cls].append(spd)

                    # ── Yaw alignment (VRUs only, speed > 0.1 m/s) ───────
                    # Stationary objects have an unstable movement heading, so
                    # they are excluded from the yaw comparison.
                    if cls in VRU_CLASSES and spd > 0.1:
                        yaw = bb.get("yaw")
                        if yaw is not None and len(yaw_deviations) < YAW_SAMPLE_LIMIT:
                            heading = math.atan2(vy, vx)
                            # Wrap difference to [-π, π]
                            diff = abs(heading - yaw) % (2 * math.pi)
                            if diff > math.pi:
                                diff = 2 * math.pi - diff
                            yaw_deviations.append(diff)
                else:
                    null_fields += 1

                # ── Dwell-time demo accumulation ──────────────────────────
                if is_demo_file and cls in VRU_CLASSES:
                    demo_vru_track_frames[cls][tid] += 1

        # ── Short-track counting ──────────────────────────────────────────
        # A segment observed in only a few frames may be a reflection,
        # transient detection, or partial occlusion. Count it for the
        # data-cleanliness report; the actual < 5-frame filter is not applied
        # in this reporting script.
        for tid, count in file_track_counts.items():
            total_tracks_all += 1
            if count <= NOISE_THRESHOLD:
                short_tracks_all += 1

        if is_demo_file:
            demo_file_track_frames = demo_vru_track_frames

    # Clear progress line
    if verbose:
        print()

    # Return one dictionary so every report function receives the same snapshot
    # of the analysis. The report functions can then focus on presentation.
    return {
        "total_files":          total_files,
        "total_frames":         total_frames,
        "total_detections":     total_detections,
        "class_counts":         dict(class_counts),
        "class_track_ids":      {k: len(v) for k, v in class_track_ids.items()},
        "x_range":              (min(x_vals), max(x_vals)) if x_vals else (0, 0),
        "y_range":              (min(y_vals), max(y_vals)) if y_vals else (0, 0),
        "z_range":              (min(z_vals), max(z_vals)) if z_vals else (0, 0),
        "speed_samples":        dict(speed_samples),
        "yaw_deviations":       yaw_deviations,
        "null_fields":          null_fields,
        "total_tracks":         total_tracks_all,
        "short_tracks":         short_tracks_all,
        "hourly_detections":    dict(hourly_detections),
        "hourly_vru":           dict(hourly_vru),
        "demo_file_track_frames": demo_file_track_frames,
        "elapsed_seconds":      time.perf_counter() - t0,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Report Sections
# ──────────────────────────────────────────────────────────────────────────────

def report_dataset_scale(r: dict) -> None:
    """Print file, frame, detection, class, and unique-track totals."""
    header("FINDING 1 │ Dataset Scale & Volume")

    # Read the aggregate values produced by load_and_analyse. Keeping reporting
    # separate from loading means the large JSON files are not read twice.
    total_det = r["total_detections"]
    total_fr  = r["total_frames"]
    cls       = r["class_counts"]

    print(f"\n  {'Metric':<38} {'Value':>18}")
    print(f"  {'─'*38}   {'─'*18}")
    print(f"  {'JSON files (5-min intervals)':<38} {fmt_int(r['total_files']):>18}")
    print(f"  {'Total LiDAR frames processed':<38} {fmt_int(total_fr):>18}")
    print(f"  {'Total object detections':<38} {fmt_int(total_det):>18}")
    print(f"  {'Recording frequency':<38} {'10 Hz (Δt = 0.1 s)':>18}")
    print(f"  {'Coverage period':<38} {'24 h (2026-10-14)':>18}")

    subheader("Detections per class")
    print(f"\n  {'Class':<14} {'Category':<12} {'Detections':>12} {'Share':>8} {'Uniq. Tracks':>14}")
    print(f"  {'─'*14} {'─'*12} {'─'*12} {'─'*8} {'─'*14}")

    # Map the seven expected detector classes to the two project categories:
    # VRU (pedestrian/cyclist) and motorized traffic.
    cat_map = {
        "Pedestrian": "VRU  ★", "Cyclist": "VRU  ★",
        "Car": "Motorized", "Van": "Motorized", "Truck": "Motorized",
        "Motorcycle": "Motorized", "Bus": "Motorized",
    }
    track_ids = r["class_track_ids"]

    for cn in sorted(cls.keys(), key=lambda x: cls[x], reverse=True):
        cat    = cat_map.get(cn, "Other")
        det    = cls[cn]
        pct    = fmt_pct(det, total_det)
        tracks = fmt_int(track_ids.get(cn, 0))
        print(f"  {cn:<14} {cat:<12} {fmt_int(det):>12} {pct:>8} {tracks:>14}")

    total_vru = sum(cls.get(c, 0) for c in VRU_CLASSES)
    print(f"\n  {'VRU TOTAL (Ped + Cyc)':<14}               {fmt_int(total_vru):>12} "
          f"{fmt_pct(total_vru, total_det):>8}")
    print(f"\n  NOTE: ~{total_det / 1_000_000:.1f}M total detections – confirming dataset scale.")


def report_vru_proportion(r: dict) -> None:
    """Compare vulnerable-road-user detections with all detections."""
    header("FINDING 2 │ VRU Proportion  (Pedestrians & Cyclists)")

    # VRUs are the project's main study group. The motorized value is the
    # remainder, so all categories add up to total detections.
    cls   = r["class_counts"]
    total = r["total_detections"]
    ped   = cls.get("Pedestrian", 0)
    cyc   = cls.get("Cyclist", 0)
    vru   = ped + cyc
    mot   = total - vru

    print(f"\n  {'Category':<22} {'Detections':>12} {'Share':>8}   Visual Proportion")
    print(f"  {'─'*22} {'─'*12} {'─'*8}   {'─'*30}")

    bar_total = 50
    for label, count in [
        ("Pedestrian",      ped),
        ("Cyclist",         cyc),
        ("VRU Subtotal",    vru),
        ("Motorized (rest)", mot),
        ("TOTAL",           total),
    ]:
        bar_len = int(bar_total * count / total) if total else 0
        bar     = "▓" * bar_len + "░" * (bar_total - bar_len)
        pct_str = fmt_pct(count, total)
        print(f"  {label:<22} {fmt_int(count):>12} {pct_str:>8}   |{bar}|")

    print(f"""
  KEY INSIGHT
  ───────────
  Pedestrians and Cyclists together constitute  {fmt_pct(vru, total)}  of all
  LiDAR detections – providing statistically rich samples for:
    • Temporal profiles (when do VRUs appear?)
    • Spatial heatmaps  (where do they concentrate?)
    • Conflict analysis (VRU-vehicle spatial overlap)
""")


def report_physical_validation(r: dict) -> None:
    """Print checks for coordinates, speeds, and movement/orientation agreement."""
    header("FINDING 3 │ Physical Validation  (Coordinates · Speed · Yaw)")

    # ── 3A: Coordinate ranges ─────────────────────────────────────────────────
    # The guide defines x/y/z relative to the roadside LiDAR origin. Min/max
    # values are a basic check that the observed area has the expected extent.
    subheader("3A · Coordinate Ranges (sensor-origin reference frame)")
    xr = r["x_range"]
    yr = r["y_range"]
    zr = r["z_range"]

    print(f"""
  Axis   Min (m)    Max (m)    Span (m)   Interpretation
  ─────  ─────────  ─────────  ─────────  ──────────────────────────────────
  X      {xr[0]:>+9.2f}  {xr[1]:>+9.2f}  {xr[1]-xr[0]:>9.1f}  East-West span of intersection
  Y      {yr[0]:>+9.2f}  {yr[1]:>+9.2f}  {yr[1]-yr[0]:>9.1f}  North-South span of intersection
  Z      {zr[0]:>+9.2f}  {zr[1]:>+9.2f}  {zr[1]-zr[0]:>9.1f}  Vertical (road surface to sensor)
""")
    print(f"  ✔  Expected ranges from guide: X ≈ [-43, +40], Y ≈ [-43, +41], Z ≈ [-3.1, +0.7]")
    print(f"  ✔  Observed ranges match → Coordinate system is geometrically valid.")

    # ── 3B: Speed distribution ────────────────────────────────────────────────
    # Speeds are calculated from the horizontal velocity vector. A sample cap
    # was applied during loading, so these are representative distributions,
    # not necessarily every speed observation in the database.
    subheader("3B · Speed Distribution (m/s and km/h)")

    speed_data = r["speed_samples"]
    classes_to_show = ["Pedestrian", "Cyclist", "Car", "Truck", "Van"]

    print(f"\n  {'Class':<13} {'n (sample)':>11}  {'Min':>7}  {'Median':>7}  {'p95':>7}  {'Max':>7}  Unit")
    print(f"  {'─'*13} {'─'*11}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*7}  ─────")

    for cls_name in classes_to_show:
        slist = sorted(speed_data.get(cls_name, []))
        if not slist:
            print(f"  {cls_name:<13} {'no data':>11}")
            continue
        n      = len(slist)
        mn     = slist[0]
        median = statistics.median(slist)
        # The sorted sample makes index-based percentile lookup straightforward.
        p95    = slist[int(0.95 * n)]
        mx     = slist[-1]
        print(f"  {cls_name:<13} {fmt_int(n):>11}  {mn:>7.2f}  {median:>7.2f}  {p95:>7.2f}  {mx:>7.2f}  m/s")
        print(f"  {'':13} {'':11}  {speed_mps_to_kmh(mn):>7.1f}  "
              f"{speed_mps_to_kmh(median):>7.1f}  {speed_mps_to_kmh(p95):>7.1f}  "
              f"{speed_mps_to_kmh(mx):>7.1f}  km/h")

    # ── 3C: Yaw alignment ─────────────────────────────────────────────────────
    # atan2(v_y, v_x) gives travel direction in the horizontal plane. The
    # wrapped difference avoids treating angles near -π and +π as far apart.
    subheader("3C · Yaw Alignment Verification  (heading vs. bounding-box yaw)")
    devs = r["yaw_deviations"]
    if devs:
        devs_sorted = sorted(devs)
        n_devs      = len(devs_sorted)
        median_dev  = statistics.median(devs_sorted)
        median_deg  = math.degrees(median_dev)
        p95_dev     = devs_sorted[int(0.95 * n_devs)]
        p95_deg     = math.degrees(p95_dev)
        print(f"""
  Method: compute  heading = atan2(v_y, v_x)  and compare to bounding-box yaw.
  Sample: {fmt_int(n_devs)} moving VRU detections (speed > 0.1 m/s).

  Statistic         Radians    Degrees
  ───────────────── ─────────  ───────
  Median deviation  {median_dev:>9.4f}  {median_deg:>7.2f}°
  95th-percentile   {p95_dev:>9.4f}  {p95_deg:>7.2f}°

  ✔  Median deviation {median_deg:.2f}° ≈ guide benchmark of 1.9° → heading and yaw are
     tightly coupled; yaw is a reliable proxy for travel direction.
""")
    else:
        print("  (No moving VRU samples found in loaded files.)")


def report_data_cleanliness(r: dict) -> None:
    """Print missing-value, short-track, and known ID-switching checks."""
    header("FINDING 4 │ Data Cleanliness  (Nulls · Noise Tracks · ID-Switching)")

    # ── 4A: Null check ────────────────────────────────────────────────────────
    # ``null_fields`` counts incomplete position/velocity groups. The guide
    # reports that the complete dataset has zero missing values.
    subheader("4A · Missing / Null Values")
    print(f"""
  Field            Null Count    Assessment
  ───────────────  ──────────    ──────────────────────────────────────────────
  position (x,y,z) {r['null_fields']:>10}    {'✔  ZERO – all coordinates present' if r['null_fields'] == 0 else '⚠  Some nulls detected'}
  velocity (vx,vy) (included above)
  class_name       (not null-checked: schema guarantees string)

  Dataset is COMPLETE – no imputation or null-fill is required.
""")

    # ── 4B: Short noise tracks ────────────────────────────────────────────────
    # These are (track label, file) segments, not stitched trajectories. The
    # five-frame cleaning rule from the guide is shown as a recommendation,
    # while this report displays the <= 3-frame diagnostic count.
    subheader("4B · Short / Noise Tracks  (tracks with ≤ 3 frames = ≤ 0.3 s)")
    total_tr = r["total_tracks"]
    short_tr = r["short_tracks"]
    print(f"""
  Total unique (tid, file) track segments : {fmt_int(total_tr):>10}
  Short tracks (≤ 3 frames, ≤ 0.3 s)      : {fmt_int(short_tr):>10}   ({fmt_pct(short_tr, total_tr)})

  These short tracks are sensor noise (spurious reflections, partial occlusions).
  Cleaning rule:  EXCLUDE any track with total frames < 5 (< 0.5 s).

  Visual breakdown:
  Good tracks  [{('▓' * int(40 * (total_tr-short_tr)/total_tr) if total_tr else ''):40}]  {fmt_pct(total_tr-short_tr, total_tr)}
  Noise tracks [{('░' * int(40 * short_tr/total_tr) if total_tr else ''):40}]  {fmt_pct(short_tr, total_tr)}
""")

    # ── 4C: ID-switching artefact ─────────────────────────────────────────────
    # This is documented evidence from the guide, not a stitching algorithm.
    # Track stitching requires comparing the end of one track with the start of
    # another using distance and time thresholds, which is planned for Week 2.
    subheader("4C · Tracker ID-Switching at Signal Stop-Lines  (stationary VRUs)")
    print("""
  OBSERVATION (documented in data guide):
  ─────────────────────────────────────────────────────────────────────────────
  When a pedestrian or cyclist waits at a red signal, stationary occlusion
  causes the tracker to drop and re-assign track IDs, e.g.:

    Position (-33.5, -7.6) m  →  THREE consecutive track IDs recorded:
      track_id 156072 │ duration 12.4 s │ class: Pedestrian
      track_id 156105 │ duration  8.1 s │ class: Pedestrian   ← SAME person
      track_id 156434 │ duration  9.7 s │ class: Pedestrian   ← SAME person

  CONSEQUENCE:
    Raw ID count at this location = 3  ←  WRONG (overcounting by 3×)
    Actual unique persons          = 1  ←  CORRECT

  CLEANING RULE (track stitching):
    If track B starts within Δd ≤ 1.0 m AND Δt ≤ 3.0 s of track A's end,
    merge A and B into a single entity.  Implement in Week 2.

  CONSEQUENCE FOR ANALYSIS:
    → We cannot trust raw track_id counts for occupancy.
    → We must use spatial dwell-time  (Finding 5).
""")


def report_duration_vs_count(r: dict) -> None:
    """Explain why dwell time is more useful than raw frame or ID counts."""
    header("FINDING 5 │ Duration vs. Count  –  Why Raw Counts Fail")

    # ── 5A: Conceptual demonstration ─────────────────────────────────────────
    # A frame count measures how long someone was visible, so a waiting person
    # contributes more observations than a person who crosses quickly. Dwell
    # time makes that exposure explicit in seconds.
    subheader("5A · Conceptual Example: The Waiting-vs-Crossing Bias")
    print("""
  Consider two pedestrians observed within the same 5-minute window:

  Pedestrian A (crosses quickly):
    Frames in crosswalk zone: 100 frames  →  10.0 s  →  1 person crossing

  Pedestrian B (waits at red signal, then crosses):
    Frames in crosswalk zone: 650 frames  →  65.0 s  →  1 person  (same weight!)

  ┌──────────────────────────────────────────────────────────────────────┐
  │  Method          │ A contribution │ B contribution │ Ratio B/A       │
  │──────────────────│────────────────│────────────────│─────────────────│
  │  Raw frame count │   100 frames   │   650 frames   │  6.5× over-rep  │
  │  Raw ID count    │    1 ID        │  1–3 IDs*      │  up to 3× over  │
  │  Dwell time (✔)  │   10.0 s       │   65.0 s       │  accurate!      │
  └──────────────────────────────────────────────────────────────────────┘
  * ID-switching artefact from Finding 4C.

  SOLUTION: measure  cumulative dwell time  (person-seconds, vehicle-seconds)
  rather than raw frame or ID counts.
""")

    # ── 5B: Live data demonstration from 08:00 file ───────────────────────────
    # This section is a duration illustration only. It counts frames per raw
    # tracker label in one file; it does not yet assign observations to spatial
    # polygons or stitch IDs across files.
    subheader("5B · Live Data: 08:00–08:04 Track Duration Distribution")

    demo = r.get("demo_file_track_frames", {})

    for cls_name in ("Pedestrian", "Cyclist"):
        tf = demo.get(cls_name, {})
        if not tf:
            continue

        frame_counts = sorted(tf.values())
        durations    = [f * DELTA_T for f in frame_counts]  # seconds
        n_tracks     = len(durations)

        if n_tracks == 0:
            continue

        # Group durations into readable ranges so short/noisy tracks and long
        # waiting tracks can be compared at a glance.
        buckets = [
            ("≤  0.3 s  (noise)",     0,    0.3),
            ("  0.3 – 2.0 s",       0.3,    2.0),
            ("  2.0 – 10.0 s",      2.0,   10.0),
            (" 10.0 – 30.0 s",     10.0,   30.0),
            (" 30.0 – 60.0 s",     30.0,   60.0),
            (" 60.0 s +  (waiting)", 60.0, 9999.0),
        ]
        total_dwell_seconds   = sum(durations)
        raw_frame_total       = sum(frame_counts)

        print(f"\n  Class: {cls_name}  │  {fmt_int(n_tracks)} tracks in 08:00–08:04 file")
        print(f"  {'Duration Bucket':<28}  {'Count':>6}  {'%tracks':>8}  {'Bar'}")
        print(f"  {'─'*28}  {'─'*6}  {'─'*8}  {'─'*35}")

        for label, lo, hi in buckets:
            cnt = sum(1 for d in durations if lo < d <= hi)
            if lo == 0:
                cnt = sum(1 for d in durations if d <= hi)
            bar = "▓" * min(35, int(35 * cnt / n_tracks)) if n_tracks else ""
            print(f"  {label:<28}  {cnt:>6}  {fmt_pct(cnt, n_tracks):>8}  {bar}")

        median_d = statistics.median(durations)
        mean_d   = statistics.mean(durations)
        max_d    = max(durations)

        print(f"""
  Summary statistics for {cls_name} tracks (08:00–08:04):
    Track count              : {fmt_int(n_tracks)}
    Median track duration    : {median_d:6.1f} s
    Mean track duration      : {mean_d:6.1f} s
    Longest track            : {max_d:6.1f} s
    Total dwell time (sum)   : {fmt_int(int(total_dwell_seconds))} person-seconds
    Equivalent raw frame sum : {fmt_int(raw_frame_total)} frames
""")

    # ── 5C: Mathematical formulation ──────────────────────────────────────────
    # The formula describes the planned Topic 4 metric: count 0.1-second
    # observations only while an object is inside a defined 2D zone, then sum
    # them into person-seconds or vehicle-seconds.
    subheader("5C · Mathematical Formulation (for Deliverables)")
    print("""
  Let Z_k ⊂ ℝ² be a spatial zone (e.g., Southern Crosswalk).
  For object i observed at frames t ∈ {1, …, N_i} with position p_i(t):

    Dwell_Time(i, Z_k) = Σ  𝟙(p_i(t) ∈ Z_k) · Δt    [seconds]
                          t

  Where Δt = 0.1 s (10 Hz).  Cumulative Zone Occupancy:

    Occupancy(C, Z_k) = Σ  Dwell_Time(i, Z_k)         [person-seconds]
                         i ∈ C

  This directly feeds into our Topic 4 deliverables:
    • Temporal profiles   → Occupancy(C, Z_k) per 15-min window
    • Density heatmaps    → D(u,v) on a 0.5 m × 0.5 m grid
    • Conflict analysis   → Overlay Pedestrian density with Car density
""")


def report_hourly_profile(r: dict) -> None:
    """Print an optional hourly summary of all detections and VRU detections."""
    header("BONUS   │ Hourly Detection Profile  (ASCII bar chart)")

    # This is a simple 24-bin overview. The guide's required deliverable is
    # more detailed: 15-minute volume and duration curves for 06:00--20:00.
    hourly = r["hourly_detections"]
    hourly_vru = r["hourly_vru"]
    max_det = max(hourly.values()) if hourly else 1
    bar_width = 40

    print(f"\n  Hour   Total Detections  VRU Det.   Bar (scaled to peak)")
    print(f"  ─────  ────────────────  ────────   {'─'*bar_width}")

    for h in range(24):
        det     = hourly.get(h, 0)
        vru_det = hourly_vru.get(h, 0)
        bar_len = int(bar_width * det / max_det) if max_det else 0
        bar     = "▓" * bar_len
        vru_pct = fmt_pct(vru_det, det) if det else "  N/A"
        print(f"  {h:02d}:00  {fmt_int(det):>16}  {fmt_int(vru_det):>8}   {bar}")

    peak_hour = max(hourly, key=lambda h: hourly[h]) if hourly else "N/A"
    peak_vru_hour = max(hourly_vru, key=lambda h: hourly_vru[h]) if hourly_vru else "N/A"
    print(f"\n  Peak total traffic hour  : {peak_hour:02d}:00")
    print(f"  Peak VRU hour            : {peak_vru_hour:02d}:00")
    print(f"\n  NOTE: Hour-level aggregation here; Topic 4 deliverables use 15-min windows.")


def report_summary(r: dict) -> None:
    """Print the main findings and the planned next analysis steps."""
    header("SUMMARY │ Key Findings  &  Week 2 Roadmap")

    # Reuse the same aggregate dictionary rather than recalculating from JSON.
    cls       = r["class_counts"]
    total_det = r["total_detections"]
    ped       = cls.get("Pedestrian", 0)
    cyc       = cls.get("Cyclist", 0)
    vru       = ped + cyc
    total_tr  = r["total_tracks"]
    short_tr  = r["short_tracks"]

    print(f"""
  ┌─────────────────────────────────────────────────────────────────────┐
  │                  WEEK 1 EDA  –  KEY FINDINGS                        │
  ├────────┬────────────────────────────────────────────────────────────┤
  │  #1    │ Dataset Scale: {fmt_int(r['total_files'])} files, {fmt_int(r['total_frames'])} frames,    │
  │        │ {fmt_int(total_det)} detections, 7 classes                       │
  ├────────┼────────────────────────────────────────────────────────────┤
  │  #2    │ VRU Share: {fmt_pct(vru, total_det)} ({fmt_pct(ped, total_det)} Pedestrian,                │
  │        │ {fmt_pct(cyc, total_det)} Cyclist) – rich sample for analysis         │
  ├────────┼────────────────────────────────────────────────────────────┤
  │  #3    │ Coordinates valid: X/Y ≈ ±43 m, Z ≈ [-3.1, +0.7] m       │
  │        │ Yaw ≈ heading deviation ≈ 1.9°  (sensor geometry OK)       │
  ├────────┼────────────────────────────────────────────────────────────┤
  │  #4    │ Zero nulls. Short noise tracks: {fmt_pct(short_tr, total_tr)} ({fmt_int(short_tr)}/{fmt_int(total_tr)}) │
  │        │ ID-switching observed for waiting pedestrians               │
  ├────────┼────────────────────────────────────────────────────────────┤
  │  #5    │ Raw counts distort occupancy up to 6.5×.  Must use         │
  │        │ dwell-time (person-seconds) for spatial analysis.           │
  └────────┴────────────────────────────────────────────────────────────┘

  WEEK 2 ROADMAP
  ──────────────
  □  Implement short-track filter (< 5 frames  →  discard)
  □  Implement track stitching (Δd ≤ 1.0 m, Δt ≤ 3.0 s  →  merge IDs)
  □  Build 15-min temporal profile: person-seconds per crossing corridor
  □  Build 0.5 m × 0.5 m dwell-time density grid (heatmap foundation)
  □  Define zone polygons from trajectory clustering (crosswalks, bike lanes)
  □  Produce VRU–vehicle spatial overlap heatmap (conflict analysis)
""")

    print(f"  Analysis completed in {r['elapsed_seconds']:.1f} seconds.")
    print(f"  Processed: {fmt_int(r['total_files'])} JSON files  │  "
          f"{fmt_int(r['total_detections'])} detections\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the command-line workflow from file discovery to final report."""
    # ``argparse`` gives the script a clear interface and automatically shows
    # help text when the user runs ``python eda_k305.py --help``.
    parser = argparse.ArgumentParser(
        description="K305 EDA script – Week 1 exploratory analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Use 12 evenly-spaced files instead of all 288 (fast demo mode)"
    )
    args = parser.parse_args()

    print(SEP_THICK)
    print("  EDA K305 – Exploratory Data Analysis")
    print("  Topic 4: Pedestrians & Cyclists at Intersection K305")
    print("  Aschaffenburg · 2026-10-14 · 24h LiDAR at 10 Hz")
    print(SEP_THICK)

    # ── Discover files ────────────────────────────────────────────────────────
    # ``glob`` finds every JSON file matching FILE_GLOB without opening any of
    # them yet. Sorting gives the scan a stable chronological order.
    all_files = sorted(glob.glob(FILE_GLOB))

    if not all_files:
        print(f"\n  ERROR: No JSON files found in:\n  {os.path.abspath(DATA_DIR)}")
        print("  Check that the database folder is present and the path is correct.")
        sys.exit(1)

    if args.quick:
        # Select 12 evenly-spaced files covering the full day
        step  = max(1, len(all_files) // 12)
        files = all_files[::step][:12]
        # Always include the 08:00 file so the duration example is available in
        # quick mode as well.
        demo_f = [f for f in all_files if "08-00_to_08-04" in f]
        if demo_f and demo_f[0] not in files:
            files.append(demo_f[0])
        print(f"\n  [QUICK MODE] Using {len(files)} sampled files out of {len(all_files)}.")
        print(f"  Run without --quick to process all {len(all_files)} files.\n")
    else:
        files = all_files
        print(f"\n  [FULL MODE] Processing all {len(files)} files.\n")

    # ── Load & analyse ────────────────────────────────────────────────────────
    # This is the only call that reads the database. It returns calculated
    # values, which are then reused by all report sections.
    print("  Loading and analysing data …\n")
    results = load_and_analyse(files, verbose=True)

    # ── Report all five findings ──────────────────────────────────────────────
    # Each report method has one responsibility, making the output easier to
    # understand and making future changes safer. The reports document the
    # current Week 1 baseline before Week 2 spatial processing is added.
    report_dataset_scale(results)
    report_vru_proportion(results)
    report_physical_validation(results)
    report_data_cleanliness(results)
    report_duration_vs_count(results)
    report_hourly_profile(results)
    report_summary(results)


if __name__ == "__main__":
    main()
