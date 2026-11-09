_29 October 2026, NSE object list (score at least 0.25), variant `clean` unless stated. Signal mapping is inferred, not from the junction plan._

**When**
- **07:00 to 08:00 is the busiest hour** for pedestrians, cyclists and motorcycles alike: the morning commute to the university. Pedestrians peak again at 13:00 and 15:00, cyclists at 15:00 and 16:00. See **Time**.

**Who**
- **Vulnerable road users (pedestrians, cyclists, motorcycles) are 20% of all tracks** in `clean` (3,829 pedestrian, 2,551 cyclist, 1,626 motorcycle tracks against 28,138 cars). In `stitched` they are 32%: the movement filter drops many short pedestrian tracks, so the true share is somewhere between.

**Where**
- **Most pedestrian and cyclist trips link the E and N arms** (Würzburger Straße east and Dr.-Willi-Reiland-Ring north): 821 tracks E to N and 722 N to E, then W to S with 357. See **Space**.
- **45% of pedestrian tracks and 25% of cyclist tracks pass one of the five crossings** (X1 to X5). The rest walk or ride along the sidewalks, or cross somewhere the zones do not cover.

**Signals**
- **10 to 17% of pedestrians step onto a crossing on red**: 17% at X1, 10% at X2, 12% at X4. Cyclists: 7% at X1, 11% at X2. See **Signals**, and check single cases in **Video**.

**Conflicts**
- **The original pipeline finds 3,566 near-misses (time to collision)**. Most involve a VRU: car and pedestrian 910, cyclist and car 816, motorcycle and pedestrian 583, motorcycle and cyclist 501.

**How far to trust the data**
- **NSE and Ouster agree on most objects**: 77 to 93% of NSE detections are also seen by Ouster in the four 10-minute windows. Vehicles get the same class 93 to 99.6% of the time, pedestrians 74 to 87%, cyclists only 44 to 63%; 30% of NSE cyclists are persons for Ouster. Ouster reports 1.1 to 1.6 times more pedestrians and longer tracks. Cyclist counts are the least certain number here. See **NSE vs Ouster**.
- **Tracks break into pieces**: 64,426 pieces for the day; stitching joins 19% of them. 36% of detections score below 0.25 and are left out. See **Data quality**.
