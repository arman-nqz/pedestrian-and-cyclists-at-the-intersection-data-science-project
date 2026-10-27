# Week 1 Meeting: Spoken Script & Presentation Guide
**Topic 4: Pedestrians and Cyclists at the Intersection – When and Where?**  
*Intersection K305: Dr.-Willi-Reiland-Ring & Würzburger Str., Aschaffenburg*  
*Target Talk Duration: 5 to 8 minutes*

---

## ⏱️ Quick Timing & Agenda Overview
* **Min 0:00 – 1:00**: What I did this week (Setup, documentation study, libraries).
* **Min 1:00 – 2:30**: Dataset scale & quick live terminal demo (`eda_k305.py --quick`).
* **Min 2:30 – 4:30**: 4 key findings from the data (VRU share, geometry, data quality).
* **Min 4:30 – 6:00**: The core methodology breakthrough: **"Duration vs. Count"** (Dwell time).
* **Min 6:00 – 7:30**: Roadmap for Week 2 & 2 targeted questions for the professor.

---

## 🗣️ Spoken Script (Memorize & Speak Naturally)

### 1. Introduction & Week 1 Preparation (~1 minute)
> *"Hello Professor / everyone,*  
> *During this first week, my primary objective was to set up my development environment in VS Code, thoroughly study the dataset documentation, and conduct exploratory data analysis on Intersection K305.*  
>  
> *I studied the LiDAR schema and reviewed the necessary Python tooling for our pipeline. Because the dataset spans 24 hours across 288 files with over 11 million detection records, I focused on high-efficiency, lightweight Python libraries — specifically streaming JSON processing using Python's standard library (`json`, `math`, `statistics`, `glob`, `collections`), and explored spatial libraries like `shapely` and `numpy` that we will use in upcoming weeks for polygon zones.*  
>  
> *To validate the data, I wrote a dedicated exploratory script, `eda_k305.py`, which parses the 5-minute files and verifies our core physical assumptions."*

---

### 2. Live Demo & Dataset Scale (~1.5 minutes)
> *(Action: Open terminal in VS Code and run `python eda_k305.py --quick`)*  
>  
> *"I can quickly show the output in the terminal. I built a `--quick` mode that samples across the 24 hours in about 7 seconds, as well as a full 24-hour scan mode.*  
>  
> *Here is what we confirmed about the data volume:*
> * We have **288 JSON files**, recorded at **10 Hz** (one frame every 0.1 seconds).
> * That gives us roughly **861,000 frames** and **11.5 million detections** across the full day.
> * There are 7 distinct classified object types: Cars, Vans, Trucks, Buses, Motorcycles, and critically for us: Pedestrians and Cyclists."*

---

### 3. Key Findings on VRUs & Data Cleanliness (~2 minutes)
> *"Four key observations stood out from the exploratory analysis:*  
>  
> 1. **High VRU Share**:  
>    *Pedestrians represent ~20.2% and cyclists represent ~3.3% of total detections across the 24 hours. Vulnerable Road Users make up nearly **23.5%** of the entire dataset. This means we have a very rich sample size for temporal and spatial modeling.*  
>  
> 2. **Physical & Coordinate Validation**:  
>    *All positions are in a metric sensor frame spanning roughly ±43 meters in X and Y, with vertical Z between -3.1 and +0.7 meters, representing the road surface relative to the sensor. Speeds are physically realistic (pedestrian median is ~0.6 m/s, cyclists ~1.4 m/s). Furthermore, vehicle yaw closely aligns with travel direction (`atan2(vy, vx)`) within a median deviation of only 1.9 degrees.*  
>  
> 3. **Data Completeness (Zero Nulls)**:  
>    *Every single detection has valid 3D coordinates, dimensions, and velocity vectors. There are zero missing or null records.*  
>  
> 4. **Identified Data Artifacts (Noise & ID-Switching)**:  
>    *We observed that ~15% of track IDs last for 3 frames or fewer (≤ 0.3 seconds). These are sensor noise or brief occlusions that we must filter out. Also, when pedestrians wait stationary at red lights, the tracker occasionally drops them and assigns a new track ID upon movement. We need a stitching rule in Week 2 so we don't artificially inflate unique pedestrian counts."*

---

### 4. Core Methodological Insight: "Duration vs. Count" (~1.5 minutes)
> *(This is the most important theoretical concept to impress the professor)*  
>  
> *"This brings me to our main analytical finding for Topic 4: **Why raw counting fails and why we must use Dwell Time (presence duration).**  
>  
> If someone walks across the crosswalk in 10 seconds, they generate 100 frames. But if someone waits at a red light for 60 seconds before crossing, they generate 600 frames.  
> If we simply count frames, the waiting person is over-represented by **6.5 times**. And if the tracker splits their ID into three tracks while waiting, raw ID counts are also distorted.  
>  
> Therefore, we formulated our metric around **spatial dwell time**:  
> Measuring total **person-seconds** and **vehicle-seconds** inside specific spatial polygons (crosswalks, sidewalks, bicycle paths). This gives an objective measurement of spatial occupancy, directly aligns with the poster requirements, and forms the mathematical basis for our heatmaps and VRU-vehicle conflict zones."*

---

### 5. Week 2 Roadmap & Questions for the Professor (~1.5 minutes)
> *"For next week (Week 2), our concrete roadmap is:*  
> 1. Implement trajectory filtering (discarding tracks < 0.5s) and track-stitching across stop lines.  
> 2. Aggregate the 24-hour data into **15-minute temporal curves** (06:00 to 20:00).  
> 3. Discretize the intersection into a **0.5m × 0.5m dwell-time grid** to produce the spatial heatmaps.  
> 4. Cluster trajectories to identify the dominant crossing paths.  
>  
> *Before we start implementing the spatial polygons, I have two quick questions for you, Professor:*  
>  
> * **Question 1 (Map & Geometry)**: Do we have an official HD map, OpenStreetMap GeoJSON, or aerial image with known coordinates for K305, or should we infer the exact crosswalk and lane boundary polygons directly from our trajectory clusters?  
> * **Question 2 (Signal Timing)**: Will we receive signal state logs (SPaT data) for the traffic lights, or should we infer green/red phases based on vehicle queue stop-and-go patterns?"*

---

## 📋 Cheat Sheet: Quick Answers if the Professor Asks

| Potential Question | Your Short Answer |
| :--- | :--- |
| *"How long does the script take to run?"* | *"In quick mode, it takes ~7 seconds across 12 sampled files. The full 24h run over all 288 files finishes in about 3 minutes because it streams file-by-file without overloading RAM."* |
| *"Why didn't you use pandas or a database yet?"* | *"For the exploratory week, stdlib Python allowed us to verify schemas and noise thresholds with zero overhead. For Week 2 spatial grids and 11.5M points, we plan to leverage vectorized libraries like Polars / NumPy and Shapely for polygon containment."* |
| *"What is the peak hour for traffic?"* | *"Total traffic peaks around 08:00 in the morning rush hour (~86k detections/5min), while VRU activity (especially cyclists and pedestrians) shows strong afternoon activity peaking between 14:00 and 16:00."* |
| *"What is the noise filter rule?"* | *"Any trajectory with fewer than 5 frames (< 0.5 seconds) will be filtered out as spurious sensor noise before calculating volume."* |

---

## 💻 Commands to Practice in VS Code
```bash
# Test the quick version (recommended for the live meeting):
python eda_k305.py --quick

# Full version (if professor asks for complete dataset numbers):
python eda_k305.py
```
