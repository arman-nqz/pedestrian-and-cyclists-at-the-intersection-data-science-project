# AGENT.md: NewSense vs Ouster sensor comparison (K305)

Handover guide for an agent (or person) who continues this work in a new chat.
Last updated 2026-11-16. Read this file first. Read `PROMPT_sensor_comparison.md`
only if you need the original task specification in full. The earlier version of
this file (written before the Ouster object list was found) is in git history at
commit `5fb26b9` and is superseded.

## 1. Goal

Decide which sensor, **NewSense** or **Ouster**, gives more reliable pedestrian
and cyclist (VRU) trajectories at intersection K305, with a number-backed and
defensible recommendation. An honest "mixed evidence" result is acceptable.

The project is Topic 4, "Pedestrians and Cyclists at the Intersection – When and
Where?" (see `topic.pdf`). Complaints about NewSense: one physical object gets
several track IDs, and detections flicker. VRU evidence outranks vehicle
evidence.

## 2. Current status

| Step | Status |
| :--- | :--- |
| Code (`sensor_compare.py`, notebook) | Done |
| Sample run (10 min per epoch) | Done, all 3 gates passed, outputs in `output/sample/` |
| Pushed to GitHub `main` | Done (commit `5fb26b9`). `.venv/` and `output/cache/` are git-ignored |
| Full run | Done 2026-11-16 by the user. All gates passed. Outputs are in `output/full/` and `sensor_comparison_full.ipynb`, committed to `main`. Results are in section 7b |
| Independent review of the full results | Prompt ready: `PROMPT_review_full_results.md`. It writes `REVIEW_full_results.md`. Not yet run |
| Video check of disputed tracks | Not started |

Working rules from the user:
- Agents run analyses on a small sample only; the user starts full-data runs.
- Do not commit the near-miss output folders under `../output/` (the
  `k305_*_20261110_*` folders). The near-miss work went badly and must not reach `main`.
- Never commit `../database/` (huge).

## 3. Files in this directory

| File | Purpose |
| :--- | :--- |
| `sensor_compare.py` | All logic: file catalogue, parsing and Parquet cache, transforms, loading, gates, common region, single-sensor metrics, frame pairing and matching, fragmentation, night check, scorecard, decision rule, plotting. All thresholds are named constants at the top. |
| `sensor_comparison.py` | Notebook source (jupytext percent format). **Edit this, never the `.ipynb` JSON.** |
| `sensor_comparison.ipynb` | Generated from the `.py` and executed in sample mode. |
| `output/cache/` | Parquet caches: per source file `<stem>.det.parquet` (detections, native coordinates) and `<stem>.frames.parquet` (every emitted frame, including empty ones, with a duplicate-timestamp count). Also `matches_<mode>_filtered_<epochs>_<paramhash>.parquet`. Git-ignored. |
| `output/<mode>/figures/*.png`, `output/<mode>/tables/*.csv` | Every figure and table. Key tables: `scorecard.csv` and `conclusion.txt`. |
| `.venv/` | Fresh Python 3.15 venv (numpy, pandas, pyarrow, scipy, matplotlib, ipykernel, nbconvert, jupytext). Git-ignored. The repo-root `../.venv` is broken; do not use it. |
| `PROMPT_sensor_comparison.md` | Original task specification (method, metrics, deliverables). |
| `topic.pdf` | Project topic description. |

Regenerate and run the sample:
```
.venv/bin/jupytext --to notebook sensor_comparison.py -o sensor_comparison.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 sensor_comparison.ipynb
```
Run module tests from a script file, not from stdin: `build_cache` uses a
ProcessPoolExecutor (forkserver), which fails when `__main__` is `<stdin>`.

## 4. The full run (the user runs this)

```
cd "/home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project/comparingDataFromBothSensors"
SENSOR_COMPARE_MODE=full .venv/bin/jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --output sensor_comparison_full.ipynb sensor_comparison.ipynb
```

Estimates, scaled from the sample:

| | Estimate |
| :--- | :--- |
| Cache build | 1–2 min for 151 files, one progress line per file in the terminal |
| Total runtime | 5–10 min |
| Peak RAM | 6–8 GB (about 40 MB per loaded 5-min window) |
| Cache size | about 300 MB |

Full mode loads:
- 49 NewSense files for 29.10 (07:20–11:25 CET);
- 47 Ouster files;
- 6 NewSense night files (02:00–02:30 CET);
- 49 NewSense files for 28.10.

`check_full_mode_files()` checks those counts without opening the files, and it
passes.

What only the full run exercises (untested):
- the 10-minute Ouster files `..._06-40-00` and `..._07-35-00`;
- the 3-minute last window of epoch A (08:10–08:13 CET);
- the heavy frame-drop period (06:40–07:05 UTC);
- duplicate timestamps across file boundaries;
- track-ID reuse within an epoch (a tid that reappears after 30 s of silence
  becomes a new track; 0 cases in the sample);
- memory and runtime at full scale.

If a gate fails, do **not** tune thresholds or transforms to make it pass.
Report the measured values. Any other error is likely a bug in the untested paths
above.

After the run:
1. Read `output/full/tables/conclusion.txt`, then `scorecard.csv`.
2. Use `video_check_candidates.csv` to check the longest one-sensor-only VRU
   tracks against the Miovision video (section 8).
3. With the user's approval, commit `output/full/` and `sensor_comparison_full.ipynb` to `main`.

## 5. Verified data facts

Paths, from `ROOT = /home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project`
(directory names contain spaces and a trailing dot; use `pathlib` and quote them):
- NewSense: `ROOT/database/Data from date of 28.10, 29.10./newsense/object_list/k305_object_list_<DATE>_aggregation_5min/k305_object_list_<DATE>_<HH-MM>_to_<HH-MM>.json`.
  File names are CET.
- Ouster: `ROOT/database/new data/drive-download-20261103T131231Z-1-001/Object_list_THA/object_list+occupations.log.2026-10-29_<HH-MM>-00.000.gz`
  (48 files).

**NewSense format:** one JSON file per 5 minutes, 3000 frames at 10 Hz.
- Timestamp: `frames[i].frame_timestamp.seconds/.nanosec` (UTC).
- Objects: `track_id`, `class_name`, `score` (0.20–0.66), `bounding_box.position/scale/yaw` and `velocity.x/y`.
- Observed in the sample: each track has **one constant class and one constant
  score**, and tracks **never have missing frames**. NewSense starts a new ID
  instead of leaving a gap.

**Ouster format:** gzipped JSON lines. Lines alternate between
`{"timestamp": µs, "frame_count", "objects": [...]}` (used) and the same keys
with `"occupations"` (skipped by testing `'"occupations":' in line[:70]`).
- Object fields: `id`, `classification` (PERSON, BICYCLE, VEHICLE,
  LARGE_VEHICLE, UNKNOWN), `classification_confidence`, `position`, `velocity`,
  `dimensions`, `num_points`.
- A file parses in about 2 s (the original prompt expected 30 s).

Ouster quirks (all handled in code):
- **File names are the window END, in UTC.** `..._08-20-00` covers 09:15–09:20
  CET. Always select by timestamp, never by file name.
- **Skip `..._06-20-00`**, which starts with stale frames from the previous evening.
- `..._06-40-00` and `..._07-35-00` hold 10 minutes each; the others hold 5.
  Coverage is continuous from 07:20 to 11:25 CET.
- Dropped frames show only as timestamp gaps of 0.2 s or more. They are frequent
  06:40–07:05 UTC.
- Some consecutive frames have the same timestamp: keep the first and count the
  second.
- New tracks start as UNKNOWN and get their class a few frames later.
- No Ouster data exists for 28.10.

Time constants (epoch seconds, UTC; CET = UTC+1):
```
ANALYSIS_START = 1793254800  # 07:20 CET     SWITCH_START = 1793257980  # 08:13 CET
SWITCH_END     = 1793258100  # 08:15 CET     ANALYSIS_END = 1793269500  # 11:25 CET
```

Epochs:
- **Epoch A** = `[ANALYSIS_START, SWITCH_START)` (secondary).
- **Epoch B** = `[SWITCH_END, ANALYSIS_END)` (primary).
- The 08:13–08:15 CET recalibration interval is dropped from both sensors.
- 28.10 uses the same clock hours (constants − 86400).

Coordinates: the common frame is the **epoch-B Ouster frame**.
- NewSense → common: θ = 95.8°, t = (−12.72, 6.10).
- Ouster epoch A → common: `NS→B ∘ inverse(NS→A)`, where NS→A is θ = 170.8°,
  t = (−18.15, 4.67). This works out to about θ = −75°, t = (−12.53, −12.64), and
  is composed in code.
- Velocities are rotated only (no translation).
- Clock: `ouster_ts ≈ newsense_ts + 0.08 s`.

## 6. Method in brief (see `PROMPT_sensor_comparison.md` for the full specification)

- **Groups:** `ped` (Pedestrian/PERSON), `bike` (Cyclist/BICYCLE), `veh`, `unk`.
  A track's group is its most frequent non-`unk` group.
- **Variants:**
  - *filtered* (primary): NewSense score ≥ 0.25; Ouster tracks whose group is not `unk`.
  - *raw*: everything.
- **Common region:** 2 m cells where each sensor has at least N moving detections
  (≥ 1 m/s) in epoch B. N is 5 in sample mode and 30 in full mode. The region is
  built once and reused for epoch A, the night check and 28.10.
- **Gates** (halt the notebook on failure):
  1. Alignment: median share ≥ 0.70 and every epoch-B window ≥ 0.50.
  2. Clock offset: the best offset must lie in [0, 0.15] s.
  3. Coverage: data in every 5-minute window.
- **Single-sensor metrics** (per sensor, group, epoch and variant): stream
  health, flicker (< 1 s), gaps, class stability, implausible steps, jitter,
  static long tracks, ID handovers.
- **Cross-sensor metrics:**
  - Pairing: each NewSense frame is paired with the Ouster frame nearest to
    `ts + 0.08` (within 0.06 s), **one-to-one** (the nearer NewSense frame wins).
  - Matching: Hungarian assignment on centre distance, at most 2 m.
  - From the matches: confirmation rate (moving and static), class confusion,
    **fragmentation in both directions**, unconfirmed tracks (< 10% matched),
    VRU traversal counts, and the video-check list.
- **Fragmentation attribution:** Ouster tracks mapping to several NewSense IDs
  measure **NewSense** fragmentation, and the reverse. In `scorecard.csv` each
  frag row's value is already the fragmentation *of* that column's sensor.
- **Decision rule** (`decide()`), applied to the filtered, epoch-B, ped and bike,
  scored rows:
  - A sensor is recommended only if it wins at least 2/3 of the comparable rows
    **and** does not lose the fragmentation rows. Reading "including the
    fragmentation rows" as a veto is our interpretation of the prompt.
  - Both conditions must hold **with and without** `gap_track_share`,
    `gap_mean_missing_share` and `class_multi_share`, which NewSense cannot lose
    by design (see section 5).
  - Ties are values within 5% of each other. Rows with fewer than 10 tracks on
    either side are not scored.
  - Otherwise the result is "MIXED EVIDENCE", with the split listed.

## 7. Sample results (PROVISIONAL, 10 min per epoch, not a basis for a decision)

**Gates:**
- Alignment: 0.873 and 0.849 in the two epoch-A windows, 0.875 and 0.861 in the
  two epoch-B windows.
- Clock offset: best +0.05 s, tied with +0.10 s at 10 Hz.
- Coverage: passed.

**Main VRU rows (epoch B, filtered):**

| Metric | Group | NewSense | Ouster |
| :--- | :--- | :--- | :--- |
| Fragmentation, mean distinct IDs per object | ped | 1.97 | 1.44 |
| Share of tracks shorter than 1 s | ped | 0.046 | 0.295 |
| ID handovers per 100 tracks | ped | 14 | 49 |
| Confirmation rate, moving | ped | 0.96 | 0.52 |
| Share of tracks shorter than 1 s | bike | 0.056 | 0.083 |
| ID handovers per 100 tracks | bike | 0 | 18 |
| Confirmation rate, moving | bike | 0.98 | 0.78 |

Bike fragmentation rows have too few tracks to be scored.

**Verdict:** MIXED. NewSense wins 16 of 21 rows (11 of 15 without the
structural rows), but Ouster wins all three fragmentation rows.

**Night check:** no overlap with the 3 night static cells.

## 7b. Full-run results (29.10, 07:20–11:25 CET; epoch B, filtered)

All three gates passed (the notebook halts on a gate failure).

**Verdict generated by the notebook: MIXED EVIDENCE.**
- With all rows, NewSense is better on 15 of 24 comparable VRU rows and Ouster
  on 9, with 0 ties.
- Without the gap and class-stability rows, which NewSense cannot lose, the
  split is 9 to 9.
- Ouster wins all 6 fragmentation rows.
- Vehicle rows (context only): NewSense 7, Ouster 4, ties 1.

| Metric | Group | NewSense | Ouster | n tracks (NS/OU) |
| :--- | :--- | :--- | :--- | :--- |
| Fragmentation, mean distinct IDs per object | ped | 2.27 | 1.27 | 556/749 |
| Share of objects split into ≥ 2 IDs | ped | 0.60 | 0.20 | 556/749 |
| Fragmentation, mean distinct IDs per object | bike | 2.39 | 1.40 | 246/295 |
| Share of objects split into ≥ 2 IDs | bike | 0.67 | 0.30 | 246/295 |
| Share of tracks shorter than 1 s | ped | 0.059 | 0.219 | 2204/1194 |
| Share of tracks shorter than 1 s | bike | 0.065 | 0.074 | 555/364 |
| ID handovers per 100 tracks | ped | 18.8 | 32.0 | 2204/1194 |
| ID handovers per 100 tracks | bike | 6.0 | 5.0 | 555/364 |
| Confirmation rate, moving | ped | 0.92 | 0.61 | 677/1019 |
| Confirmation rate, moving | bike | 0.82 | 0.74 | 386/412 |

Fragmentation rows: the NewSense value is the number of distinct NewSense IDs
per Ouster track, so it measures NewSense fragmentation, and the reverse for the
Ouster value.

**Open questions** (the review prompt asks about these):
- **Merged groups.** Is the NewSense fragmentation real, or does the Ouster merge
  groups of pedestrians into one track? A merged track would inflate the
  NewSense ID count.
- **Duplicate tracks.** Does NewSense fragment through parallel duplicate tracks?
  That would fit its lower handover rate.
- **Unconfirmed Ouster pedestrians.** Why are only about 60% of Ouster moving
  pedestrians confirmed?

## 8. Possible next steps

- Run `PROMPT_review_full_results.md` in a new chat, then read `REVIEW_full_results.md`.
- Check the `video_check_candidates.csv` tracks in the Miovision video:
  `../database/Data from date of 28.10, 29.10./mio vision/miovision/K305/2026_10_29/Standard_SCU{3K2,4YV}_2026-10-29_0600/*.mp4`
  (one-hour clips from 06:00 CET). This is the only independent ground truth.
- Optional: signal logs (`traffic signal data/K305_2026_10_29.xlsx`, 1 Hz). Mass
  VRU crossings on red would suggest ghosts.
- Optional: the Ouster `settings/` (extrinsics, `event_zones.json`) live under
  `../database/Data from date of 28.10, 29.10./ouster/`. It is not established
  which Ouster frame `event_zones.json` uses, so never apply it to raw NewSense x/y.

## 9. Working rules

- Never print or `cat` raw data files (about 12 GB uncompressed). Print shapes
  and aggregates only.
- Check results through the small CSVs in `output/<mode>/tables/`; do not read
  the `.ipynb` JSON.
- Keep all sample/full differences inside `mode_config()`, with no
  `if RUN_MODE` in metric code.
- If you change matching parameters, the matches cache file name changes
  automatically (it includes a parameter hash). After a code fix that changes
  matching but not the parameters, bump the version string in `match_params_hash()`.
- Git: commit only what the user asks for. Leave the near-miss folders under
  `../output/` out of commits.
