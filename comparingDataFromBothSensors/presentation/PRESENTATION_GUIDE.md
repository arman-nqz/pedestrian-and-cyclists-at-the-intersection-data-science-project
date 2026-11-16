# Presenter guide: how we compared NewSense and Ouster

Deck: `sensor_comparison_method.pptx` (14 slides, speaker notes on every slide).
All paths below are relative to `comparingDataFromBothSensors/`.

## 1. Overview

**Message.** We compared the two sensors fairly. We first made the data comparable (one map, one clock, three
gates, a common region), then measured track quality in two families: each sensor on its own, and the two sensors
checking each other. A fixed rule turned the measurements into one verdict. The verdict is "mixed evidence". The
Ouster is clearly better at keeping one ID per person, which is the team's main complaint about NewSense. A video
check comes next.

**Total time:** about 13–15 minutes, plus questions.

**Colour rule to say once:** blue is always NewSense, orange is always the Ouster (`sensor_compare.py`, `COLORS`).

## Words you will use (read this first)

| Word | What it means, simply |
| :--- | :--- |
| **Sensor** | A device at the intersection that "watches" the traffic. We have two: NewSense and Ouster. |
| **Ouster / LiDAR** | A LiDAR sends out laser light and measures what bounces back, so it "sees" objects in 3D. Ouster is the brand. |
| **Object list** | What a sensor writes down: ten times per second, a list of every object it sees, with a position, a speed and a type (pedestrian, cyclist, vehicle). |
| **Frame** | One of those lists, like one picture in a video. 10 frames per second. |
| **Detection** | One object in one frame ("a pedestrian is here at this moment"). |
| **Track** | The same object followed over many frames: one person's path across the intersection. |
| **ID (track ID)** | The number the sensor gives a track. Ideally: one person = one ID for the whole walk. |
| **VRU** | Vulnerable road users: pedestrians and cyclists. This is what the project is about. |
| **Epoch** | A part of the morning. Epoch A is before the Ouster was recalibrated, epoch B is after. |
| **Recalibration** | The Ouster's settings were changed at 08:13, so its "map" changed. That is why the morning is split in two. |
| **Fragmentation** | One real person gets several IDs, so one path is cut into pieces. The main complaint about NewSense. |
| **Flicker** | Very short tracks (under 1 second): something appears and disappears. |
| **Confirmation** | The other sensor also sees the same object at the same place and time. |
| **Ghost** | A "detection" of something that is not there, for example a pole seen as a person. |
| **Ground truth** | The real answer of what happened. We do not have it, except the video. |
| **Gate** | A safety check that must pass before we compare anything. |
| **Scorecard** | A table: one row per measurement, with the NewSense value, the Ouster value and which one is better. |

## 2. Slide by slide

Each slide has an **In simple words** box first: read it to understand the idea. The bullet points after it are what to say, and the sources are where the content comes from.

| # | Slide | Time |
| :--- | :--- | :--- |
| 1 | How we compared NewSense and Ouster | 0:30 |
| 2 | The question we had to answer | 1:00 |
| 3 | Same place, same time, two sensors | 1:00 |
| 4 | Step 1: one map and one clock | 1:15 |
| 5 | Three checks must pass before any comparison | 1:00 |
| 6 | Compare only where both sensors can see | 1:00 |
| 7 | Step 2: find the same object in both sensors | 1:15 |
| 8 | Each sensor on its own: are its tracks clean? | 1:30 |
| 9 | The sensors check each other | 1:30 |
| 10 | From many measurements to one verdict | 1:30 |
| 11 | Extra checks that support the comparison | 1:00 |
| 12 | Limits of the method | 1:00 |
| 13 | What we found, in plain words | 1:00 |
| 14 | Next step: check on video (and handover) | 0:45 |
| | **Total** | **about 14:15** |

### Slide 1: Title (0:30)

> **In simple words.** This is the opening. You tell the audience: I will not show you the final numbers in detail; I will show you *how* we did the comparison, so they can trust the results my colleague shows later. Think of it as explaining the rules of a competition before someone announces the winner. The two coloured dots matter: every chart uses blue for NewSense and orange for Ouster, so if they remember that, they can read every figure.

- My part is the method: what we measured, why, and how it became one verdict.
- My colleague presents the detailed results afterwards.
- Blue = NewSense, orange = Ouster in every figure.

Sources: `AGENT.md` §1; `sensor_compare.py` (`COLORS`).

### Slide 2: The question we had to answer (1:00)

> **In simple words.** The team has used NewSense so far, but NewSense has two problems. Problem 1: when one person walks across the intersection, NewSense often gives that person several different numbers (IDs), as if several people walked. Problem 2: sometimes objects pop up for a moment and vanish (flicker). Now a second sensor, the Ouster, is available for one morning. The question is simply: which of the two sensors follows pedestrians and cyclists better? The team will use the winner from now on. Two rules: pedestrians and cyclists count more than cars, and it is fine to say "we cannot clearly decide" instead of pretending.

- Which sensor gives more reliable trajectories of pedestrians and cyclists (VRUs) at K305? The team keeps using
  that sensor.
- Two known complaints about NewSense: one object gets several track IDs, and detections flicker.
- Ground rules: VRU evidence outranks vehicle evidence; an honest "mixed evidence" result is acceptable and better
  than a confident wrong one.

Sources: `AGENT.md` §1; `PROMPTS/PROMPT_sensor_comparison.md` ("Why this matters", §9).

### Slide 3: Same place, same time, two sensors (1:00)

> **In simple words.** Both sensors watched the same intersection at the same time, so it is a fair comparison: same people, same cars, same moment. Both write down ten times per second what they see. In the middle of the morning, at 08:13, the Ouster was recalibrated, which means its internal "map" changed. Data from before and after cannot simply be mixed, so we split the morning in two: epoch A (before) and epoch B (after). The two minutes of the change are thrown away. Epoch B is the one we trust most: it is long (more than 3 hours) and the Ouster worked smoothly then. In epoch A the Ouster missed many frames, like a video that stutters, so epoch A is only a second check.

- Both sensors watch K305 at the same time: 29.10, 07:20–11:25 CET. Both give object lists at 10 frames per
  second (ID, class, position, speed).
- The Ouster was recalibrated at 08:13. Epoch A = 07:20–08:13 (secondary), epoch B = 08:15–11:25 (primary, 3 h
  10 min). 08:13–08:15 is dropped from both sensors.
- Epoch B is the main one: it comes after the recalibration and covers more than three hours. Epoch A is noisier
  because the Ouster dropped many frames before about 08:05.

Sources: `AGENT.md` §5; `PROMPTS/PROMPT_sensor_comparison.md` (time constants, Ouster format);
`sensor_comparison.py` (purpose cell, limits cell); `REVIEW_full_results.md` §2 (caveat: rely on epoch B).

### Slide 4: Step 1: one map and one clock (1:15)

> **In simple words.** Each sensor describes positions in its own coordinate system, like two people giving directions from different starting points. Before comparing, we translate NewSense positions into the Ouster's system (turn and shift them so both use the same map). The clocks are also slightly different: the Ouster is about 0.08 seconds ahead, so we correct for that. How do we know this works? We look at fast cars: if the maps and clocks match, a car seen by NewSense should have an Ouster car within 1 metre at the same moment. The chart shows this is true for about 85–90% of fast cars all morning. If something were wrong, the line would drop close to zero. We use cars for this test because the transformation was fitted on moving vehicles.

- One map: NewSense positions are rotated and shifted into the Ouster's (epoch-B) coordinate system. The
  transformation was fitted on moving vehicles. Epoch-A Ouster data gets its own composed transformation.
- One clock: the Ouster clock runs about 0.08 s ahead of NewSense.
- Proof (figure, gate 1): the share of fast NewSense vehicles (> 4 m/s) with an Ouster vehicle within 1 m stays
  around 0.85–0.9 in every 5-minute window. Full run median 0.87.

Sources: `AGENT.md` §5; `PROMPTS/PROMPT_sensor_comparison.md` (transforms, gate 1); `REVIEW_full_results.md` §2
(median 0.87); figure `output/full/figures/gate1_alignment.png`.

### Slide 5: Three checks must pass before any comparison (1:00)

> **In simple words.** These are three safety checks (gates) that must pass before we compare anything, like checking that two scales show zero before weighing something. Check 1: do the cars from both sensors land on the same spot (the chart from the last slide)? Check 2: we try different clock corrections and see which lines the cars up best; it must be between 0 and 0.15 seconds, which confirms our 0.08 seconds. Check 3: both sensors must have data in every 5-minute block of the morning. If any check fails, the program stops by itself. Important: we never change the limits just to make a check pass. All three passed.

- Gate 1, alignment: values around 0.8–0.9 mean maps and clocks line up. Fails if median < 0.70 or any epoch-B
  window < 0.50.
- Gate 2, clock: time shifts from −0.30 to +0.30 s are tried; the best must be between 0 and 0.15 s. Then 0.08 s
  is used everywhere.
- Gate 3, coverage: after filtering, both sensors have data in every 5-minute window of both epochs.
- If a gate fails, the notebook stops; thresholds are never tuned to make it pass. All three passed in the full run.

Sources: `AGENT.md` §6, §4, §7b; `sensor_compare.py` (gate constants); `sensor_comparison.py` (gate cells);
`REVIEW_full_results.md` §2.

### Slide 6: Compare only where both sensors can see (1:00)

> **In simple words.** The Ouster sees much further (about 80 metres) than NewSense (about 40 metres). If we compared everything, the Ouster would look better just because it sees more road, which is not fair. So we only compare the area both sensors see well: we cut the intersection into small 2 m × 2 m squares and keep a square only if both sensors saw enough moving objects there. That is the grey area in the maps. We also look at the data in two versions. "Filtered" (the main one) throws away NewSense objects with a low confidence score (below 0.25, a filter the project already used) and Ouster objects with an unknown type. "Raw" keeps everything.

- The Ouster sees about ±80 m, NewSense about ±40 m, so both are restricted to the area both see.
- Common region: 2 m squares where each sensor has at least 30 moving detections (≥ 1 m/s) in epoch B. The same
  region is reused for epoch A, the night check and 28.10.
- Track-level measures use tracks with at least half of their detections inside the region.
- Two versions: filtered (main) = NewSense score ≥ 0.25 (earlier project work used this filter) and Ouster tracks
  with a known class; raw = everything.

Sources: `PROMPTS/PROMPT_sensor_comparison.md` §2, §3, "NewSense format"; `AGENT.md` §6; `sensor_comparison.py`
(common region cell); figure `output/full/figures/common_region_map.png`.

### Slide 7: Step 2: find the same object in both sensors (1:15)

> **In simple words.** Now we line up the two sensors. Step 1: for every NewSense frame, find the Ouster frame taken at the same moment (after the 0.08 s correction). Step 2: in those two frames, connect each object with the nearest object of the other sensor, but only if they are at most 2 metres apart, and each object can be used only once. We do not care here what type each sensor says it is; we only use position. It is like laying two photos taken at the same moment side by side and pointing at the same person in both. Step 3: these connections (matches) are used for the measurements on slide 9. Key message: neither sensor is "the truth". If only one sensor sees something, either that sensor imagined it or the other one missed it, and we cannot tell which from the data alone.

- Pair frames: each NewSense frame gets the Ouster frame nearest to its time + 0.08 s, accepted within 0.06 s,
  one-to-one (if two NewSense frames want the same Ouster frame, the nearer one wins).
- Match objects: in each frame pair, objects are matched one-to-one on centre distance (Hungarian assignment), at
  most 2 m, ignoring the class.
- Analogy (no new fact): two photos taken at the same moment; point at the same person in both.
- Neither sensor is the truth: an unmatched detection is a false detection by one sensor or a miss by the other,
  and the data cannot tell which.

Sources: `AGENT.md` §6; `sensor_compare.py` (`pair_frames`, `CLOCK_OFFSET`, `PAIR_TOL`, `MATCH_MAX_DIST`);
`sensor_comparison.py` (§5 cell and purpose cell).

### Slide 8: Each sensor on its own: are its tracks clean? (1:30)

> **In simple words.** The first group of measurements looks at each sensor alone, as if you judged a drawing of a path without comparing it to anything. A good sensor draws long, smooth, unbroken paths. The six measurements, all "lower is better": (1) very short tracks under 1 second, i.e. flicker; (2) gaps, i.e. holes in the middle of a path; (3) class switches, a track that is first "pedestrian" and then "cyclist"; (4) impossible jumps, a person moving faster than 4 m/s between two frames (a cyclist 15, a car 30); (5) jitter, how much the position shakes even when the object moves smoothly; (6) ID handovers, a path ends and right there, within 2 seconds and 1.5 metres, a new ID starts, so one path became two. Be honest about one thing: NewSense, by the way it works, never leaves holes and never changes a track's type; instead it starts a new ID. So it automatically wins measurements 2 and 3. That is why the final decision is also checked without them (slide 10).

- Same computation for both sensors, per group (ped, bike, veh), per epoch, per variant. Lower is better for all six.
- Very short tracks (< 1 s) = flickering. Gaps = missing frames inside a track. Class switches = a track in more than
  one known group. Impossible jumps = frame steps faster than 4 / 15 / 30 m/s (ped / bike / veh). Jitter = shaking of
  the position of tracks that move at least 3 m. ID handovers = a track ends and within 2 s a new track of the same
  group starts within 1.5 m of the extrapolated position.
- Built-in advantage: NewSense never reports gaps and keeps one class per track (it starts a new ID instead), so it
  cannot lose the gap and class rows. The verdict is therefore also checked without them.
- Stream health (frames per 5 minutes) is also measured but is not in the scorecard; it appears on slide 11.

Sources: `PROMPTS/PROMPT_sensor_comparison.md` §5; `sensor_comparison.py` (§4 cell); `sensor_compare.py`
(`SPEED_LIMIT`, `HANDOVER_*`, `FLICKER_S`, `STRUCTURAL_METRICS`); `AGENT.md` §5 (no gaps, one class).

### Slide 9: The sensors check each other (1:30)

> **In simple words.** The second group compares the sensors with each other, using the matches from slide 7. This is the most important part. (1) Confirmation: of everything sensor A reports, how much does sensor B also see? Higher is better. We only score moving objects, because for people standing still we cannot tell a waiting person from a ghost. (2) Fragmentation: this tests the main complaint directly. Take one long Ouster track of one person and look at which NewSense IDs were on that same person over time. If NewSense used 3 IDs (the diagram: one orange bar, three blue bars), NewSense cut that person into 3 pieces. We also do it the other way round, so the Ouster is judged by NewSense in the same way. Lower is better. (3) Class agreement: do both sensors call the object the same thing? We only show this as background; it does not vote.

- Confirmation rate (higher = better): share of a sensor's detections the other sensor reports within 2 m. Split into
  moving and static tracks; only the moving rate is scored, because for static detections "waiting people vs ghosts
  is ambiguous".
- Fragmentation (lower = better): for each track with at least 30 matched detections, count the distinct IDs of the
  other sensor that cover at least 5 matched frames. An Ouster track seen as several NewSense IDs measures NewSense
  fragmentation, and the reverse. Done in both directions. Three scored rows per group: mean IDs, share split into
  ≥ 2 IDs, ID changes per minute.
- Class agreement: confusion matrix of groups over matched pairs; context only, not scored.
- The diagram on the slide (one orange bar, three blue bars) is an illustration, not data.

Sources: `PROMPTS/PROMPT_sensor_comparison.md` §6; `AGENT.md` §6 (attribution); `sensor_comparison.py` (§5.1–5.3
cells); `output/full/tables/scorecard.csv` (`scored` and `note` columns).

### Slide 10: From many measurements to one verdict (1:30)

> **In simple words.** We now have many measurements, and each one has a winner. How do we decide overall? Think of a match with several rounds. Only the rounds about pedestrians and cyclists, on the main data (filtered, epoch B), count. If the two values are within 5% of each other, the round is a draw. Rounds with too few tracks (under 10) do not count. A sensor is declared the winner only if three things are all true: (1) it wins at least 2 out of every 3 rounds, a clear majority, not just a little more than half; (2) it does not lose the fragmentation rounds, because that is the team's main complaint; (3) both still hold when we remove the three rounds NewSense wins automatically (gaps and class switches, from slide 8). If any answer is "no", the result is "mixed evidence". The verdict sentence is written by the program from the numbers, so nobody could "help" either sensor.

- Voting rows: filtered variant, epoch B, ped and bike, scored metrics. Within 5% = tie; fewer than 10 tracks on
  either side = not scored.
- A sensor is recommended only if (1) it wins at least 2/3 of the comparable rows, (2) it does not lose the
  fragmentation rows, and (3) both still hold without `gap_track_share`, `gap_mean_missing_share` and
  `class_multi_share`.
- Otherwise the result is "MIXED EVIDENCE" with the split. Vehicle rows are context only. The conclusion text is
  generated from the scorecard, never hand-written.
- Say openly: reading "including the fragmentation rows" as a veto is our interpretation of the original task.

Sources: `sensor_compare.py` (`decide()`, `_tally()`, `_better()`, `TIE_REL`, `CLEAR_MAJORITY`,
`MIN_TRACKS_FOR_ROW`, `STRUCTURAL_METRICS`); `AGENT.md` §6; `PROMPTS/PROMPT_sensor_comparison.md` §9;
`REVIEW_full_results.md` §6 (veto is defensible: the team's main complaint).

### Slide 11: Extra checks that support the comparison (1:00)

> **In simple words.** These four extra checks do not vote; they help us understand the results. (1) Stream health: did each sensor deliver all its frames, 3000 per 5 minutes? This is how we saw the Ouster stuttering early in the morning. (2) Night check: NewSense reports many people standing still that the Ouster does not see. Are they real people waiting, or ghosts such as poles? At 2 a.m. almost nobody is outside, so if NewSense "sees" a standing person at the same spot at night, it is probably a ghost. In the map, blue dots are daytime standing detections that only NewSense sees, and black circles are the night spots. (3) Counting trips: both sensors count how many people walk or cycle by per 5 minutes; the counts should rise and fall together. More is not better, because a sensor that cuts paths into pieces could count one person twice. (4) Another day: there is no Ouster data on 28.10, so we only checked whether NewSense behaves the same as on 29.10. It turned out the 28.10 NewSense data is in a different format, so it cannot be used to support the 29.10 result.

- Stream health: frames per 5 minutes (3000 expected). Shows the Ouster frame drops in epoch A.
- Night check (02:00–02:30 CET): almost nobody is on the street, so static VRU tracks at night mark fixed-structure
  ghosts. Daytime unconfirmed static NewSense detections are compared with those night cells (figure).
- VRU counts per 5 minutes: trips ≥ 2 s and ≥ 3 m. Counts should follow each other; a fragmenting sensor counts higher,
  so a higher count is not better by itself.
- NewSense 28.10 vs 29.10: checks whether NewSense behaviour is typical. The review found the 28.10 data has a
  different format (all scores 1.0, no Motorcycle class), so it cannot back up 29.10.

Sources: `PROMPTS/PROMPT_sensor_comparison.md` §5, §6.5, §7, §8; `sensor_comparison.py` (§3, §6, §7, §8 cells);
`REVIEW_full_results.md` §2, §3.3, §7; figure `output/full/figures/night_check_map.png`.

### Slide 12: Limits of the method (1:00)

> **In simple words.** Every method has weak points, and saying them openly makes the talk more trustworthy. In short: it is only one morning; we do not know the real truth (only the video can tell); the Ouster was still being set up that morning; we have not seen the Ouster at night, in rain, or in the busy afternoon; the 0.25 filter on NewSense throws away many ghosts, but also some real walking people (about one in five of its walking pedestrians); and some measurements naturally favour NewSense. Also, some "rounds" are really the same question asked two or three times, so one topic can get several votes.

- One morning (about four hours on 29.10).
- No ground truth: unmatched detections are ambiguous.
- Ouster being reconfigured: recalibration at 08:13, frequent dropped frames before about 08:05.
- Night, rain and the afternoon peak untested for the Ouster.
- The 0.25 filter is not neutral: it removes many static NewSense tracks but also about one in five walking NewSense
  pedestrians.
- Some rows favour NewSense by construction (gaps, class switches; smooth paths may be smoothing, not accuracy);
  rows are not independent (one metric family votes 2–3 times).

Sources: `sensor_comparison.py` (limits cell); `PROMPTS/PROMPT_sensor_comparison.md` §9; `REVIEW_full_results.md`
§3.1, §6, §9.

### Slide 13: What we found, in plain words (1:00)

> **In simple words.** The short answer: there is no clear winner, so the result is "mixed evidence". Each sensor is good at something. NewSense has fewer very short tracks and smoother paths. The Ouster is much better at keeping one ID per person, which is exactly the team's main complaint about NewSense, and that complaint is now confirmed by the data. The big numbers on the slide mean: when the Ouster followed one pedestrian, NewSense used on average 2.27 different IDs for that person; in the other direction, the Ouster used 1.27 IDs per pedestrian. The perfect value is 1, one ID per person. An independent review of the results agrees it is mixed, but leans towards the Ouster for following paths, after a video check. Keep this slide short; your colleague shows the details.

- No clear winner: the generated verdict is MIXED EVIDENCE; no sensor reaches the 2/3 majority.
- NewSense: fewer very short tracks and smoother paths.
- Ouster: keeps one ID per person far more often; the team's complaint about NewSense is confirmed.
- Number shown: mean IDs per pedestrian, measured by the other sensor, epoch B, filtered: NewSense 2.27 vs Ouster
  1.27 (from `conclusion.txt`: 2.273 vs 1.268, n = 556/749).
- The independent review agrees the result is mixed, but leans towards the Ouster for trajectory work, after a video
  check.
- Keep it short; the colleague shows the details.

Sources: `output/full/tables/conclusion.txt`; `output/full/tables/scorecard.csv`; `AGENT.md` §7b;
`REVIEW_full_results.md` §1, §9.

### Slide 14: Next step: check on video (0:45)

> **In simple words.** The next step is to watch the video of the intersection at a few chosen moments, because the video is the only real "truth" we have. It answers three questions: does NewSense really give one person several IDs? Are the people NewSense sees standing still real, or ghosts? Are NewSense objects with a low confidence score (below 0.25) real people? The five most important moments take about 45 minutes to check, all 18 take about 2 hours. Then you hand over to your colleague with the sentence in section 3.

- The Miovision video is the only independent truth.
- Three questions: does NewSense really give one person several IDs; are the standing NewSense "pedestrians" real or
  ghosts; are NewSense tracks with a score below 0.25 real people?
- About 45 minutes for the 5 priority-1 checks, about 2 hours for all 18.
- Then hand over (section 3 below).

Sources: `VIDEO_CHECK_GUIDE.md` (goal, time needed); `REVIEW_full_results.md` §8.

## 3. Handover to the colleague

My talk ends at slide 14, after the method, the plain-language summary and the next step. The colleague's results
presentation begins with the actual numbers: the scorecard, the per-metric results and the review's detailed checks.

Handover sentence: *"Now that you know how we measured and how the verdict is built, [colleague] will show you what
the numbers say in detail."*

## 4. Likely questions and answers

**Why not just trust one sensor as the truth?**
Neither sensor is ground truth. An unmatched detection is either a false detection by one sensor or a miss by the
other, and the data alone cannot tell which. The video is the only independent check.
(`sensor_comparison.py`, purpose and limits cells; `VIDEO_CHECK_GUIDE.md`)

**Why is epoch B the main comparison?**
It is after the 08:13 recalibration and is 3 h 10 min long. In epoch A the Ouster dropped 7–15% of its frames
(07:30–08:00), which makes epoch A noisier and inflates its Ouster fragmentation.
(`PROMPTS/PROMPT_sensor_comparison.md`, time constants; `REVIEW_full_results.md` §2)

**How do you know the two maps really line up?**
Gate 1: fast NewSense vehicles have an Ouster vehicle within 1 m in about 87% of cases (median over windows, full
run); with the wrong epoch's transform the share is below 3%.
(`REVIEW_full_results.md` §2; `PROMPTS/PROMPT_sensor_comparison.md`, reference results)

**Why 0.25 as the NewSense score filter?**
Earlier project work filtered detections with score < 0.25. The review found this filter is not neutral on 29.10:
it removes 56% of NewSense pedestrian tracks, mostly static and unconfirmed, but also about 180 real moving
pedestrian tracks. No single threshold separates NewSense's real pedestrians from its ghosts on 29.10.
(`PROMPTS/PROMPT_sensor_comparison.md`, NewSense format; `REVIEW_full_results.md` §3.1, §5)

**Why does fragmentation have a veto?**
"Several IDs for one object" is the team's stated main complaint, and fragmentation is the most robust result. The
veto reading of the original rule is our interpretation.
(`AGENT.md` §6; `REVIEW_full_results.md` §6)

**Could the Ouster be merging groups of people, so that NewSense only looks fragmented?**
The review tested this. Ouster track sizes do not grow with the number of NewSense IDs, concurrent NewSense IDs sit
closer together (median 0.37 m for ped) than two people would, and the gap persists on isolated tracks. Its
conclusion: NewSense fragmentation is real (about 75% confidence).
(`REVIEW_full_results.md` §1, §4)

**NewSense has fewer ID handovers. Doesn't that contradict the fragmentation result?**
The handover measure only sees a new track that starts after the old one ends, with the same class. About 19% of
NewSense's extra IDs are parallel duplicates, more start just before the old ID ends, and 34–66% of its splits change
class. Its per-track rate is also diluted by many static tracks.
(`REVIEW_full_results.md` §3.4, §3.5, §4)

**Why are some rows removed in the second check?**
NewSense keeps one class and one score per track and never reports gaps inside a track, so it cannot lose
`gap_track_share`, `gap_mean_missing_share` and `class_multi_share`. The verdict must hold with and without them.
(`sensor_compare.py`, `STRUCTURAL_METRICS` comment; `AGENT.md` §6)

**Would a different weighting change the verdict?**
No. The review tried four tallies; none gives either sensor a 2/3 majority, so "mixed" is robust. After its bias
corrections the lean moves from NewSense to the Ouster.
(`REVIEW_full_results.md` §6)

**Why is a higher VRU count not better?**
A sensor that splits tracks into pieces can count more trips. In the full run the fragmenting sensor did not count
more, probably because many fragments are shorter than the 2 s / 3 m trip limit (an untested inference in the review).
(`sensor_comparison.py`, §7 cell; `REVIEW_full_results.md` §7)

**Why not use 28.10 to confirm the result?**
The Ouster has no data for 28.10, and NewSense 28.10 has a different output format (all scores 1.0, no Motorcycle
class), so it cannot validate 29.10.
(`AGENT.md` §5; `REVIEW_full_results.md` §3.3, §7)

## 5. Open questions for the presenter

Points the sources do not explain, or where they disagree:

1. **Reasons for the numeric thresholds.** The sources state but do not justify: 2/3 as the "clear majority",
   the 5% tie band, the minimum of 10 tracks per row, the 2 m matching gate, the 0.06 s pairing tolerance, the 1 s
   flicker limit, the 2 s / 1.5 m handover window, the 4 / 15 / 30 m/s speed limits, the 30-detection region
   threshold, the 30 matched detections and 5 frames per ID for fragmentation. Prepare your own short reasons, or
   say they were design choices.
2. **Why the coverage gate.** The sources say what gate 3 checks but not why. The deck states only what it checks.
3. **Why epoch B was chosen as primary.** The original specification simply declares epoch B primary. The deck uses
   the review's supporting reason (after the recalibration, Ouster frame drops in epoch A) and the epoch lengths.
4. **Veto interpretation.** The original rule says "a clear majority of those rows, including the fragmentation
   rows". The code reads this as "wins ≥ 2/3 and does not lose the fragmentation rows" (`_tally()`), which
   `AGENT.md` calls "our interpretation". Decide how you want to present it.
5. **Which conclusion to emphasise.** `conclusion.txt` says MIXED EVIDENCE with NewSense ahead on the raw tally
   (15–9; 9–9 without structural rows). `REVIEW_full_results.md` says mixed but leaning towards the Ouster. The deck
   follows the instruction to interpret through the review. Agree the wording with your colleague so the two talks
   match.
6. **Disagreements between sources (code followed for what was done):**
   - `AGENT.md` §2 lists the independent review as "Not yet run", but `REVIEW_full_results.md` exists.
   - `AGENT.md` §5 gives NewSense scores 0.20–0.66; the review shows this holds only for 29.10 (all 1.0 on 28.10).
   - The original specification describes frame pairing without the one-to-one rule; the code (`pair_frames`) and
     `AGENT.md` pair one-to-one.
   - The notebook's fragmentation note says "values near 0 mean one ID per object". That fits the share of tracks
     split into ≥ 2 IDs; the mean number of IDs has a minimum of 1, as slide 13 says.
   - `handovers_per_100[ped]` counts as a NewSense win in the scorecard; the review says it is not robust and
     should count as a tie.
7. **Colleague's name** for the handover sentence (slide 14 notes and section 3 use "[colleague]").
