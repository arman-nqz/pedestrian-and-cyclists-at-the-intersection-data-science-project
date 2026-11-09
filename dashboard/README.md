# K305 VRU dashboard

An interactive Streamlit dashboard for Topic 4, **"Pedestrians and cyclists at the intersection K305: when and where?"**
It shows when and where pedestrians, cyclists and motorcycles (vulnerable road users, VRUs) use the junction of
Dr.-Willi-Reiland-Ring and Würzburger Straße in Aschaffenburg, and where they meet motor traffic. Every number can be
checked against the recording: replay the tracks on the map with both camera videos running alongside.

Data: **29 October 2026** (CET, UTC+1). NSE LiDAR object list for the whole day, plus Ouster BlueCity LiDAR
(about 07:12 to 08:35), the VRS5000 traffic signal log and two Miovision cameras (06:00 to 13:00).

## Run it

```bash
pip install -r requirements.txt
streamlit run dashboard/Overview.py
```

Then open http://localhost:8501. Tested with Python 3.13 and Streamlit 1.67. The dashboard reads prebuilt files from
`dashboard/data/` (not in git, see [Build the data](#build-the-data)); a page whose files are missing says which
command to run.

After pulling code changes, restart Streamlit: it reloads pages on save, but not the modules in `dashboard/lib/`.

## Pages

| Page | What it answers |
|---|---|
| **Overview** | Track counts per class, the key findings (`content/findings.md`) and the limits of the data |
| **Time** | When: counts per 15 minutes or per hour, per class and entry arm, and the peak windows |
| **Space** | Where: time spent or tracks passing per cell, on the OpenStreetMap layout with street names, crossings X1 to X5 and arms N/E/S/W; classes side by side or as a difference; use of each crossing |
| **NSE vs Ouster** | How far to trust the sensors: the two LiDAR systems compared in four shared 10-minute windows (W1 07:20, W2 07:40, W3 08:00, W4 08:20): detection overlap, class agreement, position error, counts, track fragmentation |
| **Conflicts** | Where VRUs meet motor traffic: near-miss candidates (TTC and PET) by class pair, map, hour, sortable event list; select an event to replay it. Compare the original pipeline's events with events recomputed on cleaned tracks. Overlap map: cells where a VRU and a vehicle pass within a few seconds of each other |
| **Signals** | Which signal group serves which crossing (inferred), share of crossings started on red, signal timeline with crossing entries |
| **Replay** | The tracked objects on the map (play, pause, frame step, speed, trails, ids). Both camera videos follow the player's clock. Events from Conflicts are highlighted (red rings, dashed line between the two tracks) |
| **Video** | Both cameras at any second between 06:00 and 13:00, with the signal states and near-miss events nearby |
| **Data quality** | What cleaning does: duplicates, broken tracks, stitching joins and where they happen, low-score detections, a sensitivity table for the movement filter |

### Sidebar

- **Cleaning variant** (default `clean`), used by all pages:
  - `segmented`: raw tracks, split where the sensor lost the object for more than 1 s
  - `stitched`: pieces of the same object joined again (gated mutual-best matching)
  - `clean`: stitched, minus tracks shorter than 3 frames or moving less than 2 m. This drops people who wait, so counts of pedestrians are lower; compare with `stitched` before quoting a number.
- **Classes** and **time of day** (15-minute steps).

The filters are kept in the URL, so a link opens the same view. On Video, `?t=07:21:30` opens that second.

## Build the data

All commands run from the repository root. The raw data goes in `database/` (not in git):

```
database/newsense/object_list/     NSE object list, 5-minute JSON files
database/ouster/                   Ouster BlueCity logs (.gz JSON lines, named by UTC rotation time)
database/traffic_signal_data/      K305_2026_10_29.xlsx (VRS5000 log)
database/miovision/K305/           camera videos, 7 one-hour MP4 parts per camera from 06:00
```

1. **Main tables** (about 5 minutes, the first run parses the JSON and caches it):
   ```bash
   python build_dashboard_data.py
   ```
   Steps (choose with `--steps`): `tracks counts density overlap events signals quality replay meta`.
   Useful options: `--min-score 0.25` (NSE score threshold, default), `--date 2026-10-29`,
   `--replay-variants clean stitched`, `--start 07:20 --minutes 30` for a quick partial build.
2. **Events on our own tracks** (optional, about an hour per variant):
   ```bash
   python build_dashboard_data.py --steps events --compute-events clean stitched
   ```
3. **Crossings and arms** (only after the map or the sensor frame changes): `python zones.py`, then rebuild step 1 so
   tracks get their arm and crossing.
4. **Signal mapping**: `python signal_mapping.py`.
5. **NSE vs Ouster**: `python build_comparison_data.py`.
6. **Map** (only if the sensor frame moves): `python map_alignment.py --osm dashboard/config/k305_map.osm --data-dir database/newsense/object_list`.
   To refresh just the background layers (buildings, green areas, railway, lane counts):
   `python map_alignment.py --layers-only dashboard/config/k305_map.osm dashboard/config/k305_map.json`.

Tests: `python -m unittest discover -s tests` (includes a smoke test that runs every page).

## Folder layout

```
dashboard/
  Overview.py            entry page
  pages/                 one file per page (number = order in the menu)
  lib/
    data.py              cached loaders, class colours, variants
    filters.py           sidebar and URL state
    plots.py             OSM-style base map (roads by type and lanes, buildings, street names, zones)
    replay.py            merges 5-minute replay chunks and builds the player
    video.py             which video file and offset show a given local time
  assets/player.html     the replay player (canvas + video sync)
  content/findings.md    text on the Overview page
  config/                map, zones, signal mapping, NSE-Ouster transforms (in git)
  data/                  built tables, replay chunks (not in git)
```

Coordinates are NSE sensor meters (about ±46 m around the junction). Times are stored as epoch seconds (UTC) and shown
in local time.

## Limits

- **Near misses are candidates**, found by an algorithm with TTC and PET thresholds of 1.5 s. Counts are not divided by
  traffic volume. About 16% of TTC events have a TTC near 0 and last one frame, which points to tracking glitches;
  check events in the replay before quoting them.
- **Signal mapping is inferred** from when people step onto each crossing; no official signal plan is in the data.
  Check it against the junction plan.
- **Cyclists are the least certain class**: NSE and Ouster agree on the class of only 44 to 63% of cyclists.
- **Tracks break**: the object list has about 64,000 track pieces for the day; stitching joins 19%. 36% of detections
  score below 0.25 and are left out.
- **Video sync** assumes each video file starts on the full hour. The Replay page has an offset knob if the picture
  runs ahead or behind.
- The 14 October data is not used (much noisier tracking).

More detail: [docs/DASHBOARD_SPEC.md](../docs/DASHBOARD_SPEC.md) (design), [docs/ANALYSIS_WINDOWS.md](../docs/ANALYSIS_WINDOWS.md)
(shared windows), [docs/NSE_VS_OUSTER.md](../docs/NSE_VS_OUSTER.md) (sensor comparison),
[STITCHING_COMPARISON.md](../STITCHING_COMPARISON.md) (track cleaning).
