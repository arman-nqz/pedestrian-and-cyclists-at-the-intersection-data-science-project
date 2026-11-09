_Draft written from the analysis so far. The team should review and rewrite these before the final presentation._

- **The share of pedestrians, cyclists and motorcycles depends on the cleaning:** 18% of the tracks in `clean`, 32% in `stitched`. Cleaning removes many short pedestrian tracks. See **Data quality** before comparing counts.
- **Cyclists peak sharply in the morning (07:00 to 08:00); pedestrians are busiest at midday and in the late afternoon** (13:00, 17:00 and 15:00 in `clean`). See **Time**.
- **The most common pedestrian and cyclist movements connect the N and E arms** (Dr.-Willi-Reiland-Ring north and Würzburger Straße east).
- **The sensor splits one object into several tracks:** stitching joins 29% of the track pieces, and the movement filter then removes most pedestrian tracks.
