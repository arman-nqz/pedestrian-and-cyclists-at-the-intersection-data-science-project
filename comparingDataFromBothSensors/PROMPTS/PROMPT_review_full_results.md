# Task: review the full-run results of the NewSense vs Ouster sensor comparison

## Context

We study pedestrians and cyclists (VRUs) at intersection K305 and must choose
which sensor, NewSense or Ouster, gives more reliable VRU trajectories for the
rest of the project.

A notebook compares the two sensors on the same time and place:

- Data: 29.10, 07:20–11:25 CET.
- Epoch B (08:15–11:25 CET) is the primary result; epoch A (07:20–08:13 CET) is
  secondary.
- The full run has finished. Its own conclusion is **MIXED EVIDENCE**.

Your job is to review those results critically. Check whether the numbers are
trustworthy and whether the conclusion follows from them, and say what they
actually tell us. You are a reviewer, not the author: look for bugs, biases and
alternative explanations. Do not just restate the tables.

Read these first, in this order:

1. `comparingDataFromBothSensors/AGENT.md`: the handover guide, covering data
   facts, method, decision rule and known caveats.
2. `comparingDataFromBothSensors/PROMPT_sensor_comparison.md`: the original
   method specification. Read the sections relevant to what you check.
3. `comparingDataFromBothSensors/sensor_compare.py`: the implementation of
   every metric. Read a function before you interpret its output.

`ROOT = /home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project`.
Directory names contain spaces and a trailing dot, so quote paths in the shell.

## Where the results are

All paths are under `ROOT/comparingDataFromBothSensors/`.

| What | Path |
| :--- | :--- |
| Generated conclusion | `output/full/tables/conclusion.txt` |
| Scorecard: one row per metric × group × epoch × variant, with values, track counts, direction and better sensor | `output/full/tables/scorecard.csv` |
| All other tables | `output/full/tables/*.csv` (gates, stream health, single-sensor metrics, confirmation, class confusion, fragmentation, unconfirmed tracks, night check, VRU counts, 28.10 vs 29.10, video-check candidates) |
| Figures (11) | `output/full/figures/*.png` |
| Executed full notebook | `sensor_comparison_full.ipynb` (do not read its JSON; use the CSVs and PNGs) |
| Sample run, for comparison | `output/sample/` (10 min per epoch, provisional) |
| Parquet caches, if you need a custom check | `output/cache/` (per-file detections and frames in native coordinates, plus the matched pairs) |

The generated conclusion, as a quick orientation:
- NewSense is better on 15 of 24 VRU rows (epoch B, filtered).
- Without the three rows NewSense cannot lose by design, the split is 9 to 9.
- Ouster wins all 6 fragmentation rows, e.g. pedestrians: 2.27 NewSense IDs per
  Ouster track versus 1.27 Ouster IDs per NewSense track.
- NewSense wins on short tracks, implausible steps, jitter and the confirmation
  rate of moving VRUs.

## What to check

1. **Gates and data health.**
   - Confirm that alignment (gate 1), the clock offset (gate 2) and coverage
     (gate 3) are in the expected range in every window. Read the gate CSVs and
     `stream_health*.csv`.
   - Look closely at epoch A before 08:05 CET, when the Ouster dropped many
     frames, and at the short last window 08:10–08:13 CET.
   - Check how many frames stayed unpaired (`frame_pairing.csv`).
2. **Bugs and sanity.**
   - Shares lie in [0, 1].
   - No table is empty or all-NaN.
   - Both sensors and both epochs appear in every table.
   - Track counts are plausible: compare them with the sample and between the
     sensors.
   - If a value looks wrong, trace it to the code.
3. **Is the fragmentation result real, or an artefact?** This is the key question,
   because fragmentation is the team's main complaint about NewSense.
   - **Merged objects.** The LiDAR may merge a group of pedestrians walking
     together into one Ouster track. The matching is one-to-one per frame, but
     over time such a track can match different NewSense people. That inflates
     the NewSense ID count while NewSense is actually right. Check this, for
     example by looking at the n_ids distribution, at whether the extra IDs of
     one Ouster track overlap in time, or at Ouster track sizes. Use the cached
     matches and detections.
   - **Duplicate tracks.** NewSense might fragment by running parallel duplicate
     tracks rather than by sequential handovers. That would explain why its
     handover rate is lower than the Ouster's, even though the other sensor
     sees it split objects more.
   - **Your verdict.** Say which explanation the evidence supports.
4. **Confirmation-rate asymmetry.** Ouster moving pedestrians are confirmed by
   NewSense only about 60% of the time, against about 92% the other way round.
   - Find out whether these are real pedestrians that NewSense misses, Ouster
     false pedestrians, or a range or region effect. Look at
     `unconfirmed_tracks.csv`, the unconfirmed map and the class confusion.
5. **Rows that favour one sensor by construction.**
   - NewSense keeps one class and score per track and never leaves gaps, so it
     cannot lose the gap or class-stability rows.
   - Are there other rows that favour one sensor by construction? For example,
     the Ouster "filtered" variant drops tracks that are always UNKNOWN, and
     NewSense uses a score threshold.
6. **Decision rule.**
   - Is the rule reasonable (2/3 majority, fragmentation as a veto, the check
     without the structural rows)?
   - Would a sensible alternative weighting change the verdict? Show it, but do
     not replace the notebook's rule.
7. **Supporting checks.**
   - Night check: do NewSense static VRU ghosts sit at fixed structures?
   - 28.10 vs 29.10: does NewSense behave the same on both days?
   - VRU counts: does the sensor that fragments more count more?
8. **Video check plan.**
   - From `video_check_candidates.csv`, pick about 10 tracks per sensor whose
     check against the Miovision video would most change the conclusion.
   - Give their CET times and positions. The videos are in
     `ROOT/database/Data from date of 28.10, 29.10./mio vision/miovision/K305/2026_10_29/`.

## Rules

- **Do not rerun the notebook or a full analysis**, and do not parse the raw
  source files in `ROOT/database/`.
  - Custom checks must use the Parquet caches in `output/cache/`, loaded with the
    functions in `sensor_compare.py` (`load_sensor`, `make_variant`, `add_region`,
    and so on).
  - Keep custom checks small: one epoch or a few windows at a time. RAM is 14 GB.
- **Use the right Python.** Run Python with
  `comparingDataFromBothSensors/.venv/bin/python`. The repo-root `.venv` is broken.
  Run scripts from a file, not from stdin, because `sensor_compare` uses a
  process pool.
- **Keep the output small.** Never print raw data rows or `cat` large files.
  Print shapes and aggregates only. Look at as many of the 11 figures as you
  need.
- **Leave the existing files alone.** Do not modify `sensor_compare.py`,
  `sensor_comparison.py`, the notebooks or anything in `output/full/`. If you
  find a bug, describe it with evidence (file:line, expected vs actual) and
  estimate whether it could change the verdict. Do not fix it.
- **No git.** Do not commit or push anything.

## Deliverable

Write `comparingDataFromBothSensors/REVIEW_full_results.md` with these sections:

1. **Verdict in three sentences.** What the results support, how confident you
   are, and what would change it.
2. **Gates and data health.** Pass or fail, with the numbers.
3. **Bugs or suspicious values.** Each with evidence and its likely impact. Write
   "none found" if that is the case.
4. **Fragmentation: real or artefact.** Your checks, numbers and conclusion.
5. **Confirmation asymmetry.** Explanation, with evidence.
6. **Bias in metrics or the decision rule.** What favours which sensor, and
   whether the verdict is robust to it.
7. **Supporting checks.** Night, 28.10 and counts, briefly.
8. **Video check list.** A table of tracks to verify, and why each one matters.
9. **Recommendation to the team.** Which sensor to continue with, or what
   evidence is still needed before choosing, in plain language a project
   supervisor can read.

Label every number with its epoch, variant and group. Distinguish clearly
between what the data shows and what you infer. Then reply with a short summary
and the path to the review file.
