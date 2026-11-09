# Does track stitching change the near-miss results?

Branch: `stitching-comparison`. New files: `track_stitching.py`, `compare_stitching.py`, `output/stitching_comparison/`.

## Question

The sensor sometimes loses an object and gives it a new `track_id` when it reappears. `near_miss_analysis.py` does not join such pieces. We join them (`track_stitching.py`) and run the existing TTC / PET-proxy functions again to see what changes.

## How to run

```bash
python compare_stitching.py --data-dir <folder with the 288 json files> --start 07:00 --minutes 120
python compare_stitching.py --data-dir <folder> --start 07:40 --minutes 15 --skip-published   # quick check
```

Outputs per window go to `output/stitching_comparison/<start>_<minutes>min/`: `summary.csv`, `event_overlap_vs_segmented.csv`, `ttc_events_<variant>.csv`, `stitch_info.json`, `comparison.png`.

## Variants (same TTC / PET functions, same thresholds)

| Variant | What it is |
|---|---|
| published | `near_miss_analysis.py main()` as is, one 5-min file at a time |
| segmented | control: whole window at once, tracks split at time gaps > 1 s, one class per segment, **no stitching** |
| stitched | segmented + stitching (joins pieces of the same object), one class per stitched track |
| clean | stitched + drop tracks with < 3 frames or < 2 m of movement |

## Result: 07:00 to 09:00 on 2026-10-14 (2 hours, the morning peak)

| Variant | TTC events | with pedestrian | with cyclist | PET-proxy events | pedestrian tracks | cyclist tracks |
|---|---:|---:|---:|---:|---:|---:|
| published | 466 | 275 | 191 | 455 | 5,285 | 2,222 |
| segmented (control) | 461 | 275 | 186 | 131 | 5,285 | 2,221 |
| stitched | 513 | 312 | 201 | 175 | 3,506 | 1,541 |
| clean | 275 | 177 | 98 | 80 | 859 | 613 |

Stitching made 9,234 joins from 31,795 segments (22,561 tracks left).

- **The control reproduces the published TTC result** (461 vs 466 events, 99% of the published events found again).
- **Stitching raises TTC events by 11%** (461 to 513), although it reduces pedestrian tracks by 34%. The 46 new events are mostly short (half last a single frame, median minimum TTC 0.46 s). They come from short fragments that the 5-frame minimum used to throw away and that are now part of a longer track. 91% of the stitched events were already found without stitching.
- **The clean filter removes 194 of 461 events (42%).** The removed events are shorter (median 3 frames vs 4) and have a lower TTC (median 0.48 s vs 0.77 s). They are mostly car vs pedestrian (72) and cyclist vs car (50), involving tracks that barely move. They may be noise, or they may be real events with stopped vehicles and waiting people. **We have not checked which.**
- **PET proxy: published (455) and control (131) differ a lot.** Our unverified explanation: the published code takes an object's class from the first row of its `track_id`, and `track_id`s are reused (see below), so classes can be wrong in the PET step. TTC is not affected because it uses the class of each row.

## Data finding: `track_id`s are reused

The same `track_id` can show up for different objects minutes or hours apart (for example one bus id with 7 frames spread over 5,500 s). Over one 5-minute file this does not matter, because the short scraps are dropped. If a longer window is processed at once, the id must be combined with a time-gap split, otherwise unrelated objects are glued together (this produced 178 false single-frame events in our first control run).

Also: the published run keeps 178,854 tracks and removes 54,113 short ones (sum 232,967). This is close to our 232,417 segments (tracks split at gaps > 1 s) and not to our 194,260 distinct ids, probably because tracks are counted per file there. This is a guess and should be confirmed.

## Validation of the stitching itself

`track_stitching.synthetic_cut_test()` cuts 0.5 to 3 s holes into long real tracks and checks that they are joined again. On the full day: 81% repaired, 0.6% joined to the wrong partner (pedestrians 91%). On real data there is no ground truth for the joins.

## Limits

- One 2-hour window, not the full day. Full-day runs take hours with the published code.
- Counts are candidate events from constant-velocity TTC and a 2 m grid PET proxy, with the limits already listed in `README.md`.
- No variant is verified as "correct". Next step: check a sample of events from each group (new in stitched, removed by the filter) by replaying the tracks.
