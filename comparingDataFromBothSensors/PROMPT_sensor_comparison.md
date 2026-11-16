# Task: build a notebook that decides which sensor is more reliable — NewSense or Ouster

## Why this matters

We study pedestrians and cyclists (VRUs) at intersection K305. So far we used
the NewSense object list, but it gives one physical object several track IDs,
and it shows flickering detections. We also have an Ouster LiDAR object list
for part of one morning. The team will continue the project with whichever
sensor gives more reliable VRU trajectories, so this notebook has to produce a
defensible, number-backed recommendation. An honest "mixed evidence" result is
better than a confident wrong one.

The data was investigated before this prompt was written. The section
"Verified facts" is reliable: build on it and do not re-investigate it beyond
the validation checks listed. You do not need to read `AGENT.md`; where it
disagrees with this prompt (it says there is no Ouster object list), this
prompt is right.

## Deliverables

All in `/home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project/comparingDataFromBothSensors/`:

| File | Content |
| :--- | :--- |
| `sensor_compare.py` | All loaders, transforms, matching and metric functions. |
| `sensor_comparison.py` | The notebook source in jupytext percent format (`# %%` cells). Short cells that call `sensor_compare`. |
| `sensor_comparison.ipynb` | Generated from the `.py` file and executed **in sample mode**, with outputs. |
| `output/cache/` | Parquet caches (flattened object lists, matched pairs). |
| `output/<mode>/figures/*.png`, `output/<mode>/tables/*.csv` | Every figure and table shown in the notebook; `<mode>` is `sample` or `full`. |
| `output/<mode>/tables/scorecard.csv` | One row per metric: value for each sensor and which is better. |
| `.gitignore` | Containing `output/cache/` and `.venv/`. |

Do not commit anything and do not modify files outside this directory.

## Run modes: you run the sample, the user runs the full data

The data is large, so **you only ever run the analysis on a small sample**. The
user will run the full analysis themselves afterwards. Never start a full run,
and never parse or cache a source file outside the sample.

The notebook's first code cell sets the mode:

```python
RUN_MODE = os.environ.get("SENSOR_COMPARE_MODE", "sample")   # "sample" or "full"
```

The mode changes only which time ranges and files are loaded, and the output
folder. Every loader, gate, metric and plot is the same code in both modes.

| | `sample` (you run this) | `full` (the user runs this) |
| :--- | :--- | :--- |
| Epoch A | 08:00–08:10 CET = `[1793257200, 1793257800)` | `[ANALYSIS_START, SWITCH_START)` |
| Epoch B | 09:15–09:25 CET = `[1793261700, 1793262300)` | `[SWITCH_END, ANALYSIS_END)` |
| NewSense 29.10 files | `08-00_to_08-04`, `08-05_to_08-09`, `09-15_to_09-19`, `09-20_to_09-24` | `07-20_to_07-24` … `11-20_to_11-24` (49) |
| Ouster files | `..._07-05-00`, `..._07-10-00`, `..._08-20-00`, `..._08-25-00` | all except `..._06-20-00` (47) |
| Night check (section 7) | `02-00_to_02-04` | `02-00_to_02-04` … `02-25_to_02-29` (6) |
| NewSense 28.10 (section 8) | `09-15_to_09-19`, `09-20_to_09-24` | same clock hours as 29.10 (49) |
| Common-region threshold (section 3) | 5 detections per cell | 30 detections per cell |

Because you cannot test full mode by running it, make it safe by construction:

- Keep all mode differences in one small config block; no `if RUN_MODE` inside
  metric code.
- In full mode the notebook builds any missing caches itself and prints one
  progress line per file, so the user has a single thing to run.
- Add a function that lists the files full mode would load and checks that
  they exist (49 + 47 + 6 + 49), without opening them. Call it once and
  confirm the counts.
- The loader must already handle what only full mode meets: the two 10-minute
  Ouster files, the skipped `..._06-20-00` file, the dropped
  `[SWITCH_START, SWITCH_END)` interval, and windows with dropped frames.

Ten minutes per epoch is enough to test the code but not to decide between
the sensors. Label sample results as provisional everywhere they appear.

## Verified facts

### Paths

`ROOT = /home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project`
(directory names contain spaces and a trailing dot; use `pathlib`, and quote in shell).

- NewSense object lists:
  `ROOT/database/Data from date of 28.10, 29.10./newsense/object_list/k305_object_list_<DATE>_aggregation_5min/k305_object_list_<DATE>_<HH-MM>_to_<HH-MM>.json`
  with `<DATE>` = `2026-10-28` or `2026-10-29`. File names are local time (CET = UTC+1).
- Ouster object lists:
  `ROOT/database/new data/drive-download-20261103T131231Z-1-001/Object_list_THA/object_list+occupations.log.2026-10-29_<HH-MM>-00.000.gz`
  (48 files).

### NewSense format

One JSON document per 5 minutes, about 20 MB, 3000 frames at 10 Hz:

```
frames[i].frame_timestamp.seconds / .nanosec      Unix epoch UTC (the key is "seconds")
frames[i].objects[j].track_id                      int
                    .class_name                    Pedestrian, Cyclist, Car, Van, Truck, Motorcycle, Bus
                    .score                         0.20–0.66; hard floor at 0.20
                    .bounding_box.position.{x,y,z} metres
                    .bounding_box.scale.{x,y,z}    length, width, height in metres
                    .bounding_box.yaw              radians
                    .velocity.{x,y}                m/s
```

Earlier project work filters detections with `score < 0.25`.

### Ouster format

Gzipped JSON lines, about 210 MB uncompressed per file. Lines alternate
between two kinds with the same `timestamp` and `frame_count`:

```
{"timestamp": <µs epoch UTC>, "frame_count": n, "objects": [ ... ]}       <- use these
{"timestamp": <µs epoch UTC>, "frame_count": n, "occupations": [ ... ]}   <- skip these
```

Skip an occupations line without parsing it by testing
`'"occupations":' in line[:70]` (occupations lines also contain nested
`"objects"` arrays further in, so do not test for `"objects"`). This halves
the parsing time.

Fields to keep from each object: `id` (track ID), `classification` (`PERSON`,
`BICYCLE`, `VEHICLE`, `LARGE_VEHICLE`, `UNKNOWN`), `classification_confidence`,
`position.{x,y,z}`, `velocity.{x,y}`, `dimensions.{length,width,height}`,
`num_points`.

Known quirks, all of which the loader must handle:

- **File names are the end of the window, in UTC.** `..._08-20-00` holds
  08:15–08:20 UTC, which is 09:15–09:20 CET and pairs with the NewSense file
  `09-15_to_09-19`. Never pair by file name; select by timestamp.
- **Skip the file `..._06-20-00` entirely.** It starts with stale frames from
  the previous evening.
- `..._06-40-00` and `..._07-35-00` each hold 10 minutes. The other files hold 5.
- Coverage is continuous from 06:20:00 to 10:25:00 UTC (07:20–11:25 CET).
- `frame_count` counts emitted frames, not time. Dropped frames show up only as
  timestamp gaps of 0.2 s or more. They are frequent between 06:40 and 07:05
  UTC (one 5-minute window has 2584 frames instead of 3000) and rare afterwards.
- Occasionally two consecutive frames carry the same timestamp. Keep the first,
  drop the second, and count how often this happens.
- A new track usually starts as `UNKNOWN` and gets its class a few frames later.

### Time constants (epoch seconds, UTC)

```
ANALYSIS_START = 1793254800   # 29.10 06:20:00 UTC = 07:20 CET
SWITCH_START   = 1793257980   # 29.10 07:13:00 UTC = 08:13 CET
SWITCH_END     = 1793258100   # 29.10 07:15:00 UTC = 08:15 CET
ANALYSIS_END   = 1793269500   # 29.10 10:25:00 UTC = 11:25 CET
```

- Epoch A = `[ANALYSIS_START, SWITCH_START)`, about 53 minutes.
- Epoch B = `[SWITCH_END, ANALYSIS_END)`, 3 h 10 min. **This is the primary comparison.**
- Drop `[SWITCH_START, SWITCH_END)` from both sensors.
- NewSense files needed for 29.10: `07-20_to_07-24` through `11-20_to_11-24` (49 files).
- The same clock hours on 28.10 are these constants minus 86400.

### The Ouster recalibration and the coordinate transforms

The Ouster system was recalibrated at about 08:13–08:14 CET on 29.10. Ouster
positions before and after are in two different world frames. NewSense uses a
third frame. These 2D rigid transforms were fitted on moving vehicles and
verified on other time windows:

```
x' = cos(θ)·x − sin(θ)·y + tx
y' = sin(θ)·x + cos(θ)·y + ty

NewSense → Ouster frame in epoch B:  θ =  95.8°,  t = (−12.72,  6.10)
NewSense → Ouster frame in epoch A:  θ = 170.8°,  t = (−18.15,  4.67)
```

Use the **epoch-B Ouster frame as the common frame**:

- NewSense (all days): apply the epoch-B transform.
- Ouster epoch B: unchanged.
- Ouster epoch A: apply `NS→B ∘ inverse(NS→A)`. Build it by composing the two
  transforms in code instead of deriving the numbers by hand.
- Rotate velocity vectors with the same rotation (no translation).

Clock: `ouster_ts ≈ newsense_ts + 0.08 s`.

Reference results with these transforms, for NewSense motor vehicles faster
than 4 m/s: 80–90% have an Ouster vehicle within 1.0 m in the time-paired
frame, median distance 0.2–0.4 m. With the other epoch's transform the share
is below 3%.

### Environment

- The existing `ROOT/.venv` is broken (built for Python 3.14; the system Python
  is 3.15.2). Do not use or repair it.
- Create a fresh one: `python3 -m venv .venv` inside
  `comparingDataFromBothSensors/`, then install
  `numpy pandas pyarrow scipy matplotlib ipykernel nbconvert jupytext`.
  Wheels for CPython 3.15 exist on PyPI for these.
- 12 cores, 14 GB RAM.

## Method

### 1. Loading and caching

- Flatten each source file into one Parquet file in `output/cache/`, in the
  sensor's **native** coordinates, and skip files already cached. Apply
  transforms in memory after loading, so a transform change never forces
  re-parsing.
- Common columns: `ts` (float64 epoch seconds, each sensor's own clock), `tid`
  (int64), `cls_raw`, `grp`, `score` (NewSense `score`; Ouster
  `classification_confidence`), `x`, `y`, `vx`, `vy`, `length`, `width`,
  `height`, `npts` (Ouster only).
- Parse Ouster line by line; never read a whole decompressed file into memory.
  A file takes roughly 30 s on one core, so use
  `concurrent.futures.ProcessPoolExecutor(max_workers=6)`. The worker function
  must live in `sensor_compare.py`, not in the notebook, because Python 3.15
  starts workers with forkserver and they cannot see notebook-defined functions.
- The cache build takes a list of source files and is called by the notebook
  for the files of the current mode. For the sample that is 4 Ouster files
  and 7 NewSense files.

### 2. Class groups and filters

| Group | NewSense `class_name` | Ouster `classification` |
| :--- | :--- | :--- |
| `ped` | Pedestrian | PERSON |
| `bike` | Cyclist | BICYCLE |
| `veh` | Car, Van, Truck, Bus, Motorcycle | VEHICLE, LARGE_VEHICLE |
| `unk` | — | UNKNOWN |

- A track's group is its most frequent non-`unk` group. A track that is always
  `unk` has group `unk`.
- Each sensor is analysed in two variants:
  - **filtered** (primary): NewSense detections with `score ≥ 0.25`; Ouster
    tracks whose group is not `unk`.
  - **raw**: everything.
- Report `ped` and `bike` first everywhere. Vehicles are context.

### 3. Common region

The Ouster covers about ±80 m and NewSense about ±40 m, so restrict both to
the area both see. On a 2 m grid in the common frame, a cell belongs to the
region if each sensor has at least 30 detections there with speed ≥ 1 m/s
during epoch B (5 in sample mode, where epoch B is only 10 minutes).
Detection-level metrics use detections inside the region.
Track-level metrics use tracks with at least half of their detections inside.

### 4. Validation gates — run these before any metric

The gates run in both modes, on whatever windows the mode loads, and raise an
error that halts the notebook when they fail. If a gate fails in your sample
run, stop and report what you measured. Do not adjust thresholds or
transforms to make it pass.

1. **Alignment.** For each 5-minute window, compute the share of NewSense `veh`
   detections faster than 4 m/s that have an Ouster `veh` detection within
   1.0 m in the time-paired frame. Expected 0.80–0.90. Fail if the median over
   windows is below 0.70, or any epoch-B window is below 0.50. Plot the share
   per window; this plot also documents the recalibration.
2. **Clock offset.** Repeat the same share for offsets from −0.30 to +0.30 s in
   0.05 s steps on three windows spread over epoch B (in sample mode, on the
   two epoch-B windows). The best offset should
   be between 0 and +0.15 s. Then use +0.08 s. Fail if the best is outside
   that range.
3. **Coverage.** After filtering, each sensor has data in every 5-minute window
   of both epochs.

### 5. Metrics for each sensor on its own

Compute identically for both sensors, per group, per epoch, for both variants.

| Problem | Metric |
| :--- | :--- |
| Stream health | Frames per 5 minutes (3000 expected), share of frame gaps above 0.15 s, duplicate timestamps, longest gap |
| Flickering | Share of tracks shorter than 1.0 s; share of detections that belong to such tracks |
| Gaps inside tracks | Share of tracks with at least one missing frame between first and last detection; mean share of missing frames |
| Class stability | Share of tracks whose detections fall in more than one non-`unk` group; for Ouster also the share of `unk` detections |
| Implausible motion | From frame-to-frame position differences: share of steps implying more than 4 m/s (`ped`), 15 m/s (`bike`), 30 m/s (`veh`); 99th percentile of step speed |
| Jitter | RMS of the second difference of position for tracks with net displacement ≥ 3 m |
| Static long tracks | Tracks of ≥ 10 s that stay within 1 m of their median position: count, and their share of the group's detections |
| ID handovers | A track ends, and within 2.0 s a new track of the same group (or `unk`) starts within 1.5 m of the position extrapolated at constant velocity. Report handovers per 100 tracks. Ignore track ends in the last 2 s of an epoch |

### 6. Metrics across sensors, same time and same place

This is the core of the comparison. Use the filtered variants and epoch B as
primary; repeat for epoch A as a secondary result.

- **Frame pairing.** For each NewSense frame, take the Ouster frame nearest to
  `ts + 0.08`, and accept it only if it is within 0.06 s. Report how many
  frames stay unpaired.
- **Detection matching.** In each paired frame, match detections one-to-one
  with `scipy.optimize.linear_sum_assignment` on centre distance, ignoring
  class, and accept pairs up to 2.0 m. Cache the matched pairs as Parquet.

From the matches:

1. **Confirmation rate.** Per sensor and group, the share of detections matched
   by the other sensor. Split by moving tracks (net displacement ≥ 3 m) and
   static tracks. An unmatched detection is either a false detection by this
   sensor or a miss by the other; the data alone cannot say which, so say so.
2. **Class agreement.** Confusion matrix of groups over matched pairs.
3. **ID fragmentation seen by the other sensor.** This directly measures the
   "several IDs for one object" complaint. For every track of sensor A with at
   least 30 matched detections, take the time-ordered sequence of matched
   B track IDs. `n_ids` is the number of distinct B IDs that each cover at
   least 5 matched frames (minimum 1). Report per group the mean `n_ids`, the
   share of tracks with `n_ids ≥ 2`, and ID changes per minute of matched
   time. Do it in both directions. If Ouster tracks map to several NewSense
   IDs much more often than NewSense tracks map to several Ouster IDs, NewSense
   fragments more, and the reverse.
4. **Unconfirmed tracks.** Tracks with under 10% of detections matched: count,
   duration, group, moving or static, and a map of where they are.
5. **VRU counts per 5 minutes.** A valid traversal is a `ped` or `bike` track
   lasting ≥ 2 s with net displacement ≥ 3 m. Plot both sensors' counts over
   time and against each other. A sensor that fragments tracks counts higher.
6. **Disagreements to check on video.** Write
   `output/<mode>/tables/video_check_candidates.csv` with the 20 longest unconfirmed
   VRU tracks per sensor (CET start and end time, common-frame position,
   group), so a person can check them against the Miovision video later.

### 7. Night check for NewSense ghosts

Static VRU tracks that only NewSense sees could be real people waiting whom
the Ouster misses, or false detections on poles and signs. To help tell them
apart, load the NewSense files for 29.10 `02-00_to_02-04` through
`02-25_to_02-29` (6 files; only the first in sample mode), when almost nobody
is on the street. Find static
long `ped` and `bike` tracks there on the same 2 m grid. Report what share of
the daytime unconfirmed static VRU detections fall in cells that also held a
static VRU track at night. A high share points to fixed-structure ghosts.

### 8. NewSense on 28.10

Ouster has no data on 28.10, so no same-time comparison is possible for that
day. Run the single-sensor metrics of section 5 on NewSense for 28.10,
07:20–11:25 CET (09:15–09:25 CET in sample mode), and show them next to the
29.10 NewSense values for the same clock hours to show whether its behaviour
is the same on both days.

### 9. Scorecard and conclusion

- Build `scorecard.csv` from the computed numbers: metric, group, NewSense
  value, Ouster value, better sensor, and a one-line note.
- The user re-runs the notebook on the full data, so the conclusion must come
  from the numbers of whichever run produced it. Do not hand-write result
  numbers or a verdict into markdown. Instead, a final code cell builds the
  summary text from the scorecard and displays it: the run mode, the VRU
  metrics each sensor wins, the three or four headline numbers (cross-sensor
  ID fragmentation in both directions, share of tracks shorter than 1 s,
  ID handovers per 100 tracks, confirmation rate of moving VRUs), and the
  resulting recommendation.
- Decision rule for that cell: compare the sensors on the `ped` and `bike`
  rows of the filtered variant in epoch B. Recommend a sensor only if it is
  better on a clear majority of those rows, including the fragmentation
  rows; otherwise print that the evidence is mixed and list the split.
- In sample mode the cell must print that the result is provisional and based
  on 10 minutes per epoch.
- A fixed markdown cell lists the limits, which hold in both modes: the full
  comparison covers four hours of one morning; there is no independent ground
  truth, so unmatched detections are ambiguous; the Ouster was being
  reconfigured that morning (recalibration at 08:13, dropped frames before
  08:05); night, rain and the afternoon peak are untested for Ouster.
- If VRU evidence and vehicle evidence point in different directions, VRU
  evidence decides, because the project is about pedestrians and cyclists.

## Notebook layout

1. Purpose, data used, and the key facts a reader needs (markdown).
2. Loading, alignment validation and the common region.
3. Stream health.
4. Single-sensor track quality.
5. Cross-sensor comparison.
6. Night check.
7. VRU counts.
8. NewSense 28.10 versus 29.10.
9. Scorecard and conclusion.

Each section has one or two figures and one table. Use one fixed colour per
sensor in every figure, label axes with units, and put the epoch in the title.
Give each section a two- or three-sentence markdown note on what the metric
measures and how to read the figure (which direction is better, what value
would be worrying). Keep result numbers out of the markdown, because they
change when the user runs the full data.

## How to work

- Build and test on one 5-minute window in epoch B first (NewSense
  `09-15_to_09-19`, Ouster `..._08-20-00`), then run the whole sample. The
  sample is the largest run you do.
- Generate and run the notebook with
  `jupytext --to notebook sensor_comparison.py -o sensor_comparison.ipynb`
  and `jupyter nbconvert --to notebook --execute --inplace sensor_comparison.ipynb`
  (sample mode is the default). Edit the `.py` file, never the `.ipynb` JSON.
- Check results by reading the small CSV files in `output/sample/tables/`. Do
  not read the `.ipynb` file or print raw data rows; print shapes and
  aggregates only. Look at no more than three or four figures to sanity-check
  them.
- Sanity-check the sample numbers for bugs, not for a verdict: shares are
  between 0 and 1, no table is empty or all-NaN, both sensors and both epochs
  appear in every table, and the alignment gate is in the expected range.
- The raw files total about 12 GB uncompressed. Never print or `cat` them.
- Time the sample run (cache build and analysis separately) so you can
  estimate the full run for the user.

## When you finish

Report in a short message:

- whether each validation gate passed on the sample, and with what numbers;
- the sample scorecard's main rows, labelled as provisional;
- the exact command for the user to run the full analysis, for example
  `SENSOR_COMPARE_MODE=full .venv/bin/jupyter nbconvert --to notebook --execute --output sensor_comparison_full.ipynb sensor_comparison.ipynb`,
  with your estimate of its runtime, peak memory and cache size, scaled from
  the sample timing;
- anything that only the full run exercises and you therefore could not test;
- anything you skipped or could not compute.

If a gate failed and you stopped, report the measured values and stop there.
