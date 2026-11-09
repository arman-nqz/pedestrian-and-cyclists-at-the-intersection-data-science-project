# Running the K305 Near-Miss Analysis

This guide explains how to run `near_miss_analysis.py` against the new K305 multi-modal LiDAR data and review its results.

## Dataset choices

The script supports both new datasets:

| Date | Available chunks | Coverage | Command option |
| --- | ---: | --- | --- |
| 2026-10-29 | 288 | Full day | Default; `--date 2026-10-29` |
| 2026-10-28 | 224 | Available portions of the day | `--date 2026-10-28` |

The October datasets use CET (`+01:00`) timestamps and continuous detection-confidence scores. By default, detections with a score below `0.25` are excluded before the TTC and PET calculations.

## 1. Open a terminal in this project folder

```bash
cd "/home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project"
```

## 2. Create the Python environment (first time only)

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 3. Run a quick sample

```bash
.venv/bin/python near_miss_analysis.py
```

This recommended first run uses the default date, **2026-10-29**, and analyses the three chunks from **08:00 to 08:14**.

To run the same quick sample for October 28:

```bash
.venv/bin/python near_miss_analysis.py --date 2026-10-28
```

## 4. Run a full scan

Run every available chunk for October 29:

```bash
.venv/bin/python near_miss_analysis.py --all
```

Run every available chunk for October 28:

```bash
.venv/bin/python near_miss_analysis.py --date 2026-10-28 --all
```

October 29 has 288 five-minute chunks. October 28 has 224 available chunks, so a full run automatically processes those 224 files rather than expecting 288.

For the fastest full scan, skip SVG plots:

```bash
.venv/bin/python near_miss_analysis.py --all --no-plots
```

Add `--save-all` only when you need the much larger frame-level TTC and PET tables.

## Useful commands

```bash
# Verify TTC mathematics and boundary stitching before a real run
.venv/bin/python near_miss_analysis.py --self-test

# Analyse one particular October 29 file and skip plots
.venv/bin/python near_miss_analysis.py \
  --files k305_object_list_2026-10-29_08-00_to_08-04.json \
  --no-plots

# Use a stricter continuous detection-confidence filter
.venv/bin/python near_miss_analysis.py --all --min-score 0.35

# Change safety thresholds
.venv/bin/python near_miss_analysis.py --all --ttc-threshold 1.0 --pet-threshold 1.0

# Use another compatible JSON directory explicitly
.venv/bin/python near_miss_analysis.py --data-dir /path/to/object_list_directory --all
```

The main command-line options are:

| Option | Meaning |
| --- | --- |
| `--date 2026-10-28` or `--date 2026-10-29` | Select a bundled K305 date. October 29 is the default. |
| `--all` | Analyse every available chunk for the selected date. |
| `--files FILE ...` | Analyse only named files; these can be filenames in the selected date folder or full paths. |
| `--data-dir PATH` | Override the date-based input directory. |
| `--min-score VALUE` | Minimum detection score, from 0 to 1. Default: `0.25`. |
| `--ttc-threshold VALUE` | TTC near-miss threshold in seconds. Default: `1.5`. |
| `--pet-threshold VALUE` | PET-proxy near-miss threshold in seconds. Default: `1.5`. |
| `--no-plots` | Skip SVG charts. |
| `--save-all` | Also export all frame-level interaction tables. |

## Optional: use the interactive notebook

Use `near_miss_analysis.ipynb` when you want to inspect tables and charts inside Jupyter. In its setup cell, select the same choices as the script:

```python
DATASET_DATE = "2026-10-29"  # or "2026-10-28"
RUN_MODE = "quick"           # or "full" or "manual"
MIN_DETECTION_SCORE = 0.25
```

Then use **Restart Kernel and Run All**. The notebook imports `near_miss_analysis.py`, so it uses the same score filtering, boundary stitching, TTC/PET calculations, video mapping, and output naming as the command-line pipeline.

## Finding the output from a run

Every run has its own self-describing folder in `output/`. For example:

```text
output/k305_2026-10-29_full_day_score-0p25_ttc-1p50_pet-1p50_20261109_143012_123456/
```

The folder name contains the dataset date, run scope, minimum score, TTC/PET thresholds, and creation timestamp. It prevents a new run from overwriting an older one and makes different parameter choices easy to compare.

Open `RUN_INFO.txt` inside the folder for a human-readable record of the exact input directory, number of selected files, thresholds, and creation time. The same run identifier is stored in `run_report.json`.

## What results to expect

| File | What it means |
| --- | --- |
| `RUN_INFO.txt` | Plain-language record of the date, mode, input path, file count, thresholds, and creation time. |
| `run_report.json` | Machine-readable summary: run ID, selected files, processing time, track/class counts, data-quality counters, and TTC/PET statistics. |
| `near_miss_ttc_events.csv` | One consolidated TTC near-miss event per row. This is the primary review file. |
| `near_miss_pet_proxy_events.csv` | Vehicle–VRU events that used the same 2 m grid cell close together in time. This is a PET *proxy*. |
| `plot_*.svg` | TTC/PET distributions, conflict locations, hourly counts, and interaction types. Omitted with `--no-plots`. |
| `all_*.csv` | Frame-level interactions; created only with `--save-all`. |

## How to review TTC events with video

Open `near_miss_ttc_events.csv` in Excel, LibreOffice, or another spreadsheet program. Important columns are:

- `min_ttc_sec`: predicted seconds until contact if both road users retained their current velocities. Smaller means a more serious candidate.
- `duration_sec`: how long the near-miss condition lasted.
- `class_1` and `class_2`: road-user classes involved in the event.
- `x_mid` and `y_mid`: estimated conflict location in the LiDAR coordinate system.
- `timestamp_local`: time of the most critical event frame; its embedded timezone offset is retained.
- `video_available`: whether the event falls within the local camera recording window.
- `video_playback_offset`: the `MM:SS` position within the one-hour video file.
- `video_file_scu3k2` and `video_file_scu4yv`: matching files from the two Miovision Scout cameras.

The cameras recorded from **06:00:00 inclusive to 13:00:00 exclusive** local time. For an event at 08:24:15, use video part `003` and seek to `24:15`. Events outside that window remain in the safety analysis but have `video_available = False` and a “No recording” filename message.

The terminal report also lists up to ten video-available TTC events below 1.0 second under **VIDEO VALIDATION TARGETS**.

## Important interpretation note

The script identifies **potential conflict events**, not proven crashes or traffic-rule violations. TTC assumes that participants keep their present velocity and direction. The PET result is a screening proxy based on shared 2 m grid cells, not a map-defined engineering PET measurement.

Review the lowest-TTC, video-available events first. Video is useful for validating whether a candidate reflects a real traffic conflict, but it does not by itself prove fault or rule compliance.
