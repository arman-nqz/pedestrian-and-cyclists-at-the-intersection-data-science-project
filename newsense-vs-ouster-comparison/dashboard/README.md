# K305 Traffic Analysis: Newsense vs Ouster (dashboard UI v2)

An interactive research dashboard for exploring how the Newsense and Ouster sensors detected, classified and tracked pedestrians, cyclists and vehicles at intersection K305 on **29 Oct 2026, 07:12–08:35 CET**. That is the only period in which both sensors and the original video exist.

**UI v4 (14 Nov 2026)** simplifies the analytical pages: each opens with its main finding and a few key numbers, and detail sits in expanders. Watch the Sensors, Follow One Person and Key results are unchanged . **UI v3** added a second camera, SCU4YV (see *Two cameras* below). **UI v2** was a beginner-friendly redesign of the interface only: no data, calculation or V2 value changed.

The centrepiece is the **Follow One Person** page. Pick one person and watch the original camera footage. Beside it, the Newsense track and the Ouster track of the same moment are shown on synchronized maps and a shared timeline. Below them is the full evidence behind every cross-sensor match.

* **Source of truth:** the corrected **Final package V2** (the files the dashboard needs are in `inputs/FINAL_PACKAGE_V2/`).
  * At start-up the app checks that V2 is complete: all 13 corrections are present and V2 validation passed. If V2 is incomplete, it stops.
  * It never reads V1.
* **Status:** this is a research tool, not a validated measurement system. V2 itself is not described as fully scientifically validated: its audit was a re-implementation by the same analyst.

## Launch

**Simplest way:** follow [`QUICK_START.md`](QUICK_START.md). Double-click `START_DASHBOARD.command` (macOS) or `START_DASHBOARD.bat` (Windows). The start file creates a private Python environment in `.venv/` on the first run, installs `requirements.txt` and opens the dashboard in the browser.

Manual equivalent (any OS, Python 3.11 or newer):

```bash
cd newsense-vs-ouster-comparison/dashboard
python3 -m venv .venv && source .venv/bin/activate        # Windows: py -3.12 -m venv .venv  then  .venv\Scripts\activate
python -m pip install -r requirements.txt
python run_dashboard.py                                   # --check: only report what is present; --port 8502
```

* **No dataset needed.** The prepared dashboard data (`data/`, 92 MB) and the V2 research inputs (`inputs/`) ship with the dashboard.
* **Camera video:** put the four MP4 files listed in `videos/PUT_VIDEOS_HERE.txt` into `videos/`. They are parts 002 and 003 of both cameras, covering 29 Oct 07:00–09:00, about 710 MB. The recordings are not in Git. Without them, all pages work but the video panels stay empty.
* The app starts a small **read-only video server on 127.0.0.1:8765**. It streams the MP4 files in place: no copies, no transcoding.
* Tested with Python 3.11.13 and 3.12.0. Versions are pinned in `requirements.txt` (Streamlit 1.66.1, pandas 2.3.3, numpy 2.3.3, plotly 7.1.0, pyarrow 26.0.0).
* The first start of a session loads the observation index, which takes about 5 s.

Direct link to an investigation: `http://localhost:8501/follow_one_person?inv=INV-00416` (the old `/object_investigation` path no longer exists).

**Presentation mode** for demonstrating the research: `http://localhost:8501/presentation` (no sidebar, large video, nine steps from the question through five examples to results and limits).

## Pages

| Section | Page | What it answers |
|---|---|---|
| | **Home** | What the project is, the two sensors and the camera, study dates, a coverage chart and notice (Ouster object data: 29 Oct ≈ 07:11–08:35 only), and four large entry points |
| Explore | **Watch the Sensors** | Any 30–180 s moment of the original video with both sensors' detections, on the video and on two maps |
| Explore | **Follow One Person** | Pick one investigation; watch the camera, the Newsense map and the Ouster map in sync; read a plain tracking comparison; open technical details |
| Compare Sensor Performance | **Key results** | The V2 findings as plain questions, each with Newsense and Ouster values and a "Definition, sample and uncertainty" pop-over; full 31-metric scorecard on demand |
| | **Detection & classification** · **Tracking** · **Movement paths** · **Where objects are seen** · **Potential conflicts** | Each starts with what it answers and its main finding; charts have titles, labelled axes and units; detailed tables are in expanders |
| Understand the Research | **How the research works** | Concepts, formulas and a glossary mapping plain dashboard words to the technical terms in the reports |
| | **Data quality & limitations** | Recording gaps, the Ouster coverage notice, the 56-entry issue register, V2 limitations, reliability of each kind of information |
| | **Presentation mode** | Guided sequence for professors: question → method → five examples → results → limits |

Colours: Newsense blue · Ouster green · original camera slate · both/matched purple · uncertain amber · unavailable grey.

## Using Follow One Person

1. **Choose an investigation.** Click one of the five examples, or open *Find an investigation*. Filter with the pills (Pedestrians, Cyclists, Both sensors detected, Newsense only, Ouster only, the match results including Ambiguous, Tracking interruptions, Visible in the camera view), sort, and page through 12 rows at a time. Click a row. *More filters* has time, duration, ID search and the Newsense "motorcycle" option. The filtered list can be downloaded as CSV with technical columns.
2. **Read the header.** "Investigation #00718" is the dashboard reference (`INV-00718`). It organises a *possible* match and is **not** a person's identity. The badge gives the match result in plain words; ambiguous cases stay ambiguous.
3. **Use the player.** The original camera is the main panel, with the Newsense and Ouster maps beside it.
   * Play/Pause (or space), ◀ 1 frame / 1 frame ▶ (or ← →), Previous/Next event, Speed, and the time slider.
   * The timeline has one row per sensor: solid = position reported, hatched = interruption, amber strip = Ouster estimated position, ◇ = classification change, red line = current moment. Hover for details; click to jump.
   * *More display options*: one combined map, the other sensor's track, trails, IDs, other road users, per-sensor video dots, ±0.1 s steps.
   * *Timing uncertainty* (amber bar): explanation of the unexplained 2.81 s offset and the manual visual alignment slider (video only, never saved).
4. **Below the player:** *How did each sensor track it?* (first/last detected, duration, number of IDs, interruptions, …), *What does the match result mean here?*, a plain *Side-by-side comparison*, a glossary, and **Technical details** (identifiers and original candidate ID, all metrics with original names, matching evidence including rejected alternatives, trajectory/speed/distance charts, event log, raw samples with CSV export).

## Two cameras (UI v3)

The dataset contains two MioVision cameras with different viewpoints of the junction. Each recorded 7 h on 28 and 29 Oct.
* **Camera 1 · SCU3K2:** looks across the junction toward a modern white building.
  * Approved V2 timing and ground calibration; sensor positions are drawn on it.
* **Camera 2 · SCU4YV:** looks along the wide road toward brick façades.
  * Its clock was **measured** on 14 Nov 2026: camera clock = sensor time − 79.8 s, ±0.5 s, for 29 Oct 07:12–08:35. This is not part of V2.
  * No ground calibration, so no sensor positions are drawn on it.
  * Evidence: `diagnostics/MULTI_CAMERA_INVESTIGATION.md` in the original project folder (not included here).

**Camera controls** (above the player on Follow One Person and Watch the Sensors):
* **Cameras:** *Both cameras* (side by side, maps below) · *Camera 1 only* · *Camera 2 only*. With *Camera 2 only*, camera 2 drives the maps through the measured relation.
* **Camera 2 timing:**
  * *Linked (measured ±0.5 s)*: one set of controls moves both cameras and the maps.
  * *Independent (not synchronised)*: camera 2 gets its own Play, frame buttons and slider, plus a red NOT SYNCHRONISED note. Equal clock readings then do not mean the same instant.
* **Readout:** for a selected object, it says whether its position is inside camera 1's image (calibrated) and inside camera 2's *approximate* coverage. Occlusion must be judged by eye; people are never matched between the views by appearance.
* **Coverage map:** Watch the Sensors → *Which camera sees which part of the junction?* (approximate, from motion correlation).

## Folder layout

```
dashboard/
  QUICK_START.md            non-technical start guide
  START_DASHBOARD.command   macOS start file (double-click)
  START_DASHBOARD.bat       Windows start file (double-click)
  run_dashboard.py          cross-platform launcher used by both start files (checks, free port, opens the browser)
  requirements.txt          pinned Python packages
  app.py                    navigation, V2 gate, video server start
  views/                    the 12 pages (00_home … 11_presentation) (named views/, not pages/, so Streamlit's legacy auto-navigation stays off)
  components/player.py/.js  synchronized video + maps + timeline component
  utils/                    ui (design system), page helpers, inv_view, results (V2 cards), config, paths (all locations), cached data access, time chain, investigation logic, read-only video server, markdown parser
  data/                     prepared dashboard tables (92 MB parquet/json), generated from the original dataset by build/
  inputs/                   V2 research results and derived analysis files the pages read (29 small files, original relative paths, unchanged)
  config/sources.json       every input file used, with its role
  config/cameras.json       camera registry (SCU4YV parts, measured offset −79.8 s ± 0.5 s, approximate coverage)
  videos/                   put the 4 camera MP4 files here (not in Git)
  build/                    b1–b5 data builders (only needed to regenerate data/ from the dataset: python run_dashboard.py --dataset PATH --rebuild)
```

**What is not included in this folder:** the research report and slide deck, the original dataset (47.9 GB), the camera recordings, Ouster PCAPs, earlier UI versions, screenshots, the test suite and the diagnostic investigations. They remain in the original project folder.
