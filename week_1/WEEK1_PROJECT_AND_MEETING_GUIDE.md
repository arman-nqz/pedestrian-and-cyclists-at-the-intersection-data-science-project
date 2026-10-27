# Topic 4: Pedestrians & Cyclists at the Intersection (When and Where?)
## Complete Week 1 Project Guide, Script Analysis & Presentation Prep
*Intersection K305: Dr.-Willi-Reiland-Ring & Würzburger Str., Aschaffenburg*

---

## 1. Python Libraries Used in the Script

The Week 1 script (`eda_k305.py`) was built exclusively using the **Python Standard Library (Python ≥ 3.8)**. This ensures zero dependency overhead, instant execution on any machine, and efficient streaming across 288 large JSON files without memory crashes.

| Library | Type | Role in `eda_k305.py` |
| :--- | :--- | :--- |
| `json` | Standard Library | Streaming and parsing 5-minute LiDAR object-list JSON files. |
| `glob` | Standard Library | Pattern matching to discover all 288 JSON files in the dataset folder. |
| `os` | Standard Library | Operating system path operations and file location validation (`os.path.join`). |
| `math` | Standard Library | Euclidean speeds ($\sqrt{v_x^2 + v_y^2}$), angle conversions, and $\text{atan2}(v_y, v_x)$ heading angles. |
| `statistics` | Standard Library | Computing median and mean speeds, yaw deviations, and dwell times. |
| `collections` (`defaultdict`) | Standard Library | Fast counting and accumulating detections per class, hourly bins, and unique track IDs. |
| `datetime` | Standard Library | Parsing ISO-8601 timestamps (`timestamp_local`) to group frames by hour and minute. |
| `argparse` | Standard Library | CLI argument parsing: provides `--quick` demo mode (7s) vs full 24h scan mode. |
| `time` & `sys` | Standard Library | Benchmarking runtime, calculating ETAs, and handling clean error exits. |

### 📦 Upcoming Libraries Planned for Week 2 (Implementation Plan):
* **`NumPy` & `Polars` / `Pandas`**: Fast vectorized operations and data grouping across 11.5M records.
* **`Shapely` & `GeoPandas`**: Defining spatial polygon zones (crosswalks, bike tracks) and testing point-in-polygon containment.
* **`Matplotlib` & `Seaborn`**: Generating 2D continuous dwell-time heatmaps and 15-minute volume curves.
* **`Scikit-Learn`**: Clustering trajectories with DBSCAN to extract typical pedestrian crossing paths.

---

## 2. What the Script Does (Step-by-Step)

The script `eda_k305.py` is a dedicated Exploratory Data Analysis (EDA) engine designed to inspect the 24-hour LiDAR dataset:

* **Dataset Discovery**: Automatically locates all 288 JSON files in `database/k305_object_list_2026-10-14_aggregation_5min/`.
* **Dual Mode Execution**:
  * `--quick` mode: Samples 12 evenly-spaced files across the 24 hours to give a full representative summary in **~7 seconds** (ideal for a live presentation).
  * Full mode: Iterates through all 288 files (~3 minutes) streaming file-by-file to keep RAM usage low.
* **Streaming Extraction**: Reads bounding boxes $(x, y, z)$, dimensions, velocities $(v_x, v_y)$, classes, and `track_id`s.
* **Integrity Verification**: Checks for missing or null fields in coordinates and velocities (confirms 100% complete data).
* **Physics & Geometry Validation**: Computes coordinate limits, checks velocity distributions, and tests if heading angles align with bounding-box yaw angles.
* **Noise & Artifact Analysis**: Tracks object lifespan per frame to identify short sensor noise tracks ($\le 3$ frames) and tracker drops.
* **Terminal Visualization**: Generates formatted distribution tables, progress bars, and an hourly ASCII traffic profile.

---

## 3. The 5 Core Analytical Findings

1. **Dataset Scale**:
   * **288 files**, recorded at **10 Hz** (1 frame every 0.1s).
   * Totaling **~864,000 frames** and **~11.5 million object detections** across 7 classified categories.
2. **High VRU (Vulnerable Road User) Proportion**:
   * Pedestrians represent **~17.5% to 20.2%** and Cyclists **~3.1% to 3.3%**.
   * VRUs comprise **over 20% to 23.5%** of all detections, providing rich statistical sample sizes for modeling.
3. **Physical & Coordinate Validation**:
   * Coordinates span $X \approx [-43\text{m}, +40\text{m}]$ and $Y \approx [-43\text{m}, +41\text{m}]$, with vertical elevation $Z \approx [-3.1\text{m}, +0.7\text{m}]$.
   * Speeds are physically realistic (Pedestrian median $\approx 0.6\,\text{m/s}$, Cyclists $\approx 1.4\,\text{m/s}$).
   * Heading direction ($\text{atan2}(v_y, v_x)$) closely matches bounding box yaw within a median difference of only **$1.9^\circ$**.
4. **Data Cleanliness & Identified Artifacts**:
   * **Zero nulls**: All coordinates, velocities, and dimensions are complete.
   * **Sensor Noise**: ~12% to 15% of tracks last $\le 3$ frames ($\le 0.3\,\text{s}$). Filter rule: discard tracks $< 0.5\,\text{s}$.
   * **ID-Switching**: When pedestrians wait stationary at a red light, the tracker sometimes loses them and assigns a new `track_id`. A stitching rule is needed so we don't overcount people.
5. **The Core Analytical Insight — "Duration vs. Count" (Dwell Time)**:
   * **Why raw counting fails**: A person waiting at a red light for 60 seconds generates 600 frames; a person crossing quickly in 10 seconds generates 100 frames. Counting raw frames over-represents waiting people by **6×**.
   * **The Solution**: We must measure **Spatial Dwell Time / Occupancy** in **person-seconds** ($\sum \Delta t$) inside crosswalk zones.

---

## 4. Key Technical Concepts Explained Simply

### A. What is the 10 Hz LiDAR Data Structure?
* **10 Hz** = 10 frames per second. Each frame is recorded every **0.1 seconds (100 ms)**.
* Stored in **5-minute JSON files** containing an array of frames, where each frame lists detected objects.
* It is an **object-level abstraction** (3D bounding boxes and tracks), not raw laser point clouds.

### B. Spatial Dwell Time (Dwell Time)
* Dwell time measures how long an object lingers or stays inside a specific spatial zone (e.g. crosswalk or curb).
* Formula: $\text{Dwell Time} = \text{Frames} \times 0.1\,\text{s}$, yielding **person-seconds** or **vehicle-seconds**.
* **The Waiting Bias**: A pedestrian crossing quickly in 10s produces 100 frames; a pedestrian waiting at a red light for 60s produces 600 frames. Simple counting over-represents waiting people by 6x. Dwell time solves this by measuring cumulative spatial occupancy.

### C. 2D Velocity Vector $(v_x, v_y)$
* A velocity vector gives both **speed magnitude** ($\sqrt{v_x^2 + v_y^2}$) and **direction of movement** ($\text{atan2}(v_y, v_x)$) in meters per second.
* **Why track it**: Distinguishes stationary waiting users (speed near 0) from active crossers, verifies realistic motion physics, and detects potential trajectory collisions with turning motorized traffic.

### D. Track ID (`track_id`)
* A persistent digital badge assigned to an individual entity across consecutive frames.
* **Why track it**: Without `track_id`, frames are just disconnected dots. With `track_id`, we connect the dots to reconstruct the entire journey across the intersection, filter out transient noise (< 0.5s), and measure total crossing duration.

---

## 5. Why We Ask the Two Questions to the Professor

### Question 1: Digital Map vs. Trajectory Inference
> *"Do we have an official HD map, OpenStreetMap GeoJSON, or aerial photo with known coordinates for K305, or should we infer crosswalk and lane boundary polygons directly from our trajectory clusters?"*
* **Why ask**: Proves we are proactively planning the spatial polygon pipeline for Week 2. If a map exists, it saves time; if not, we demonstrate an advanced clustering solution.

### Question 2: Traffic Light SPaT Data
> *"Will we receive signal state logs (SPaT data) for the traffic lights, or should we infer green/red phases based on vehicle queue stop-and-go patterns?"*
* **Why ask**: Topic 4 focuses on conflict zones. Distinguishing safe crossing during green from hazardous crossing requires knowing signal phases. Asking about SPaT shows advanced traffic engineering knowledge.

---

## 6. Week 2 Implementation Plan & Roadmap

1. **Noise Filtering**: Discard all tracks with duration $< 0.5\,\text{s}$ ($< 5$ frames) to remove sensor reflections.
2. **Track Stitching**: Merge tracks where $\Delta d \le 1.0\,\text{m}$ and $\Delta t \le 3.0\,\text{s}$ to fix tracker drops during red-light stops.
3. **15-Minute Volume Curves**: Aggregate person-seconds and cyclist-seconds across 15-minute intervals between 06:00 and 20:00.
4. **2D Heatmaps**: Discretize intersection K305 into $0.5\,\text{m} \times 0.5\,\text{m}$ grid cells to calculate dwell-time density.
5. **Typical VRU Routes**: Extract dominant walking and cycling corridors using DBSCAN trajectory clustering.
6. **Conflict Zone Analysis**: Compute spatial co-occurrence between VRUs and turning vehicles to highlight hazardous areas.

---

## 7. Live Demo Command

To run the live demo in VS Code terminal:
```bash
python eda_k305.py --quick
```
*Finished in ~7 seconds across 12 sampled files, printing full tables and the hourly profile.*
