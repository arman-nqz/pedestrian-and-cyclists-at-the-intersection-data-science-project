_Full comparison, 29 October 2026, 08:15 to 11:25 CET, pedestrians and cyclists. Source: `comparingDataFromBothSensors/` (`REVIEW_full_results.md`, section 10), checked against the video on 17 November 2026 (18 checks, page **Video check**)._

**Verdict: use Ouster for pedestrian and cyclist trajectories, with one caveat for groups.** The number comparison alone was mixed (NSE better on 15 of 24 rows, 9 to 9 without the rows NSE cannot lose). The video settles the open points mostly in Ouster's favour.

- **NSE splits one person into several ids.** On the scorecard, one pedestrian carries 2.3 NSE ids on average (Ouster 1.3), one cyclist 2.4 (Ouster 1.4); on isolated people 1.9 against 1.2. In the video, the isolated cases checked were 1 person each (O1, O3) where NSE gave 5 and 6 ids.
- **But Ouster merges people who walk together.** Both crowd checks (O4, O5) and one isolated case (O2: two people, one Ouster track, 7 NSE ids) were groups that Ouster tracked as one object. In busy spots part of NSE's extra ids are real extra people, and Ouster undercounts pedestrians in groups: treat its counts there as a minimum.
- **NSE's biggest cluster of standing "pedestrians" is a ghost.** Nobody stood at (−16.3, 1.8), the spot with 595 static NSE tracks (N1, N2). The spot at (18.7, 0.7), also "occupied" at night, was empty once (N4) and had a real person once (N3). Most of NSE's static pedestrian output is false, and Ouster is not missing people who wait there.
- **NSE detections with a score below 0.25 can be real people.** Both low-score tracks checked were real pedestrians walking (N7, N8). The 0.25 filter used on every page of this dashboard therefore drops real moving people, and NSE's lead in confirming Ouster's pedestrians was overstated. Score does not separate real people from ghosts; movement and location do (the ghosts are static and sit at fixed spots).
- **Both sensors miss people now and then.** NSE missed real pedestrians that Ouster saw (O8, O9) and called a pedestrian a motorcycle (O6); Ouster missed a real cyclist on the west side (N5).
- **28 October NSE data cannot back up 29 October**: every score is 1.0 and there is no motorcycle class.

_Limits: one viewer, 720 × 480 video, 18 short moments; O1, N2, N8 and O7 were marked "quite unclear", and O7, N6 and O10 could not be decided. The direction is clear, the sizes are not proven._
