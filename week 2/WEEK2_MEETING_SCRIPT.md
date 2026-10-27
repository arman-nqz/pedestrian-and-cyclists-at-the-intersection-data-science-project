# Week 2 Meeting: Spoken Script & Presentation Guide
**Topic 4: Pedestrians and Cyclists at the Intersection – When and Where?**  
*Near-Miss Safety Analysis Pipeline (TTC & PET)*  
*Intersection K305: Dr.-Willi-Reiland-Ring & Würzburger Str., Aschaffenburg*  
*Target Talk Duration: 5 to 8 minutes*

---

## ⏱️ Meeting Agenda & Timing Plan

* **Min 0:00 – 1:00**: Week 2 Goal & Architecture (From Exploratory Volume to Near-Miss Safety Analysis).
* **Min 1:00 – 2:30**: Mathematical Logic of Near-Miss Detection (Kinematic TTC & Spatial PET Proxy).
* **Min 2:30 – 4:00**: Full-Day Results Walkthrough (860k frames, 2,583 TTC events, mode breakdown, peak rush hours).
* **Min 4:00 – 5:30**: Current Limitations & Problems Discovered (Constant velocity assumption, bus circular envelopes, 2m grid PET artifacts).
* **Min 5:30 – 7:00**: 4 Strategic Questions for the Professor & Week 3 Roadmap.

---

## 🗣️ Spoken Presentation Script (Memorize & Speak Naturally)

### 1. Introduction & Week 2 Objective (~1 minute)
> *"Good morning / hello Professor,*  
>  
> *Last week, we established our data pipeline, verified coordinate geometries, and confirmed that Vulnerable Road Users (pedestrians and cyclists) make up over 20% of all detections at intersection K305.*  
>  
> *This week, we took the next major step required by Topic 4: **Conflict Zone and Safety Analysis**.  
> Because actual crashes are fortunately very rare, traffic safety cannot be evaluated by waiting for accidents to happen. Instead, we applied international **Surrogate Safety Measures (SSMs)** based on Heinrich's Safety Triangle to detect and quantify **near-misses**.*  
>  
> *I built both a vectorised Python processing pipeline (`near_miss_analysis.py`) and an interactive research notebook (`near_miss_analysis.ipynb`), and successfully ran a complete 24-hour scan across all 288 files from October 14, 2026."*

---

### 2. The Logic Behind the Pipeline (~1.5 minutes)
> *(Action: Point to the code or the logic flowchart in the guide)*  
>  
> *"Our pipeline implements two distinct safety metrics:*  
>  
> 1. **Time-To-Collision (TTC)**:  
>    *TTC calculates the time remaining before two moving bodies collide if they maintain their current speeds and headings. We formulate this as a quadratic equation: $a t^2 + b t + c = 0$, where $a$ is relative speed squared, $b$ is closing rate, and $c$ is the surface distance between their bounding envelopes.*  
>    *Because daytime peak hours have up to 40 objects per frame (requiring 780 pairwise comparisons per frame, 10 times every second), we vectorised this using NumPy array broadcasting. This solves all pairwise quadratic roots simultaneously in C-speed in under 1 millisecond per frame.*  
>    *We set our critical near-miss threshold to **TTC < 1.5 seconds**, following German and international transportation standards.*  
>  
> 2. **Post-Encroachment Time (PET)**:  
>    *While TTC predicts imminent collisions, PET is an observational measure: it calculates the time gap between user 1 departing a conflict area and user 2 arriving into that exact same space. Because we don't have official crosswalk polygons yet, we built a 2-meter grid-cell spatial accumulator to track sequential passage gaps.*  
>  
> 3. **Event Consolidation**:  
>    *At 10 frames per second, a single 1-second near-miss would generate 10 separate warnings. Our algorithm consolidates consecutive frames for the same vehicle-VRU pair into a single event, recording the duration, the minimum TTC reached, and the exact spatial coordinates."*

---

### 3. Full-Day Results Walkthrough (~1.5 minutes)
> *(Action: Open `output/full_day_20261026_204014_631230/run_report.json` and show `plot_ttc_consolidated_events.svg`)*  
>  
> *"Here are the concrete findings from processing the full 24-hour dataset:*  
>  
> * **Dataset Scope**: We processed **860,338 frames** and **11.5 million object detections**. Our noise filter cleaned out **54,113 spurious noise tracks** (< 0.5s).  
> * **TTC Near-Miss Events**: Across the day, we identified **2,583 consolidated near-miss events** between motorized vehicles and VRUs with TTC < 1.5s.  
>  
> * **Who is Involved?**  
>   * **Car vs. Pedestrian** represents **39.6%** (1,024 events).  
>   * **Cyclist vs. Car** represents **29.4%** (760 events).  
>   * Pedestrians are involved in **61.4%** of all near-misses; Cyclists in **38.6%**.  
>   * Notably, **Trucks and Buses account for nearly 20% of all near-misses** (387 pedestrian and 134 cyclist conflicts), highlighting serious turning blind-spot risks.  
>  
> * **When Do They Happen? (Temporal Peaks)**:  
>   * The near-misses aren't random. They cluster sharply around daily human routines:  
>     1. **Morning Rush (07:00 – 08:00)**: **300 events** (Work and school start).  
>     2. **Midday Peak (13:00 – 14:00)**: **295 events** (School dismissal and lunch travel).  
>     3. **Evening Rush (16:00 – 17:00)**: **286 events** (Commute home).  
>   * The median critical TTC across all events was **0.57 seconds**."*

---

### 4. Technical Problems & Limitations Discovered (~1.5 minutes)
> *(Action: Be candid and professional about the engineering challenges)*  
>  
> *"While these results give us a comprehensive safety baseline, our analysis revealed four important technical challenges that we need to refine:*  
>  
> 1. **Constant Velocity Assumption**:  
>    *TTC assumes straight-line constant speed. In reality, cars turn in curves, and drivers approaching crosswalks are actively braking. A car decelerating from 30 km/h to yield to a pedestrian 10 meters away triggers a false TTC alert before stopping safely.*  
>  
> 2. **Circular Bounding Envelopes on Large Vehicles**:  
>    *We model objects as circumscribed circles. For a 12-meter bus, this creates a 12-meter circular envelope. A bus passing a cyclist in an adjacent lane with 1.5m of safe lateral clearance triggers an artificial overlap.*  
>  
> 3. **The 2-Meter Grid PET Proxy**:  
>    *The grid proxy yielded 22,192 events—an order of magnitude higher than TTC. This is because pedestrians waiting at the curb and cars driving past sequentially touch the same 2-meter grid cells, inflating counts.*  
>  
> 4. **Lack of Traffic Signal (SPaT) Data**:  
>    *Without signal logs, we cannot distinguish between permitted green-turning yielding conflicts and dangerous red-light violations."*

---

### 5. Questions for the Professor (~1.5 minutes)
> *"To address these limitations for Week 3, I prepared four specific questions for you, Professor:*  
>  
> 1. **Signal State Data**: Do we have access to SPaT signal timing logs for K305, or should we infer traffic light green/red phases by analyzing vehicle queue stop-and-go patterns at the stop line?  
> 2. **Intersection Geometry**: Can we obtain an HD map or georeferenced aerial image of K305 to define true crosswalk polygons, or should we infer crosswalk boundaries by clustering pedestrian trajectories using DBSCAN?  
> 3. **Vehicle Geometry**: Would you recommend upgrading to 3D Oriented Bounding Box (OBB) polygon checks using the bounding box yaw, or calibrating class-specific lateral safety margins to eliminate the bus/truck false positives?  
> 4. **Deceleration Modeling**: Should we integrate a Constant Acceleration / Deceleration model (e.g. Deceleration to Clear) to filter out yielding vehicles before computing TTC?"*

---

## 📋 Q&A Cheat Sheet: Answers to Potential Professor Questions

| Professor's Question | Your Direct, Confident Answer |
| :--- | :--- |
| *"Why did the full-day run take 3.75 hours?"* | *"While the TTC frame math is vectorised in NumPy, track preprocessing relies on Pandas `groupby('tid')` across tens of thousands of tracks per chunk, and `PETAccumulator` stores millions of timestamps in nested Python dictionaries. For Week 3, we plan to stream tracks across boundaries and use Polars / NumPy arrays to drop runtime below 30 minutes."* |
| *"Why are there 22k PET events but only 2.5k TTC events?"* | *"TTC requires concurrent approaching motion on a collision path. PET measures sequential occupancy of the same space. Because our 2-meter grid cells cover the curb and sidewalk edges, a pedestrian waiting to cross and a car driving past sequentially trigger the 2m cell threshold. Defined crosswalk polygons will filter this noise."* |
| *"Why did you choose TTC < 1.5s as the threshold?"* | *"TTC < 1.5s is the standard benchmark established in literature by Minderhoud & Bovy (2001) and Hayward (1972) for urban intersections. 1.5 seconds corresponds to average human perception-reaction time (PRT) plus braking initiation."* |
| *"What do the zero TTC values in the CSV mean?"* | *"In our quadratic solver, if $c \le 0$, the circumscribed circles of the two bounding boxes are already touching upon detection. In real traffic this would be a collision; in LiDAR, it is typically a tracking artifact where the tracker momentarily merged two adjacent objects."* |
| *"How will you validate these near-misses?"* | *"We have exact `timestamp_local` down to microsecond precision and spatial coordinates `(x_mid, y_mid)`. We can load these timestamps into a 3D LiDAR trajectory visualizer or sync with intersection video camera feeds to visually ground-truth the top 20 lowest-TTC events."* |

---

## 💻 Commands to Demonstrate Live in Meeting

```bash
# 1. Run deterministic TTC kinematics self-test (instant verification):
python near_miss_analysis.py --self-test

# 2. Run quick 15-minute sample (08:00 to 08:14):
python near_miss_analysis.py

# 3. View the full-day report summary in terminal:
cat output/full_day_20261026_204014_631230/run_report.json | grep -E "frames_analysed|consolidated_ttc_events|runtime_sec"
```
