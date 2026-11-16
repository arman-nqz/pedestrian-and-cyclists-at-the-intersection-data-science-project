# AGENT.md — Ouster vs. NewSense sensor comparison (K305)

Guide for agents building the Python notebooks in this directory. Everything
below was established by sampling a few files on 2026-11-16, not by reading the
full dataset. Items marked **UNVERIFIED** are inferences that a notebook must
check before relying on them.

## 0. Corrections (2026-11-16) — these override the sections below

Checked against the files after this guide was first written. Details and the
full task description are in `PROMPT_sensor_comparison.md`.

1. **An Ouster object list exists.** Sections 2 and 6 say there is none. It is in
   `../database/new data/drive-download-20261103T131231Z-1-001/Object_list_THA/`:
   48 gzipped JSON-lines files from Ouster Gemini (tracked, classified objects
   at 10 Hz), continuous for 29.10 from 07:20 to 11:25 CET. Tier A of section 6
   is therefore possible without the pcaps.
2. **Ouster file names are the end of the window in UTC.** `..._08-20-00` holds
   08:15–08:20 UTC = 09:15–09:20 CET. The file `..._06-20-00` starts with stale
   frames from the previous evening; `..._06-40-00` and `..._07-35-00` hold 10
   minutes each.
3. **The Ouster was recalibrated at about 08:13–08:14 CET on 29.10.** The
   sensor pose in `extrinsic_parameters.json` differs between the 07:34
   snapshot (−18.00, 3.50) and the later ones (−13.81, 5.66), which also
   explains the mismatch noted at the end of section 5.4. Ouster object
   positions before and after are in two different world frames.
4. **NewSense and Ouster use different coordinate frames** (section 7, item 1).
   Fitted 2D transforms, NewSense → Ouster, `x' = cosθ·x − sinθ·y + tx`,
   `y' = sinθ·x + cosθ·y + ty`:
   - after the recalibration: θ = 95.8°, t = (−12.72, 6.10)
   - before the recalibration: θ = 170.8°, t = (−18.15, 4.67)

   With them, 80–90% of moving NewSense vehicles have an Ouster vehicle within
   1 m. Which of the two Ouster frames `event_zones.json` was drawn for is not
   established, and the polygons must not be applied to raw NewSense x/y.
5. **Clock offset** (section 7, item 2): `ouster_ts ≈ newsense_ts + 0.08 s`.
6. **Ouster has no data on 28.10.** Same-time comparison is 29.10 only.
7. **The repo `.venv` is broken** (built for Python 3.14, system Python is
   3.15.2). Create a new one; CPython 3.15 wheels exist for numpy, pandas,
   pyarrow, scipy and matplotlib.

## 1. Goal of this week's work

Decide which sensor system — **NewSense** or **Ouster** — gives cleaner data for
the rest of the project, and justify it with numbers and plots.

- Project: Topic 4, "Pedestrians and Cyclists at the Intersection – When and
  Where?" at intersection **K305** (Dr.-Willi-Reiland-Ring / Würzburger Str.,
  Aschaffenburg). See `topic.pdf` in this directory.
- What the project needs from a sensor: pedestrian and cyclist **trajectories**
  (position, timestamp, class) good enough for 15-minute counts per approach,
  trajectory-density heatmaps, typical routes, and VRU–vehicle overlap areas.
  Judge "cleaner" by these needs: VRU data quality matters more than vehicle
  data quality.
- Known NewSense problems so far (reported by the team): false detections from
  flickering, and one physical object receiving several different track IDs.
- All output of this week's work goes in `comparingDataFromBothSensors/`
  (notebooks here, generated files in `output/`).

## 2. Read this first: the two datasets are not the same kind of data

| | NewSense | Ouster |
| :--- | :--- | :--- |
| What is stored | Finished **object lists** (tracked, classified boxes) | **Raw LiDAR packets** (point clouds) + perception configuration |
| Format | JSON, one file per 5 min | PCAP (UDP capture), one file per ~10 min |
| Days | 28.10 (with a gap) and 29.10 (complete) | **29.10 only** |
| Time covered | ~18.7 h + 24 h | **4 × 10 min = 40 min** |
| Size | 15 GB | 25 GB |
| Track IDs / classes | Yes | **None in the files** |

There is **no Ouster object list on disk**. The pcaps hold only UDP port 9000
(lidar) and 9500 (IMU) traffic from one sensor. A like-for-like comparison of
tracks, IDs, and classes therefore needs an Ouster object list to be produced
first. Options, in order of preference:

1. Ask the supervisors / data provider for the Ouster Gemini object-list export
   for the same windows (the configuration shows Gemini Detect was running and
   publishing an object list at 10 Hz on TCP 3002, so it may have been recorded).
2. Replay the pcaps through Ouster Gemini Detect with the shipped `settings/`
   and record the object list.
3. Build our own pipeline on the point clouds (background subtraction →
   clustering → tracking). This then measures our pipeline as much as the sensor.

Without one of these, the comparison is limited to raw point-cloud evidence
(section 6, tier B). State this limitation in any notebook conclusion.

## 3. Dataset locations

Root (note the spaces and trailing dot — always quote the path):

```
../database/Data from date of 28.10, 29.10./
├── newsense/            15 GB   object lists + counting zones + environment + visibility
├── ouster/              25 GB   4 raw pcaps + settings (29.10 only)
├── mio vision/         4.7 GB   Miovision Scout video, usable as ground truth
└── traffic signal data/ 14 MB   signal controller logs, 1 xlsx per day
```

`../DATABASE_AND_PROJECT_GUIDE.md` has more detail on the non-sensor data.
`../near_miss_analysis.py` already contains a working NewSense loader and
event-zone polygon logic that can be reused.

## 4. NewSense dataset

### 4.1 Layout and coverage

```
newsense/<topic>/k305_<topic>_<YYYY-MM-DD>_aggregation_5min/
    k305_<topic>_<YYYY-MM-DD>_<HH-MM>_to_<HH-MM>.json
```

| Topic | 28.10 | 29.10 | Typical file size |
| :--- | :--- | :--- | :--- |
| `object_list` | 224 files, **13:10–19:40 missing** (64 windows) | 288 files (full day) | 5–20 MB |
| `counting_zones` | 224 files | 288 files | 11–15 MB |
| `visibility` | 234 files, 13:10–19:40 missing (54 windows) | 288 files | ~52 KB |
| `environment` | 124 files, starts 13:40 | 288 files | ~3 KB |

File names use local time (CET, UTC+01:00 on both days).

### 4.2 `object_list` schema

```json
{
  "intersection_id": "k305",
  "topic": "object_list",
  "aggregation_minutes": 5,
  "aggregation_start_local": "2026-10-29T08:05:00+01:00",
  "frames": [
    {
      "frame_timestamp": {"seconds": 1793257500, "nanosec": 9575224},
      "timestamp_local": "2026-10-29T08:05:00.009575+01:00",
      "objects": [
        {
          "track_id": 12956,
          "class_name": "Cyclist",
          "score": 0.2968,
          "bounding_box": {
            "position": {"x": -17.23, "y": 20.11, "z": -0.74},
            "yaw": -2.10,
            "scale": {"x": 1.87, "y": 0.73, "z": 1.76}
          },
          "velocity": {"x": 0.004, "y": -0.027}
        }
      ]
    }
  ]
}
```

- `frame_timestamp.seconds` is Unix epoch UTC. The key is `seconds`, not `sec`.
- 10 Hz, 3000 frames per file. Position and scale in metres, yaw in radians,
  velocity in m/s (2D only).
- Classes: `Pedestrian`, `Cyclist`, `Car`, `Van`, `Truck`, `Motorcycle`, `Bus`.
- `track_id` is an integer; the sampled file had IDs from 706 to 117949.

### 4.3 What one sampled file looked like

File: 29.10, 08:05–08:09 (one file only — do not generalise without checking).

- Frame spacing 0.098–0.102 s, no dropped frames.
- 16.9 objects per frame, 331 tracks, median track length 61 frames (6.1 s).
- Score range 0.20–0.66, median 0.33. There appears to be a hard floor at 0.20.
- No track changed class and no track had missing frames inside its lifetime.
- Position extent: x −40 to 35 m, y −43 to 30 m, z −1.8 to 0.3 m.
- **Static tracks dominate the VRU detections.** Counting tracks that last
  ≥10 s with <1 m net displacement:

  | Class | Tracks | Detections | Static tracks | Detections in static tracks |
  | :--- | ---: | ---: | ---: | ---: |
  | Pedestrian | 118 | 28,932 | 37 | 22,737 (79%) |
  | Cyclist | 32 | 3,328 | 10 | 2,572 (77%) |
  | Car | 142 | 15,657 | 4 | 774 (5%) |

  These may be people waiting at signals or false positives on poles, signs,
  and parked bikes. Telling the two apart is a key part of the comparison.
- Only ~1.5% of sampled VRU positions fell inside the three crosswalk polygons
  from the Ouster `event_zones.json`, while 29% fell inside the inner
  `Intersection` box. Either static false positives are skewing this or the
  NewSense frame is not the Ouster `world` frame (see section 7).

### 4.4 Other NewSense topics

- `counting_zones`: same wrapper and 10 Hz frames. Each frame has `zones` (23
  entries) with `zone_id`, `zone_name`, `zone_type`, `class_counts`
  (`{"Car": [dir1, dir2], ...}`), `total_counts`, `event_counts`,
  `instance_count`. Counts looked cumulative within the day (**UNVERIFIED**).
  Zone geometry is not in the files.
- `environment`: one record per minute from an ECoB station — `pm` (pm1, pm2_5,
  pm10), `gas` (co2, so2, no2, o3, co), `weather` (t °C, p hPa, rh %).
- `visibility`: 1 Hz, `visibility_value` in metres (2000.0 in the sample, which
  may be the sensor's maximum).

## 5. Ouster dataset

### 5.1 Layout

```
ouster/
├── 10_29_7_34_29/
│   ├── 29_10_2026_07_34_29_raw.pcap                 6.0 GB
│   └── 10_29__7_34_29_configuration/{<sn>.json, settings/}
└── ouster/
    ├── 10_29__8_18_19/   {.pcap 6.1 GB, _configuration.tar, <sn>.json, settings/}
    ├── 10_29__9_04_14/   (same)
    ├── 10_29__10_24_43/  (same)
    └── 10_29__9_04_14_992519001027.json   (duplicate of the one inside the folder)
```

Each `_configuration.tar` holds the same 17 files already extracted next to it.

### 5.2 Recording windows (all 29.10.2026)

Folder names are local time; pcap packet timestamps are UTC (one hour earlier).

| Folder | Local start | Local end | Duration | NewSense `object_list` files that overlap |
| :--- | :--- | :--- | :--- | :--- |
| `10_29_7_34_29` | 07:34:29 | 07:44:21 | 592 s | 07-30, 07-35, 07-40 |
| `10_29__8_18_19` | 08:18:19 | 08:28:19 | 600 s | 08-15, 08-20, 08-25 |
| `10_29__9_04_14` | 09:04:14 | 09:14:14 | 600 s | 09-00, 09-05, 09-10 |
| `10_29__10_24_43` | 10:24:43 | 10:34:43 | 600 s | 10-20, 10-25, 10-30 |

All four fall inside the Miovision video and signal-log window (06:00–13:00).

### 5.3 PCAP contents

- Classic pcap, little-endian, Ethernet link type, microsecond timestamps.
- One source: `10.125.21.5` → `10.125.21.1`.
  - UDP 9000, 8490-byte frames: lidar packets, 1280 per second.
  - UDP 9500, 494-byte frames: IMU packets, 80 per second.
- Sensor metadata needed to decode is `<folder>_992519001027.json`:
  - OS-1-128, serial `992519001027`, firmware `v3.2.0`.
  - `lidar_mode` 2048x10 → 128 rows × 2048 columns at 10 Hz, 16 columns per packet.
  - `udp_profile_lidar` `RNG15_RFL8_NIR8`: range, reflectivity, near-IR; single return.
  - `timestamp_mode` `TIME_FROM_INTERNAL_OSC`: timestamps inside the lidar
    packets are **not wall-clock time**. Use the pcap capture timestamps to
    align with NewSense.
- Decode with the official `ouster-sdk` (`ouster.sdk.open_source(pcap, meta=[json])`
  → `LidarScan` → `XYZLut`). Check its current docs for the exact API. The repo
  `.venv` is Python 3.15 with only numpy and pandas; `ouster-sdk` may have no
  wheel for 3.15, so a separate environment on an older Python may be needed
  (**UNVERIFIED**).

### 5.4 `settings/` files worth using

| File | Content |
| :--- | :--- |
| `extrinsic_parameters.json` | Sensor → `world` transform. For `992519001027`: position (−13.81, 5.66, 4.55) m, quaternion (w 0.800, x 0.045, y 0.023, z −0.598). Three other serials are listed but have no data here. |
| `event_zones.json` | 14 polygons in `world` x/y: `Intersection`, `CW-NB`, `CW-SB`, `CW-WB`, `OCW-NB`, `OCW-WB`, `Bike-EB`, `VC-EB`, `VC-WB`, `VC-NB`, `Q-EB1`, `Q-EB2`, `Q-SB`, `PET`; height band 0–3 m. |
| `ml_aoi.json` | Detection area: 120 × 120 m centred at (−6.84, −1.03), model rev 2.10. |
| `user_defined_classifications.json` | Ouster output classes: pedestrian, bicycle, car, car with trailer, truck, truck with trailer, bus, tram, Filler. Base classes: PERSON, BICYCLE, VEHICLE, LARGE_VEHICLE, UNKNOWN. |
| `perception_config.json` | Full Gemini perception parameters (315 KB; 10 Hz). Search it, do not load it into context. |
| `lidar_hub_config.json` | Gemini hub 2.9.0.25, site at lat 49.971878, lon 9.158965; object list published on TCP 3002. |
| `logged_alerts.json` | 161 historical alerts (ML init failures, lidar issues) with microsecond epoch times. Check whether any fall on 29.10. |
| `992519001027_background.bin.zz` | Compressed background model (~40 MB, binary). |
| `lidar_hub_config.json<timestamp>` | Old config versions; ignore. |

The corrected sensor position above comes from the file itself; the value in
`../DATABASE_AND_PROJECT_GUIDE.md` (−18.00, 3.50) does not match it.

## 6. Suggested comparison plan

Restrict every comparison to the four overlap windows in 5.2. NewSense-only
analysis of the full days is still useful as a baseline of its problems.

### Tier A — object-level metrics (needs an Ouster object list, see section 2)

Compute each metric identically for both sensors, split by class, with
pedestrians and cyclists reported first.

| Problem | Metric |
| :--- | :--- |
| Flickering | Share of tracks shorter than 0.5 s / 1 s; missing frames inside a track's lifetime; detections per frame variance while the scene is stable |
| ID switches | Track ends that are followed within ~1–2 s and ~1–2 m by a new track of a compatible class; tracks per physical crossing (should be 1) |
| Class stability | Tracks whose class changes; Pedestrian ↔ Cyclist confusion rate |
| Ghosts / static false positives | Long tracks with near-zero displacement; recurring hot spots at fixed x/y across windows and across both days |
| Kinematic plausibility | Speed and acceleration distributions per class (pedestrian ≳ 3 m/s or cyclist ≳ 12 m/s is suspicious); frame-to-frame position jumps; yaw vs. heading-of-motion disagreement |
| Box plausibility | Box dimensions per class and their variance within a track |
| Completeness | Frame rate, dropped frames, coverage area (convex hull / occupancy grid of detections), detection range from the sensor |
| Trajectory usability | Share of VRU tracks that cross a full crosswalk polygon from one side to the other without breaking |
| Count agreement | 5- and 15-min VRU counts per crosswalk from each sensor against each other |

### Tier B — possible with the raw pcaps only

- Point-cloud coverage: points per frame on crosswalks and bike lane, occlusion
  shadows, effective range, from the single sensor's mounting position.
- Overlay NewSense boxes on the Ouster point cloud at matching timestamps:
  boxes with no points inside are false positives; point clusters with no box
  are misses. This also validates the coordinate alignment.
- Sensor health: missing packets or frames, IMU stability, relevant alerts.

### Ground truth for both tiers

- **Miovision video** (`mio vision/miovision/K305/2026_10_29/Standard_SCU{3K2,4YV}_2026-10-29_0600/*.00N.mp4`,
  seven one-hour clips per camera from 06:00). Manually count pedestrians and
  cyclists per crosswalk for a few minutes inside each overlap window. This is
  the only independent arbiter of which sensor is right.
- **Signal logs** (`traffic signal data/K305_2026_10_29.xlsx`, 1 Hz, 06:00–13:00):
  pedestrian crossings should concentrate in pedestrian green phases; detections
  crossing on red in bulk suggest ghosts. Push-button columns give an independent
  hint of pedestrian presence.
- **NewSense `counting_zones`** as a second NewSense-internal count.
- `environment` / `visibility`: note conditions per window so a difference is
  not wrongly attributed to weather.

### Fairness caveats to state in the conclusion

- Ouster evidence is 40 minutes of one morning; NewSense is two days. Night,
  rain, and afternoon peak are untested for Ouster.
- The Ouster data is from one LiDAR; the NewSense sensor setup is not
  documented in the data (**UNVERIFIED** how many sensors it fuses).
- A NewSense score threshold changes its results a lot (earlier project runs
  used 0.25). Report NewSense both raw and filtered, and say which is compared.
- Class sets differ: map NewSense `Van`/`Motorcycle` and Ouster
  `car with trailer`/`tram`/`Filler` to common groups (pedestrian, cyclist,
  motor vehicle) before comparing.

## 7. Things to verify early

1. **Coordinate frames.** It is not established that NewSense x/y and the
   Ouster `world` frame are the same. The sample in 4.3 hints they may not be.
   Check by plotting NewSense VRU tracks over the `event_zones.json` polygons
   and over an Ouster point-cloud top view; if needed, fit a 2D rigid transform.
2. **Clock offset.** Both use UTC-based timestamps but from different clocks.
   Estimate the offset by cross-correlating a clear event (e.g. a vehicle
   platoon entering the `Intersection` zone) before matching objects.
3. **z reference.** NewSense z was −1.8 to 0.3 m; the Ouster ground height in
   `ml_aoi.json` is 0.1 m. Do not compare z without aligning.
4. **Ouster object list availability** (section 2) — this decides whether
   tier A is possible at all and should be raised with the supervisors first.

## 8. Working rules for the data volume

- Never load a whole day or a whole pcap into memory, and never print file
  contents into the agent context. Print shapes, key lists, and aggregates only.
- NewSense: process one 5-min file at a time (≈50k object rows each), flatten to
  a DataFrame with columns `ts, frame_idx, track_id, class_name, score, x, y, z,
  yaw, sx, sy, sz, vx, vy`, and cache as Parquet in `output/`. The 12 files in
  5.2 are enough for the direct comparison. Parquet needs `pyarrow`, which is
  not yet installed.
- Ouster: stream scans; a 10-min pcap is 6,000 scans of 262,144 points. Develop
  on the first 30–60 s, downsample or crop to the 120 × 120 m AOI, and cache
  derived results rather than point clouds.
- Track IDs can continue across 5-min file boundaries; when measuring track
  length or ID switches, concatenate the three adjacent files of a window first.
- Suggested notebooks: `01_newsense_quality.ipynb`, `02_ouster_pcap_inspection.ipynb`,
  `03_alignment_time_and_space.ipynb`, `04_sensor_comparison.ipynb`, each
  writing figures and tables to `output/`.
