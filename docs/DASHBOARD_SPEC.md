# K305 VRU Dashboard: Specification

Status: draft, decisions of 2026-11-09 included. Branch: `stitching-comparison`. Last updated: 2026-11-09.

## 0. Decisions (2026-11-09)

| # | Question | Decision |
|---|---|---|
| 1 | Stack | **Streamlit** (Python). Sections 4.6 and 6 are rewritten for it. |
| 2 | Default cleaning variant | **`clean`**, with a dropdown in the sidebar to switch to `stitched` or `segmented` |
| 3 | Events | Default is the **original pipeline** (`published`) events. Events recomputed on stitched tracks stay available as a comparison |
| 4 | Map | OSM extract `dashboard/config/k305_map.osm` is aligned to the sensor frame (rotation 276 deg, no mirror); result in `dashboard/config/k305_map.json`. Crossing zones and arms still to be defined from it |
| 5 | Order of work | Map alignment first (done), then the data pipeline (M0/M1) |

## 1. Purpose

One interactive tool that answers the Topic 4 question, **when and where do pedestrians, cyclists and other VRUs use intersection K305, and where do they meet motor traffic**, and lets the viewer **check every number against the recording** by replaying it.

The course allows a dashboard as the final deliverable, so it must stand on its own: a viewer who has not read our code or reports should understand the findings and their limits.

### Users
- **Professor / assessors:** want the answers, the method in one place, and honest limits.
- **Team members:** want to inspect tracks and events, compare cleaning settings, find errors.

### Goals
1. Show the four Topic 4 outputs: time profiles, density maps, typical routes, VRU–vehicle overlap.
2. Show near-miss candidate events (TTC, PET proxy) and jump from any event to its replay.
3. Make data quality visible: how cleaning and stitching change the numbers.
4. Run locally from a clean checkout, no cloud service needed.

### Non-goals (for now)
- Live or streaming data. Only the recorded day 2026-10-14.
- Predicting collisions, or any claim that an event is a crash. Events are candidates.
- Editing data or labeling events (may come later, see section 11).

## 2. Data and facts the design depends on

| Fact | Value | Consequence |
|---|---|---|
| Source | 288 JSON files, 5 min each, 10 Hz, 3.9 GB | Too large to load in a browser; precompute |
| Rows (detections) | 11,493,486 | Aggregate for charts; chunk for replay |
| Classes | Car, Van, Truck, Bus, Pedestrian, Cyclist, Motorcycle | No scooter class; scooters probably sit in Cyclist or Pedestrian |
| VRUs (professor) | Pedestrian, Cyclist, Motorcycle | Filter default: these three |
| Coordinates | sensor-local meters, about x −45..42, y −45..45 | Not aligned to a map yet |
| Track ids | continue across file borders, but are **reused** for different objects minutes apart | Always split tracks at time gaps; never trust `track_id` alone |
| Tracks | 232,417 segments per day; stitching joins about 29% of them; 7.9–8.8 M rows after cleaning | Use stitched ids (`trk_s`) |
| Time | local time is UTC+2 on 2026-10-14 | Show local clock |
| Replay size | about 1.5 MB per busy 5-min chunk as JSON | Full day about 300 MB raw; needs chunking and compression |
| Signal data, map, other datasets | exist in the repo's `dataset/` folder, not yet explained | Out of scope until described; design leaves room (section 11) |

**Cleaning variants** (from `STITCHING_COMPARISON.md`) the dashboard must offer, because counts depend on them:

| Variant | Meaning |
|---|---|
| `segmented` | tracks split at gaps > 1 s, not stitched (control) |
| `stitched` | segmented + stitching (default) |
| `clean` | stitched + drop tracks < 3 frames or < 2 m of movement |

The published pipeline's events (`published`) can be shown for comparison.

## 3. Information architecture

A Streamlit app with a sidebar filter panel and one page per view:

1. **Overview:** headline numbers, key findings, limits.
2. **Time:** when VRUs appear.
3. **Space:** where VRUs go.
4. **Routes:** typical paths.
5. **Conflicts:** VRU–vehicle overlap and near-miss events.
6. **Replay:** the recording, with playback controls.
7. **Data quality:** what the cleaning did.
8. **Method:** definitions, parameters, references (static text).

### Global filters (apply to views 2–7 unless stated)
- **Time range:** slider with 15-min steps, default whole day.
- **Class:** Pedestrian, Cyclist, Motorcycle, motor vehicles (Car, Van, Truck, Bus). Default: all three VRU classes on, motor vehicles on in Space/Conflicts/Replay only.
- **Cleaning variant:** dropdown with `segmented` / `stitched` / `clean`. Default `clean`. A visible label always names the active variant. Because `clean` drops 83% of pedestrian tracks (it may remove people who wait), the Overview shows a one-line warning next to it and links to Data quality.
- The selected time range and filters are kept when switching tabs, and stored in the URL so a view can be shared.

## 4. View requirements

### 4.1 Overview
- Counts per class for the active variant: tracks, share of VRUs. Peak hour per class.
- 3 to 5 key findings, written as sentences, each with a link to the view that shows it. (Text is authored by the team, not generated.)
- A permanent **limits box**: one day only; candidate events, not collisions; no scooter class; map not aligned (until section 5.4 is done); no signal data (until added).

### 4.2 Time
- **Counts per 15 min**, 00:00 to 24:00, lines for Pedestrian and Cyclist (and Motorcycle on toggle). Metric: tracks that **start** in the interval, counted once per stitched track. Unit and definition shown on the chart.
- Peak window per class, marked on the chart and listed in a small table (start, count).
- Optional split by arm (N/E/S/W) once zones exist (section 5.4). Until then the control is disabled with a note.
- Day/night shading from sunrise and sunset times (static constants).
- Hover shows the exact count and the share of all VRUs in that interval.

### 4.3 Space
- **Density map:** 2D histogram of positions, 0.5 m cells (selectable 0.5 / 1 / 2 m), log or linear color scale, for the chosen classes and time range. Each position is weighted by time, so the unit is **seconds of presence per m²** (dwell time), not raw frame counts, to avoid over-weighting people who wait. A toggle shows raw detections for comparison.
- Side-by-side mode: two classes (for example Pedestrian vs Cyclist) with the same color scale.
- Optional difference mode (A minus B, normalized).
- Zoom and pan; cursor shows coordinates (m) and value.
- Background layer: none by default; the Google Maps image only after alignment (5.4).

### 4.4 Routes
- Typical paths per class: cluster stitched tracks by entry zone to exit zone, show one representative path per cluster, line width = number of tracks, click for the list of tracks.
- Table: top routes, count, median duration, median speed.
- Needs zones (5.4). Until then show a placeholder: the density map with a note.

### 4.5 Conflicts
- **Event list** (table): time (local), class pair, minimum TTC (s), duration, position, source variant. Sortable, filterable by class pair, TTC range and time range.
- **Event map:** event positions on the same map as 4.3, point size or color = severity (min TTC).
- **Hour histogram** of events.
- **Overlap map:** zones where VRU and vehicle tracks are in the same place within a few seconds (PET-style). Parameters: cell size, time window; defaults documented in Method.
- Each event has a **Replay** button that opens view 4.6 at the event time (start − 5 s), pauses, highlights the two tracks, and draws the line between them.
- A **disclaimer** banner on the tab: events are algorithm-generated candidates, counts are not normalized by exposure, thresholds listed.
- **Event source** dropdown: `published` (original pipeline, **default**) or recomputed on the active variant's tracks. The comparison switch shows both, matched by time and position, so users see what stitching and cleaning changed. Replay of a `published` event uses the original track ids; because those ids are not the stitched ids, the replay highlights the two objects by time and position when the active variant differs.

### 4.6 Replay (extends the existing `k305_player.html`)
Must keep everything the current player does, and add:

| Requirement | Detail |
|---|---|
| Playback | play/pause, speed 0.25x to 8x, frame step, loop, keyboard shortcuts (Space, arrows) |
| Time control | a **window picker** (start time + length 5 / 10 / 15 min) plus a clock input and "jump to" from other views; the slider in the player moves inside the window. Streamlit reruns the script on every widget change, so playback runs in the browser and the window is changed from Streamlit widgets |
| Data loading | the selected window is read from prebuilt files (cached with `st.cache_data`) and embedded in the player; a "Next window" button continues without a gap in time |
| Layers | class filters, dim motor vehicles, trails (length 0–10 s), track ids (stitched id shown as `uid.seg`), velocity arrows |
| Selection | click a track: highlight it, show class, id, start and end time, duration, path length, mean speed, whether it was stitched (and from which pieces) |
| Event mode | when opened from an event: highlight the pair, show distance and TTC over time as a small chart under the canvas |
| Variant | choose cleaning variant; stitched joins can be shown (dashed line across the gap) |
| Bookmarks | "Mark this moment": copy link with time, filters and selection |
| Overlays | optional density map under the tracks; optional zone outlines |

### 4.7 Data quality
- Table and bar chart: tracks per class at each stage (raw segments, after stitching, after filter), as in `STITCHING_COMPARISON.md`.
- Sensitivity table: tracks and VRU counts for different minimum frames and minimum movement.
- Stitching summary: joins made, gap histogram, map of where joins happen, result of the synthetic cut test (recall, wrong joins).
- Known issues list (track id reuse, class flips, no scooter class).

### 4.8 Method
Static page: definitions of every metric, all parameters with their defaults and their source (paper or team choice, marked), references with their verification level.

## 5. Data pipeline

The browser reads **prebuilt files**; it never parses the raw JSON.

### 5.1 Build script
`build_dashboard_data.py` (new) runs once and writes to `dashboard/data/` (not committed, listed in `.gitignore`; regenerate with one command):

```
python build_dashboard_data.py --data-dir <folder with 288 json> --out dashboard/data
```

Steps: parse → segment → stitch (`track_stitching.py`) → filter variants → derive features → aggregate → events → write files. Must be restartable (cache the parsed table as Parquet) and print progress.

### 5.2 Output files and contracts

| File | Content | Used by |
|---|---|---|
| `meta.json` | day, utc offset, bounds, classes, variants, parameters, build time, git commit | all |
| `tracks_<variant>.parquet` (or `.csv.gz`) | one row per track: `trk`, class, t_start, t_end, frames, length_m, mean_speed, x_start, y_start, x_end, y_end, zone_in, zone_out, stitched_from | tables, selection |
| `counts_15min_<variant>.json` | per class, per 15-min bin, per arm: tracks started, tracks present | Time |
| `density_<variant>_<class>_<hour>.json` | grid of dwell seconds per cell (0.5 m), per hour | Space |
| `routes_<variant>_<class>.json` | clusters: representative polyline, track ids, counts | Routes |
| `events_<variant>.json` | TTC events (min TTC, duration, pair ids, classes, x, y, t) and PET-proxy events | Conflicts |
| `events_published.json` | events from the original pipeline | Conflicts comparison |
| `quality.json` | stage counts, sensitivity table, stitch summary | Data quality |
| `replay/<variant>/<HHMM>.json.gz` | one file per 5-minute chunk: frame times, per-frame `[trk, x, y, yaw]`, track metadata `[class, length, width]` | Replay |

Contracts: every file starts with `{"schema": 1, ...}`; times are epoch seconds (UTC) plus the offset in `meta.json`; coordinates are sensor meters with 2 decimals (replay: 1 decimal).

### 5.3 Event generation
Events for the dashboard are computed by the **existing** functions in `near_miss_analysis.py` (imported, not reimplemented) on the tracks of the chosen variant, so that event track ids match the replay. Thresholds: TTC < 1.5 s, PET proxy < 1.5 s, as in the repo, and shown in the UI.

### 5.4 Prerequisites that are not built yet
| Item | Needed for | Owner / status |
|---|---|---|
| `zones.json`: crossing polygons and the N/E/S/W arms | arm split, routes, overlap zones | open; start from the OSM crossings in `k305_map.json` |
| Map alignment of OSM to the sensor frame | background map, zones | **done**: `map_alignment.py`, result `dashboard/config/k305_map.json` (see section 5.5) |
| Repo version of the full cleaning pipeline (parse + filter variants) | build script | partly: `track_stitching.py` exists; parse/filter still in the notebook |
| Signal data | compliance view, phase-based overlap | not yet described by the team |

The dashboard must work without the open items (features degrade as noted in each view).

### 5.5 Map alignment (done)

`map_alignment.py --osm <map.osm> --data-dir <json folder> --out dashboard/config` finds the transform from OSM (latitude / longitude) to the sensor frame, using 36 of the 288 files:

- **Result:** `q = R(-276 deg) @ (east, north) + (-34.5, -12.5) m`, **no mirror**. The OSM origin is the mean of the traffic-signal nodes.
- **How it was found:** rotation search with FFT cross-correlation of the OSM roads against the density of moving vehicles, then a fine local search.
- **Mirror question settled two independent ways:** (a) right-hand traffic: vehicles on the main axis keep right of the opposite flow in the sensor frame (8.4 m gap); (b) on the OSM one-way roads the recorded vehicle direction matches the drawn direction at 86 of 104 points (mirrored alternative: 9 of 102).
- **Pedestrian check:** the mean log density of pedestrians on OSM footways is 0.64, random points 0.44.
- **Accuracy:** not measured beyond the visual check in `alignment_check.png`; treat it as about 2 m. The OSM junction (signals mean) lies at the edge of the sensor window, so the map is trustworthy mainly where tracks exist.

## 6. Technical approach

### Decision: Streamlit

A Streamlit multipage app reading prebuilt files. Python all the way for the team; the replay is the one custom piece.

| Part | Approach |
|---|---|
| App shell | `streamlit` with one page per view (4.1 to 4.8); filters in the sidebar, stored in `st.session_state` and the URL query parameters |
| Charts and maps | Plotly (line, bar, heatmap with `go.Heatmap`, scatter for events and routes); map features from `k305_map.json` drawn as lines |
| Data | prebuilt Parquet / JSON in `dashboard/data/`, read with pandas and cached with `st.cache_data`; nothing parses the raw JSON at run time |
| Replay | our JavaScript player (from `k305_player.html`) embedded with `st.components.v1.html`; the selected window's frames are passed as JSON; controls inside the player; window and variant chosen with Streamlit widgets |
| Events to replay | the Conflicts page sets the replay window and the highlighted pair in `st.session_state`, then switches to the Replay page |

### Known limits of this choice
- Streamlit reruns the script on each widget change. Playback must therefore stay inside the embedded player; Streamlit cannot drive frames.
- The player cannot send clicks back to Python without a custom component. Track selection and the details box therefore live inside the player. If we need clicks to filter other views, a small custom component is needed (extra work, optional).
- Whole-day scrubbing is replaced by a window picker (5 to 15 min). A 15-min window is about 4 MB, so loading is quick.

### Alternatives considered
| Option | For | Against |
|---|---|---|
| Static JavaScript app | smooth replay with day-wide scrubbing, no Python server | the team would write much more JavaScript |
| Jupyter + widgets | fits the notebook | not a standalone deliverable; slow playback |
| Single HTML with embedded data | one file | full day does not fit |

### Layout
```
dashboard/
  app.py                 entry point (Overview page), sidebar filters
  pages/                 1_Time.py, 2_Space.py, 3_Routes.py, 4_Conflicts.py, 5_Replay.py, 6_Data_quality.py, 7_Method.py
  lib/                   data.py (loaders + cache), filters.py, plots.py, replay.py (builds the player HTML)
  assets/player.js       the replay player
  config/                k305_map.json, k305_map.osm, alignment_check.png, zones.json (later)
  data/                  generated, not committed
docs/DASHBOARD_SPEC.md
build_dashboard_data.py
map_alignment.py
```

Run with `streamlit run dashboard/app.py`. Add `streamlit`, `plotly`, `pyarrow` to `requirements.txt`.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Startup | first view visible in under 3 s on a normal laptop with local data |
| Replay | 30 frames/s render with up to 80 objects; no stutter at chunk borders; chunk fetch under 300 ms |
| Memory | under 1 GB in the browser for a full-day session |
| Data size | `dashboard/data/` under 500 MB; if larger, reduce replay to every 2nd frame (5 Hz) as an option and say so in the UI |
| Browsers | current Chrome, Edge, Firefox |
| Accessibility | color-blind-safe palette (class colors also differ in shape: circle for VRU, box for vehicles); keyboard control for replay; text alternatives for charts (data tables) |
| Reproducibility | one command builds all data; `meta.json` records parameters and the git commit |
| Honesty | the active variant, thresholds and limits are always visible; no number without its definition on hover or in Method |
| Language | English UI; German terms only where the course sheet uses them |

## 8. Visual design

- Dark theme for the replay canvas (as in the current player), light theme for charts and tables; follow the system preference where possible.
- Class colors fixed across all views: Pedestrian blue, Cyclist orange, Motorcycle purple, vehicles gray tones.
- One consistent number format (thousands separator, 1 decimal for seconds).
- Empty and loading states for every view; an error message names the missing file and the build command.

## 9. Acceptance criteria

The dashboard is accepted when:
1. `build_dashboard_data.py` runs from a clean checkout and produces all files in section 5.2 (those not blocked by 5.4) without manual steps.
2. Counts in Time and Data quality equal the notebook's numbers for the same variant (checked for at least two variants and three classes).
3. The 15-min pedestrian and cyclist curves match `k305_hourly.png` aggregated to hours (same peaks at 07:00, 13:00, 17:00 for the `clean` variant).
4. Every row in the event list opens a replay at the right time with the two tracks highlighted.
5. Replay plays any 5-minute chunk of the day at 1x without visible stutter, across a chunk border, with controls working as in 4.6.
6. Switching the cleaning variant changes counts, density, events and replay consistently, and the label always shows the active variant.
7. The limits box and disclaimers from sections 4.1 and 4.5 are visible.
8. A teammate who did not build it can run it from the README in under 10 minutes.

## 10. Milestones

| # | Milestone | Content | Depends on |
|---|---|---|---|
| M0 | Pipeline in the repo | parse, segment, stitch, filter variants as a module with tests on 3 sample files; build script skeleton | `track_stitching.py` |
| M1 | Data bundle | all files in 5.2 except zones and routes; quality numbers match the notebook | M0 |
| M2 | App shell + Time + Data quality | Streamlit pages, sidebar filters, URL state, charts | M1 |
| M3 | Space | density map, side-by-side, dwell-time weighting | M1 |
| M4 | Replay | player component with window picker, selection, variants | M1 |
| M5 | Conflicts | events table/map, jump to replay, published comparison | M1, M4 |
| M6 | Zones from the aligned map | `zones.json` from OSM crossings and arms, background map layer, arm split, routes (alignment itself is done) | `k305_map.json`; team review of zones |
| M7 | Polish | Method page, accessibility pass, README, acceptance test | all |

M2 to M4 can run in parallel after M1.

## 11. Questions

### Answered (2026-11-09)
1. Stack: Streamlit.
2. Default variant: `clean`, with a dropdown.
3. Events: original pipeline by default.
5. Map: OSM extract provided and aligned.

### Still open
4. **Replay size:** window length 5 / 10 / 15 min at full 10 Hz, or offer 5 Hz for longer windows?
6. **Other datasets and signal data** (`dataset/` folder): what are they, and should compliance or phase-based views be in scope?
7. **Event review:** do we want a "mark as real / false" feature to validate events? It needs somewhere to store labels (a JSON file in the repo is enough).
8. **Hosting:** local only, or a published copy (for example Streamlit Community Cloud)? A published copy needs the data size cut and the data files committed or hosted.
9. **`clean` default:** the movement filter removes 83% of pedestrian tracks and 42% of the near-miss events in the 07:00 to 09:00 test. Is that what we want as the default once a sample of the removed events has been reviewed?

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Full-day replay data too large or slow | unusable replay | chunking, gzip, 5 Hz option, only the active variant loaded |
| Near-miss events not trusted (constant velocity, circles, grid PET) | weak conflict view | disclaimers, comparison with published events, manual review of a sample |
| Cleaning choices change the story | confusing numbers | variant switch always visible, Data quality tab |
| Zones and map not available in time | Routes and arm split missing | views degrade gracefully; density map is the fallback |
| Two code bases (notebook and repo) drift apart | different numbers | M0 moves the pipeline into the repo; notebook imports it |
| Dashboard scope grows | not finished | milestones M2–M5 are the minimum; M6–M7 are the extras |
