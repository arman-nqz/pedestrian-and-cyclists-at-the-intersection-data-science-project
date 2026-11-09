_Draft written from the 29 October 2026 data (NSE, score of at least 0.25). The team should review and rewrite these before the final presentation._

- **Pedestrians, cyclists and motorcycles are 20% of the tracks in `clean` and 32% in `stitched`.** The movement filter removes many short pedestrian tracks, so check **Data quality** before comparing counts.
- **07:00 to 08:00 is the busiest hour for pedestrians, cyclists and motorcycles.** Pedestrians have further peaks at 13:00 and 15:00, cyclists at 15:00 and 16:00 (`clean`). See **Time**.
- **The most common pedestrian and cyclist movements connect the E and N arms** (Würzburger Straße east and Dr.-Willi-Reiland-Ring north), followed by W to S.
- **45% of pedestrian tracks and 25% of cyclist tracks use one of the detected crossings.** See **Space**.
- **The 29 October tracking is much cleaner than 14 October:** 64,426 track pieces instead of 232,417, and stitching joins 19% of them. 36% of all detections have a score below 0.25 and are left out.
