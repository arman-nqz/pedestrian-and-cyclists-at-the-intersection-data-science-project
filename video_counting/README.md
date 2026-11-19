# Video counting kit (07:35–07:44, 29 Oct 2026)

Ground-truth counts for the NewSense vs Ouster comparison (`analysisByArman/video_counting_plan.md`, step 3).
Counting finished on 19 Nov 2026: `video_counts.csv` is filled in and the results are [below](#results-19-nov-2026).

## What's here

| File | What it is |
| :--- | :--- |
| `clips/0735_gate_1_SCU4YV.mp4` … `0743_…` | one clip per minute for gate 1 (main road, camera SCU4YV) |
| `clips/0735_gate_2_SCU3K2.mp4` … `0743_…` | one clip per minute for gate 2 (cycle/foot crossing, camera SCU3K2) |
| `video_counts.csv` | the count sheet, 72 rows (9 minutes × 2 gates × 4 classes) |
| `make_clips.py` | rebuilds the clips (not in git: about 840 MB) |

## The two things that differ from the original plan

1. **Use the yellow SENSOR clock, not the camera clock.** The cameras run behind the LiDAR: SCU4YV by 80 s and
   SCU3K2 by 55 s. Each clip has been shifted to match sensor time already. The top bar shows the sensor time. It
   is yellow during the minute you count, and grey ("DON'T COUNT") during the 5 s before and after. Ignore the
   white clock in the bottom-right corner.
2. **Gate 2 has moved.** The original gate 2 is in fog at the edge of the picture. The red line now sits across
   the cycle/foot crossing over the main road, right in front of SCU3K2. Before running section F of the notebook,
   change `GATES['gate_2']` to:

   ```python
   'gate_2': ((12.71, -7.69), (7.59, -0.9)),   # cycle/foot crossing over the main road, visible in SCU3K2
   ```

   Gate 1 is unchanged.

## How to count

1. Open a clip in VLC. Press `E` to step one frame, and `[` / `]` to slow down or speed up (0.5× works well).
2. Count every object **once**, when it crosses the red line, in either direction. Count only while the top bar is
   yellow.
3. Classes:
   * `Pedestrian`: walking or running, including someone pushing a bike.
   * `Cyclist`: riding a bicycle, e-scooter or moped. Real motorcycles also go here; mention them in `notes`.
   * `Car`: cars, vans, pick-ups.
   * `Truck/Bus`: lorries, buses, trams.
4. Gate 2 sees crowds of 10–30 people crossing in a few seconds when the light turns green. Count these bursts
   frame by frame, or play them twice and keep the count you trust more. Gate 2 should have almost no cars,
   because the line runs along the lanes. Still record any car that does cross it.
5. Gate 1 is in the upper middle of the picture, and a lamp post covers part of it. A car hidden behind the post
   counts if you see it on both sides.
6. Write the number in `count` and your initials in `counted_by`. If a minute can't be counted, leave `count`
   empty and say why in `notes`.
7. Second person: count `07:35` and `07:36` on their own, and add their rows with their own initials.

The clock offsets are accurate to about ±1 s. An object that crosses within a second of a minute boundary may belong
to the minute next to it. Put it in the minute the yellow clock shows, and add a note if it's that close.

## Results (19 Nov 2026)

Each sensor's gate crossings (`sensorlib.gate_crossings` / `compare_counts`, Motorcycle merged into Cyclist, NewSense
moved into the Ouster frame with `transform.npy`) compared with the video counts. Notebook section F gives the same
numbers once `GATES['gate_2']` is updated as above.

| Gate / class | Video | NewSense | Ouster |
| :--- | ---: | ---: | ---: |
| Gate 1 – cars | 203 | 203 | 203 |
| Gate 1 – trucks/buses | 9 | 9 | 9 |
| Gate 1 – two-wheelers | 1 | 4 | 4 |
| Gate 1 – pedestrians | 0 | 2 | 1 |
| Gate 2 – pedestrians | 26 | 37 | 66 |
| Gate 2 – cyclists | 65 | 46 | 33 |
| Gate 2 – cars | 0 | 0 | 2 |
| **All objects** | **304** | **301** | **321** |
| Count accuracy, all classes | – | 93.8% | 89.8% |
| Count accuracy, by class | – | 83.9% | 69.7% |

Count accuracy = 1 − Σ\|sensor − video\| ÷ video total, summed over the minute × gate (× class) cells.

* **Vehicles:** both sensors match the video exactly. Per minute, both are within ±1, except 07:40 (Ouster +2),
  07:41 (NewSense +2) and 07:43 (Ouster +4).
* **Crossing (gate 2):** NewSense counts 83 of 91 pedestrians and cyclists (−9%), Ouster 99 (+9%). In the video 71% are
  cyclists; NewSense labels 45% of its crossings pedestrians, Ouster 67%.
* **Unresolved:** both sensors independently report three gate-1 two-wheelers that are not in the video count
  (07:39:06, 07:39:14, 07:43:27 sensor time). The video count was kept as final.
* **Not tested:** whether a sensor keeps one ID per person between gates. That needs the followed-object sample.
* **Limits:** one counter, no independent second count of 07:35–07:36 yet.

## How the gates and offsets were found (19 Nov 2026)

* **Offsets:** image motion per second was correlated with Ouster's moving-object counts over 07:34:30–07:44.
  The peaks were SCU4YV −80 s and SCU3K2 −55 s (r ≈ 0.45). These match the dashboard's −79 s plus the 24 s lag
  between the cameras. They do **not** match the −71 s set by eye earlier.
* **Gate positions:** a ground-to-image homography was fitted by matching Ouster objects to objects detected in
  the video. It was checked by rendering the frames where Ouster reports a gate crossing: the crossing objects sit
  on the drawn line. SCU3K2's fit is good (480 matches). SCU4YV's fit is weaker (33 matches) but sits right on the
  cars at gate 1.
* **Gate 1 visibility:** every Ouster and NewSense crossing of gate 1 lies on the part of the line SCU4YV can see.
* An automatic detector (YOLO11) misses most people in this foggy, interlaced 720×480 footage, so the counting
  stays manual.
