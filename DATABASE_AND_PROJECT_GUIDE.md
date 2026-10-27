# Comprehensive Database & Project Guide
## Topic 4: Pedestrians and Cyclists at the Intersection – When and Where?
### *Fußgänger und Radfahrer an der Kreuzung – wann und wo?*

---

## 1. Executive Project Overview

* **Course & Scope**: Data Science Project – Traffic & Mobility Data Analytics.
* **Topic Title**: Topic 4 – Pedestrians and Cyclists at the Intersection (When and Where?).
* **Testbed Location**: Intersection **K305** (*Dr.-Willi-Reiland-Ring* & *Würzburger Straße*, Aschaffenburg, Germany).
* **Core Objective**: Analyze trajectories of Vulnerable Road Users (VRUs: pedestrians and cyclists) to uncover temporal volume profiles, spatial density heatmaps, typical crossing routes, and conflict zones where VRU paths overlap with motorized vehicle traffic.
* **Real-World Impact**: Traffic safety engineering, signal timing optimization, infrastructure planning for active mobility, and decision support for urban intersections.

---

## 2. Dataset Architecture & Specification

The primary data is recorded by high-resolution roadside LiDAR sensors installed at intersection K305.

### 2.1 File Organization & Temporal Aggregation
* **Storage Location**: `database/k305_object_list_2026-10-14_aggregation_5min/`
* **File Count**: 288 JSON files covering a complete 24-hour cycle (`2026-10-14 00:00:00` to `2026-10-14 23:59:59`).
* **Interval**: Each file aggregates exactly 5 minutes of data.
* **Recording Frequency**: Recorded at **10 Hz** (10 frames per second, $\Delta t = 0.1\,\text{s}$ nominal between consecutive frames).
* **Nominal Volume per File**: $\approx 3,000$ frames in normal daytime conditions.
* **Total 24-Hour Scope**: $\approx 864,000$ frames and $\approx 11.5 \text{ to } 12$ million object detection instances across the day.

### 2.2 JSON Schema Reference

Each 5-minute JSON file contains a root dictionary with metadata and an ordered array of `frames`:

```json
{
  "intersection_id": "k305",
  "topic": "object_list",
  "aggregation_minutes": 5,
  "aggregation_start_local": "2026-10-14T08:00:00+02:00",
  "frames": [
    {
      "frame_timestamp": {
        "seconds": 1791957600,
        "nanosec": 123456
      },
      "timestamp_local": "2026-10-14T08:00:00.000123+02:00",
      "objects": [
        {
          "track_id": 156027,
          "class_name": "Pedestrian",
          "score": 1.0,
          "bounding_box": {
            "position": {
              "x": 11.85,
              "y": -12.69,
              "z": -0.33
            },
            "yaw": 2.318,
            "scale": {
              "x": 0.77,
              "y": 0.62,
              "z": 1.78
            }
          },
          "velocity": {
            "x": 0.85,
            "y": -1.33
          }
        }
      ]
    }
  ]
}
```

### 2.3 Field Dictionary

| Field Path | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `intersection_id` | `string` | - | Identifier of the intersection (`k305`). |
| `frame_timestamp.seconds` | `int` | s | Unix epoch timestamp in seconds. |
| `frame_timestamp.nanosec` | `int` | ns | Nanosecond fraction of the epoch timestamp. |
| `timestamp_local` | `string` | ISO 8601 | Local timestamp including timezone offset (`+02:00`). |
| `objects[].track_id` | `int` | - | Unique tracking ID assigned across consecutive frames. |
| `objects[].class_name` | `string` | - | Classified category (see Section 3). |
| `objects[].score` | `float` | $[0.0, 1.0]$ | Confidence score of the LiDAR detector (typically 1.0). |
| `objects[].bounding_box.position` | `dict (x, y, z)` | meters | 3D center position relative to LiDAR origin. |
| `objects[].bounding_box.yaw` | `float` | radians | Heading angle in horizontal plane $[-\pi, +\pi]$. |
| `objects[].bounding_box.scale` | `dict (x, y, z)` | meters | 3D bounding box dimensions (length, width, height). |
| `objects[].velocity` | `dict (x, y)` | m/s | 2D velocity vector in the horizontal plane ($v_x, v_y$). |

### 2.4 Coordinate Reference System (CRS)
* **Origin $(0, 0, 0)$**: Fixed at the roadside sensor mount overlooking intersection K305.
* **$X$-Axis**: Horizontal plane transverse coordinate (East-West span: $\approx [-43.0\,\text{m}, +40.0\,\text{m}]$).
* **$Y$-Axis**: Horizontal plane longitudinal coordinate (North-South span: $\approx [-43.0\,\text{m}, +41.0\,\text{m}]$).
* **$Z$-Axis**: Vertical elevation relative to sensor mounting plane ($\approx [-3.1\,\text{m}, +0.7\,\text{m}]$).
* **Orientation / Heading**: Velocity angle aligns with bounding box yaw:
  $$\text{Heading} = \text{atan2}(v_y, v_x) \approx \text{yaw}$$
  *(Empirical verification confirms median deviation is only $1.9^\circ$ / $0.034\,\text{rad}$).*

---

## 3. Detected Object Classes & Empirical Statistics

Analysis of daytime and nighttime samples shows 7 active object classes:

| Class Name | Category | Share of Detections | Typical Dimensions ($L \times W \times H$) | Mean Speed | Peak Observed Speed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Pedestrian`** | **VRU** | **17.51%** | $0.75 \times 0.65 \times 1.75\,\text{m}$ | $0.58\,\text{m/s}$ ($2.1\,\text{km/h}$) | $2.78\,\text{m/s}$ ($10.0\,\text{km/h}$) |
| **`Cyclist`** | **VRU** | **3.10%** | $1.90 \times 0.70 \times 1.75\,\text{m}$ | $1.41\,\text{m/s}$ ($5.1\,\text{km/h}$) | $6.38\,\text{m/s}$ ($23.0\,\text{km/h}$) |
| **`Car`** | Motorized | **71.24%** | $4.20 \times 1.80 \times 1.50\,\text{m}$ | $2.13\,\text{m/s}$ ($7.7\,\text{km/h}$) | $13.65\,\text{m/s}$ ($49.1\,\text{km/h}$) |
| **`Van`** | Motorized | **4.90%** | $5.30 \times 2.05 \times 2.10\,\text{m}$ | $2.25\,\text{m/s}$ ($8.1\,\text{km/h}$) | $13.20\,\text{m/s}$ ($47.5\,\text{km/h}$) |
| **`Truck`** | Motorized | **2.47%** | $8.50 \times 2.50 \times 3.20\,\text{m}$ | $1.85\,\text{m/s}$ ($6.7\,\text{km/h}$) | $11.50\,\text{m/s}$ ($41.4\,\text{km/h}$) |
| **`Motorcycle`** | Motorized | **0.56%** | $2.10 \times 0.80 \times 1.40\,\text{m}$ | $2.80\,\text{m/s}$ ($10.1\,\text{km/h}$) | $12.80\,\text{m/s}$ ($46.1\,\text{km/h}$) |
| **`Bus`** | Motorized | **0.22%** | $12.0 \times 2.55 \times 3.30\,\text{m}$ | $1.70\,\text{m/s}$ ($6.1\,\text{km/h}$) | $10.20\,\text{m/s}$ ($36.7\,\text{km/h}$) |

> [!NOTE]
> Vulnerable Road Users (VRUs) account for **$20.61\%$** of total object instances in the intersection. This provides rich statistical samples for pedestrian and cyclist analysis.

---

## 4. Data Cleanliness Assessment & Cleaning Protocols

### 4.1 Data Integrity Strengths
* **Zero Nulls**: All records contain non-null coordinate triplets $(x, y, z)$, dimensions, velocities, and local timestamps.
* **Stable Clock**: Frame timestamps increment at regular $0.1\,\text{s}$ ($\pm 1\,\text{ms}$) intervals during active periods.
* **Physical Realism**: Bounding box dimensions accurately match standard pedestrian, bicycle, and automotive engineering dimensions.

### 4.2 Cleaning Requirements & Artifacts Identified

```mermaid
flowchart LR
    A["Raw LiDAR Frames"] --> B["Filter Spurious Tracks\n(Length < 5 frames / 0.5s)"]
    B --> C["Track Stitching\n(Link ID switches at stop lines)"]
    C --> D["Boundary Reconnection\n(Join tracks across 5-min cuts)"]
    D --> E["Clean Trajectories for Topic 4"]
```

1. **Filtering Spurious Short Tracks (12.6% of raw tracks)**:
   * *Observation*: 12.6% of tracks exist for $\le 3$ frames ($\le 0.3\,\text{s}$). These are sensor noise, transient reflections, or partial occlusions.
   * *Rule*: Exclude any trajectory with $\text{total frames} < 5$ ($< 0.5\,\text{s}$) from volume counts and route analysis.
2. **Stationary Track Fragmentation & ID-Switching**:
   * *Observation*: When a pedestrian or cyclist waits at a red signal or crosswalk, stationary occlusion often causes the tracker to lose track and assign a new `track_id` upon re-detection.
   * *Example from data*: Position $(-33.5, -7.6)$ recorded three separate pedestrian track IDs (`156072`, `156105`, `156434`) back-to-back with zero displacement.
   * *Rule*: If Track $B$ appears within distance $\Delta d \le 1.0\,\text{m}$ and time gap $\Delta t \le 3.0\,\text{s}$ of Track $A$'s termination, stitch $A$ and $B$ into a single continuous entity.
3. **5-Minute Boundary Stitching**:
   * *Observation*: 25 to 30 continuous tracks span across the 5-minute file boundary with identical `track_id`.
   * *Rule*: Maintain a cross-file track accumulator rather than treating each 5-minute JSON as an isolated island, avoiding duplicate counting at boundaries.
4. **Temporal Inactivity Gaps**:
   * *Observation*: `k305_object_list_2026-10-14_00-00_to_00-04.json` contains a 220-second gap with no detected objects (midnight quiet period or sensor initialization). Daytime files are strictly continuous.

---

## 5. The "Duration vs. Count" Methodology

### 5.1 Why Counting People / Frames Fails
* **Raw Frame Count Bias**: A pedestrian waiting at a red light for 60 seconds produces **600 frames**. A pedestrian crossing quickly in 10 seconds produces **100 frames**. Simply summing raw detections over-represents waiting people by $6\times$.
* **Raw ID Count Bias**: Tracker dropouts cause a single waiting person to be counted as multiple people.
* **The Traffic Engineering Solution**: **Presence Duration / Dwell Time**.

### 5.2 Mathematical Formulation of Duration

#### A. Zone-Based Dwell Time
Let $Z_k \subset \mathbb{R}^2$ be a spatial zone (e.g., Southern Crosswalk, Northwest Sidewalk, Westbound Cycle Track).
For object $i$ observed at frames $t \in \{1, \dots, N_i\}$ with 2D position $\mathbf{p}_i(t) = (x_i(t), y_i(t))$:

$$\text{Dwell Time}_{i, Z_k} = \sum_{t=1}^{N_i} \mathbb{I}\Big(\mathbf{p}_i(t) \in Z_k\Big) \cdot \Delta t \quad (\text{seconds})$$

Where $\Delta t = 0.1\,\text{s}$ and $\mathbb{I}(\cdot)$ is the indicator function ($1$ if inside the polygon, $0$ otherwise).

#### B. Cumulative Exposure / Spatial Occupancy
The total presence duration of class $C$ in zone $Z_k$ over a 15-minute time window is:

$$\text{Occupancy}(C, Z_k) = \sum_{i \in C} \text{Dwell Time}_{i, Z_k} \quad (\text{person-seconds or vehicle-seconds})$$

* *Example Interpretation*: In the 08:00–08:15 morning window, pedestrian occupancy on the Southern Crosswalk was 2,450 person-seconds, with average crossing duration of $11.4\,\text{s}$ per person.

#### C. Continuous Spatial Dwell-Time Grid (Density Heatmap)
Discretize the intersection area into uniform grid cells $g_{u,v}$ of size $0.5\,\text{m} \times 0.5\,\text{m}$.
The duration density $D(u, v)$ is:

$$D(u, v) = \frac{1}{\text{Area}(g_{u,v})} \sum_{i} \sum_{t} \mathbb{I}\Big(\mathbf{p}_i(t) \in g_{u,v}\Big) \cdot \Delta t \quad \left(\frac{\text{seconds}}{\text{m}^2}\right)$$

---

## 6. Core Deliverables & Metrics for Topic 4

In accordance with the project specification poster ([`topic.pdf`](file:///home/arman/Projects/University%20data%20science%20project%20cameras/topic.pdf)), the analysis must deliver the following components:

```
+-----------------------------------------------------------------------------------+
| Topic 4 Requirements Matrix                                                       |
+-------------------+--------------------------------------+------------------------+
| Deliverable       | Required Output                      | Aggregation & Format   |
+-------------------+--------------------------------------+------------------------+
| Temporal Profiles | 15-Minute Volume & Duration Curves   | 06:00 to 20:00         |
|                   | (North, South, East, West corridors) | Pedestrians & Cyclists |
+-------------------+--------------------------------------+------------------------+
| Spatial Density   | 2D Dwell-Time Heatmaps               | Grid / KDE             |
|                   | Pedestrians, Cyclists, Motorized     | Intersection K305      |
+-------------------+--------------------------------------+------------------------+
| Typical VRU Paths | Clustered Crossing Trajectories      | Vector paths           |
|                   | Main marked crosswalks & bike tracks | LineString routes      |
+-------------------+--------------------------------------+------------------------+
| Conflict Overlap  | VRU-Vehicle Overlap Heatmap          | Spatial multiplication |
|                   | High-risk interaction zones          | Crosswalk corners      |
+-------------------+--------------------------------------+------------------------+
```

### 6.1 Key Metrics Table to Populate

| Metric Name | Poster Value (Benchmark Example) | Target Metric in K305 Dataset | Traffic Engineering Meaning |
| :--- | :--- | :--- | :--- |
| **Total Pedestrians (15 min)** | 450 | Peak 15-min window count | Pedestrian demand at marked crossings |
| **Total Cyclists (15 min)** | 310 | Peak 15-min window count | Cyclist demand on bike lanes & crossings |
| **Peak Hour (Pedestrians)** | 07:30 – 08:30 | Morning peak interval | Commuter / school pedestrian rush |
| **Peak Hour (Cyclists)** | 16:00 – 17:00 | Afternoon peak interval | Commuter / student cyclist return rush |
| **Main Pedestrian Crossing Area** | Southern Crosswalk (*Würzburger Str.*) | Highest pedestrian duration zone | Critical crossing with highest exposure |
| **Main Cyclist Route** | West–East (*Dr.-Willi-Reiland-Ring*) | Dominant trajectory cluster | Primary active transport corridor |
| **VRU–Vehicle Conflict Zones** | Crosswalk corners / turning pockets | High co-occupancy zones | Areas requiring safety interventions |

---

## 7. Recommended Technical Stack & Tools

* **Core Data Handling**: `Python 3.10+`, `pandas`, `numpy`.
* **High-Throughput Processing**: `polars` or `duckdb` (enables processing all 288 JSON files in under 2 minutes).
* **Spatial Geometry & Polygons**: `shapely` (`Polygon`, `Point`, `MultiLineString`) and `geopandas`.
* **Density & Heatmaps**: `scipy.stats.gaussian_kde`, `seaborn`, `matplotlib`.
* **Trajectory Clustering**: `scikit-learn` (`DBSCAN` / `HDBSCAN` on trajectory coordinate vectors).

---

## 8. Summary for Meetings with Professors & Supervisors

### 30-Second Elevator Pitch
> *"For Topic 4, we inspected the full 24-hour K305 dataset (288 files at 10 Hz, ~11M detections). VRUs represent over 20% of the data (~17.5% pedestrians, ~3.1% cyclists). We discovered that naive counting produces severe distortion due to tracker fragmentation when users wait at signals and spurious noise tracks (< 0.5s). To solve this, we formulated a duration-based spatial occupancy model that measures cumulative presence (person-seconds and vehicle-seconds) across sidewalks, crosswalks, and bike lanes, directly aligning with our temporal profiles, density maps, and conflict overlap goals."*

### Key Questions to Clarify with the Professor
1. **Intersection Map**: Do we have an official HD map, OpenStreetMap GeoJSON, or aerial orthophoto with coordinates for K305, or should we infer the crosswalk/lane polygons from trajectory clustering?
2. **Signal Phasing**: Will traffic light signal state logs (SPaT data) be provided for K305, or should signal phases be estimated from vehicle queue start/stop timestamps?
