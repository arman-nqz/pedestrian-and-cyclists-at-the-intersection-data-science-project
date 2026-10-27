# Running the Near-Miss Analysis

This guide explains how to run `near_miss_analysis.py` and understand its results.

## 1. Open a terminal in this project folder

```bash
cd "/home/arman/Projects/University data science project cameras"
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

This is the recommended first run. It analyses three busy files from **08:00 to 08:14** and creates a new results folder inside `output/`.

The terminal prints the exact output location, for example:

```text
Output: output/sample_08-00_to_08-14_20261026_120000_000000
```

## Useful commands

```bash
# Check that the TTC calculation behaves correctly
.venv/bin/python near_miss_analysis.py --self-test

# Analyse one file only and skip plots
.venv/bin/python near_miss_analysis.py --files k305_object_list_2026-10-14_08-00_to_08-04.json --no-plots

# Save all raw, frame-by-frame interactions as well
.venv/bin/python near_miss_analysis.py --save-all

# Analyse the entire 24-hour dataset (this can take a long time)
.venv/bin/python near_miss_analysis.py --all
```

## Full 24-hour scan

Yes, a full scan is supported. Use:

```bash
.venv/bin/python near_miss_analysis.py --all
```

This processes all **288 five-minute JSON files** for 14 October 2026. It may take substantially longer than the three-file sample and uses more memory because it collects interaction data across the day.

For the fastest full scan, skip SVG chart generation:

```bash
.venv/bin/python near_miss_analysis.py --all --no-plots
```

The full scan creates a separate folder such as `output/full_day_YYYYMMDD_HHMMSS_ffffff/`. It contains the same `run_report.json` and near-miss CSV files as the sample run. Add `--save-all` only if you also need the much larger frame-level interaction CSV files.

## What results to expect

Each run creates a separate folder, so earlier results are not overwritten.

| File | What it means |
| --- | --- |
| `run_report.json` | Main summary: selected input files, processing time, track/class counts, data-quality counters, and TTC/PET statistics. |
| `near_miss_ttc_events.csv` | One row per TTC near-miss event. This is the most important result file. |
| `near_miss_pet_proxy_events.csv` | Events where a vehicle and VRU used the same 2 m grid cell close together in time. This is a PET *proxy*. |
| `plot_*.svg` | Charts for TTC/PET distributions, event locations, hourly counts, and interaction types. |
| `all_*.csv` | Raw frame-level interactions; created only when using `--save-all`. |

## How to read TTC events

Open `near_miss_ttc_events.csv` in Excel, LibreOffice, or a spreadsheet program.

- `min_ttc_sec`: predicted seconds until the two objects would touch if they continued with their current velocities. Smaller means a more serious candidate.
- `duration_sec`: how long the near-miss condition lasted.
- `class_1` and `class_2`: the involved road-user classes.
- `x_mid` and `y_mid`: estimated conflict location in the LiDAR coordinate system.
- `timestamp_local`: time of the most critical point in the event.

The default threshold is **TTC < 1.5 seconds**. By default, the script reports only interactions between a motorized vehicle and a pedestrian or cyclist.

## Important interpretation note

The script finds **potential conflict events**, not proven crashes or traffic-rule violations. Review the lowest-TTC events and the heatmap first. The PET file is a useful screening tool, but it uses 2 m grid cells because the project does not yet have defined crosswalk/conflict-zone polygons.
