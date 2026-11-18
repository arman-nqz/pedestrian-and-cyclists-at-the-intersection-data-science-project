# Review of the full-run results: NewSense vs Ouster (K305, 29.10)

Reviewer: independent agent, 2026-11-16. Scope: `output/full/` (all tables, key figures), `sensor_compare.py`,
plus small custom checks on the Parquet caches.

All custom checks were run on **epoch B only**, filtered variant unless stated otherwise. The scripts are in the
session scratchpad and are not part of the repo. Before using any custom number, I reproduced the notebook exactly:
- ped B `frag_mean_n_ids` = 2.273 (n = 556) and bike B = 2.390 (n = 246);
- Ouster moving-ped confirmation = 0.605 and NewSense = 0.916.

One custom check rematched epoch B with **raw** NewSense (no score filter). It wrote its matches cache to the
scratchpad, not to `output/cache/`.

Notation: *[B, filtered, ped]* means epoch B, filtered variant, pedestrian group. "**Data:**" marks a measured
fact and "**Inference:**" marks my interpretation.

---

## 1. Verdict in three sentences

The data supports **MIXED EVIDENCE**, but leaning towards Ouster more than the 15–9 tally suggests: NewSense
fragmentation is real and survives every artefact check, while several NewSense wins come from the 0.25 score filter,
from per-track denominators diluted by static ghost tracks, or from how the metrics are built. I am about 75%
confident that fragmentation is a genuine NewSense defect, and less sure whether NewSense's many static "pedestrians"
(mainly at (−16.3, 1.8)) are real people waiting or ghosts. A video check that shows that cluster to be real people
would give NewSense a real advantage for waiting pedestrians; one that shows ghosts, or that confirms O1–O3 in section 8
are single people, would make Ouster the clear choice.

## 2. Gates and data health: **PASS** (with two caveats)

| Check | Result |
| :--- | :--- |
| Gate 1, alignment | **Pass.** Median share 0.87. Epoch B windows range from 0.835 (11:15) to 0.896 (09:50), all ≥ 0.50. Epoch A windows range from 0.848 (08:05) to 0.896 (07:20). The short last window, 08:10–08:13, has share 0.866 on n = 5870 vehicle detections, which is fine. |
| Gate 2, clock offset | **Pass, but epoch A was not tested by the notebook.** The scan used only three epoch-B windows (08:15, 09:45, 11:20). Mean share is 0.793 at 0.00, 0.867 at +0.05 (best), 0.855 at +0.10 and 0.823 at +0.15. **My check on epoch A:** at 07:35 and 07:50 the best offset is **0.00, tied with +0.05** (share 0.883 and 0.866), against +0.05 to +0.10 in B. Both lie inside [0, 0.15]. The pairing uses 0.08 ± 0.06 everywhere, so epoch A is paired about 0.03–0.05 s off-centre. That is negligible for pedestrians (< 0.1 m) and up to about 0.7 m for fast vehicles. **Impact:** none on the VRU verdict. |
| Gate 3, coverage | **Pass.** Every window has data from both sensors, including 08:10–08:13 (NewSense 24,437 and Ouster 47,633 detections). |
| Stream health, NewSense | Clean on both days: 2999.9 frames per 5 min, one gap ≥ 0.2 s per epoch, no duplicates. |
| Stream health, Ouster epoch A | **Degraded.** 2790 frames per 5 min. The worst window has ratio 0.848 (2545 of 3000 at 07:55). There are 750 gaps ≥ 0.2 s, a longest gap of 7.5 s and 318 duplicate timestamps. Six windows from 07:30 to 08:00 are below 0.97. |
| Stream health, Ouster epoch B | Good. 2993 frames per 5 min, minimum ratio 0.966 (08:25), 52 gaps, 83 duplicates, longest gap 7.5 s. |
| Frame pairing | The pooled CSV shows 2719 of 145,797 NewSense frames unpaired (1.9%), of which 2241 are one-to-one conflicts. **Split by epoch** (my check): **A: 2327 of 31,799 (7.3%)**, concentrated at 07:30–08:00 with 223–455 per window, against 5–51 elsewhere. **B: 392 of 113,998 (0.34%).** The conflicts come from the Ouster frame drops: two NewSense frames compete for the one surviving Ouster frame. |

**Caveat:** the epoch-A fragmentation and confirmation numbers come from 07:30–08:00, when 7–15% of Ouster frames
are missing. Epoch A is noisier, and its Ouster fragmentation (ped 1.63) is inflated by dropouts. This is a reason
to rely on epoch B, as the notebook does.

## 3. Bugs or suspicious values

No crash-type bugs. Every share lies in [0, 1], and no table is empty or all-NaN; the only NaNs are the `unk` rows,
because NewSense has no unk class. Both sensors and both epochs appear wherever expected. The issues below are
design or construction problems that bias specific rows.

| # | Issue | Evidence | Likely impact |
| :--- | :--- | :--- | :--- |
| 3.1 | **The NewSense score filter (0.25) is not neutral on 29.10.** The tracks it removes are mostly static and unconfirmed, but they include about 180 moving pedestrian tracks that are real. | `make_variant`, `sensor_compare.py:483`. On 29.10 epoch B, **56%** of raw NewSense ped tracks have score < 0.25 (median 0.243), as do 40% of cyclists (median 0.279). In-region ped tracks drop from 4879 to 2204 *[B, ped]*: moving from 858 to 677 and static from 4051 to 1547. **Raw rematch:** Ouster moving-ped confirmation goes from **0.605 to 0.790**, Ouster moving-bike from **0.738 to 0.821**, and NewSense moving-ped stays at 0.912. The 40,430 Ouster moving-ped detections matched only with raw NewSense look genuine: median distance 0.24 m (0.23 m for filtered matches), 87% NewSense "Pedestrian", and the two sensors move together (median NewSense speed 0.92 m/s against 0.99 m/s for the Ouster). | Changes `confirmation_rate_moving[bike]` from a NewSense win to a **tie** (0.805 vs 0.821) and shrinks the ped gap. See section 5. |
| 3.2 | **The filter also flatters NewSense on fragmentation and ghosts.** | Raw rematch *[B, NewSense raw vs Ouster filtered]*: NewSense fragmentation for ped goes from 2.27 to **2.61** and for bike from 2.39 to **2.54**. Ouster's stays at 1.28 and 1.40. NewSense static-ped tracks go from 1547 to **4051**, with static confirmation 0.226 falling to **0.131**. | With raw NewSense, the fragmentation verdict gets stronger. Most of NewSense's low-score output is static and unconfirmed. |
| 3.3 | **NewSense on 28.10 is a different output format.** | My check of the caches: on 28.10, **every** NewSense score is exactly **1.0**, and there is no "Motorcycle" class. On 29.10, scores range from 0.20 to 0.66 and there are 535 Motorcycle tracks. That is why raw equals filtered on 28.10 in `newsense_28_vs_29.csv`. | The 28.10 vs 29.10 comparison is **not like-for-like**: different software or configuration, and the filter does nothing on 28.10. AGENT.md section 5 ("score 0.20–0.66") is true only for 29.10. |
| 3.4 | **The handover metric misses NewSense class switches.** | `handovers()`, `sensor_compare.py:754`, requires the new track to have the same `tgrp` or `unk`. Among NewSense ID splits of ≤ 2 s inside an Ouster track, **34% (ped) and 66% (bike)** change class, mostly to Motorcycle. These are never counted. I measured this for NewSense only; the reverse direction (Ouster class switches) was not checked, although Ouster `class_multi_share` [B, ped] is only 0.039. | Understates NewSense handovers. See also 3.5. |
| 3.5 | **Per-track denominators are diluted by NewSense static ghosts.** | 70% of in-region NewSense ped tracks are not moving and 51% are unconfirmed *[B, filtered, ped]*; for Ouster the figures are 42% and 34%. The ped handover row by subset, NewSense vs Ouster: **per tracked minute 1.08 vs 0.88** (413 in 383 min against 380 in 435 min); moving and confirmed tracks 25.8 vs 24.2 per 100; moving only 25.6 vs 27.1; confirmed only 24.9 vs 30.3. | `handovers_per_100[ped]` is **not robust**: Ouster wins two of the four subsets and NewSense the other two. It should count as a tie rather than a NewSense win. |
| 3.6 | **The relative tie rule fails near zero.** | `_better`, `sensor_compare.py:1030`: `implausible_step_share[bike]` is NewSense 0.0000 against Ouster 0.0002, which counts as a NewSense win. That is about 15 implausible steps in 78,599. | One NewSense win that is practically a tie. |
| 3.7 | **"Motorcycle" maps to vehicle.** | `NS_GROUP`, `sensor_compare.py:85`. In epoch B, 14,091 NewSense-veh × Ouster-bike matches are 99% NewSense **Motorcycle** (13,924 detections, 247 NewSense tracks, 198 Ouster bike tracks). Of the 8481 NewSense-veh × Ouster-ped matches, 6821 are Motorcycle. | NewSense often labels cyclists, and some pedestrians, "Motorcycle", or else Ouster labels motorcycles BICYCLE. This removes tracks from NewSense's bike group. Only the video can tell which sensor is right. |
| 3.8 | **The fragmentation count includes other-sensor IDs of any class.** | `fragmentation()`, `sensor_compare.py:902–909`. Counting only VRU-class IDs: NewSense fragmentation for ped goes from 2.27 to **1.97** and for bike from 2.39 to **1.69**. Ouster's goes from 1.27 to 1.27 and from 1.40 to 1.39. | Smaller gap, but Ouster still wins all frag rows. |
| 3.9 | **The Ouster "filtered" variant is identical to raw for VRU rows.** | `single_sensor_metrics.csv`: Ouster raw and filtered rows are identical for ped, bike and veh, because only always-unk tracks are dropped. Matching uses filtered Ouster, so a NewSense detection next to an Ouster unk object stays unmatched. | A small bias against NewSense confirmation. It does not change any row. |
| 3.10 | **Track rates differ between the sample and the full run.** | In-region ped track rate in the sample (09:15–09:25) is NewSense 6.5/min and Ouster 9.5/min; in the full epoch B it is NewSense 11.6/min and Ouster 6.3/min. **Inference:** this is driven by the NewSense static cluster at (−16.3, 1.8), which is not constant over time. | Context only. The sample is not representative of NewSense static output. |

## 4. Fragmentation: real or artefact

Question: does NewSense fragment, or does the Ouster merge groups and so inflate the NewSense ID count?

**Data (epoch B, filtered).**

1. **n_ids distribution.** NewSense IDs per Ouster ped track: {1: 225, 2: 147, 3: 95, 4: 49, 5+: 40}. Ouster IDs per
   NewSense ped track: {1: 598, 2: 113, 3: 31, 4+: 7}. The NewSense excess comes from a broad shoulder of 2–4 IDs,
   not a few extreme tracks.
2. **Merged-group test, Ouster footprint.** If Ouster tracks with many NewSense IDs were merged groups, they would
   be larger. They are not. The median Ouster ped size is L × W = 0.72 × 0.70 m for n_ids = 1 and 0.70 × 0.69 m for
   n_ids ≥ 4, with 33–36 points in both cases. Tracks with concurrent NewSense IDs are 0.72 × 0.69 m, against
   0.72 × 0.70 m for the rest.
   - This test is **weak**. Ouster PERSON boxes vary little: per-track median L ranges from 0.54 to 0.87 m and W
     from 0.59 to 0.79 m (p5–p95). The classifier may cap or normalise box size.
   - What the boxes do show is that hardly any Ouster PERSON box is as large as a merged pair (≥ 1.2 m) would be.
     The verdict rests mainly on points 3–5.
3. **Pattern of the extra IDs.** I classified each pair of consecutive counted NewSense IDs inside an Ouster VRU
   track using the full NewSense track lifetimes:

   | Pattern | ped | bike |
   | :--- | ---: | ---: |
   | **Concurrent** (NewSense lifetimes overlap) | 267 (38%) | 172 (50%) |
   | **Sequential handover** (gap ≤ 2 s) | 286 (40%) | 119 (35%) |
   | **Dropout and re-acquire** (gap > 2 s, median 4.3 s) | 155 (22%) | 51 (15%) |

   - Concurrent pairs are **0.37 m apart (ped) and 0.18 m apart (bike)** in the median. 302 of the 439 ped and bike
     pairs are under 0.5 m. Two people walking side by side are about 0.6–1 m apart.
   - **76% (ped) and 98% (bike)** of concurrent pairs carry different NewSense classes. Typically a Cyclist track
     and a Motorcycle track run on the same object, or a Pedestrian track and a vehicle-class track.
   - **The overlap is often short:** median 2.0 s (ped) and 1.4 s (bike). Only **51% (ped) and 38% (bike)** of
     concurrent pairs overlap for 2 s or more. Those long-overlap pairs are clear **parallel duplicates**: median
     0.44 m (ped) and 0.14 m (bike) apart, with different classes in 70% and 97% of cases. The short-overlap pairs
     behave like handovers in which the new ID starts slightly before the old one ends.
   - **Recount with that split:** long parallel duplicates make up about **19% of the extra IDs** (136 of 708 for
     ped, 65 of 342 for bike). The remaining **about 80% are sequential splits**: handovers, short overlaps and
     dropouts.
4. **Isolated objects.** I kept only Ouster tracks with another Ouster object within 3 m in fewer than 10% of frames:
   - ped: NewSense frag **1.92** (share ≥ 2: 0.48, n = 178) against Ouster frag **1.16** (0.14, n = 275);
   - bike: **2.17** against **1.34**.

   In crowded scenes the gap is larger (ped 2.44 against 1.33), so crowding adds to it but does not create it.
5. **Reference-length bias.** Ouster reference tracks are longer, which gives them more chances to collect IDs.
   Binned by matched duration, NewSense is worse in **every** bin. For ped: 1.72 vs 1.24 for ≤ 15 s, 2.19 vs 1.19 for
   15–30 s, 2.98 vs 1.45 for 30–60 s, and 3.86 vs 1.67 for 1–2 min. **Extra IDs per matched minute:** ped NewSense
   3.15 against Ouster 0.94; bike 4.08 against 1.74.
6. **Robust to variants.** VRU-class IDs only: 1.97 vs 1.27 (ped). Raw NewSense: 2.61 vs 1.28.

**Why is the NewSense handover rate lower, then?**
- **Data:** about 19% of NewSense's extra IDs are long parallel duplicates. A further 19% (ped) to 31% (bike) start
  shortly before the previous ID ends. `handovers()` only looks for a new track starting *after* the old one ends (t0 > t1), so it cannot
  see either kind.
- **Data:** 34–66% of its sequential splits change class, which `handovers()` ignores.
- **Data:** its per-track denominator is diluted by static ghost tracks (section 3.5).

**Verdict.**
- **Data:** the merged-group explanation is not supported. Ouster track sizes do not grow with n_ids, concurrent
  NewSense IDs sit closer together than two people would, and the effect persists on isolated tracks.
- **Inference:** NewSense fragmentation is **real**. It is mostly sequential ID splits and re-acquisitions (about 80%,
  many overlapping by under 2 s). About 20% are parallel duplicate tracks on the same object, usually with
  conflicting classes (Cyclist and Motorcycle, Pedestrian and vehicle).
- **Inference:** a residual matching ambiguity in crowds, where nearest-neighbour swaps occur within 2 m, inflates
  the crowded-case numbers for both sensors. It does not explain the isolated-track gap.

## 5. Confirmation asymmetry

Ouster moving pedestrians are confirmed 0.605 of the time and NewSense ones 0.916 *[B, filtered]*.

**Data.**
- **Most of it is the NewSense score filter.** Of 86,248 unmatched Ouster moving-ped detections *[B, in region, paired
  frames]*:
  - 23% have a filtered NewSense detection within 2 m, and in 100% of those cases that detection was already
    matched to another Ouster object;
  - **64% have a raw NewSense detection within 2 m**, and 54% have a low-score (< 0.25) one.
- **Raw rematch.** Ouster moving-ped confirmation rises from 0.605 to **0.790** and moving-bike from 0.738 to
  **0.821**. NewSense moving-ped stays at 0.912 and moving-bike at 0.805.
- **The unconfirmed Ouster pedestrians look like real walkers.** Compared with confirmed Ouster moving-ped tracks
  (medians):

  | | Straightness | Speed | Size (L × W) | Points |
  | :--- | ---: | ---: | :--- | ---: |
  | Unconfirmed | 0.81 | 1.24 m/s | 0.72 × 0.68 m | 25 |
  | Confirmed | 0.84 | 1.28 m/s | 0.72 × 0.70 m | 33 |

  Only 1% of unconfirmed tracks have straightness below 0.3.
- **Most epoch-B video candidates are seen by raw NewSense at low score.** Of the 11 epoch-B Ouster video candidates:
  - 9 are seen by raw NewSense as a **low-score Pedestrian track** (median score 0.21–0.25, split into 2–6 IDs,
    matched share 0.30–0.83);
  - 1 (359009) is seen as a low-score Cyclist;
  - 1 (381083) is barely seen (18%, mostly "Motorcycle").
- **The raw-only matches are genuine:** median distance 0.24 m, 87% NewSense "Pedestrian", and the two sensors move
  at similar speeds (section 3.1).
- **Range and edge effect** for the rest. Ouster moving-ped confirmation by distance from the NewSense native
  coordinate origin, (−12.7, 6.1) in the common frame. *Assumption:* this origin is at or near the NewSense sensor.
  The rates are: 0.85 at < 10 m, 0.80 at 10–20 m, 0.65 at 20–30 m, **0.45 at 30–40 m** and **0.01 beyond 40 m**. The
  unconfirmed map shows Ouster misses along the outer sidewalks at about (−30, −12) and (−10, −27), at the edge of
  NewSense coverage. Restricting to cells where both sensors see moving VRUs changes the rates by ≤ 0.02, so the
  vehicle-dominated common region is not the cause.

**Inference.** The asymmetry is mainly an artefact of the analysis choice. Raising the threshold to 0.25 removes
about 180 of NewSense's 858 moving pedestrian tracks (21%) *[B, in region]*. Those are often the low-score pieces of a
fragmented pedestrian, so the unmatched share of Ouster moving-ped detections roughly halves without the filter
(0.395 to 0.21). The remainder is a NewSense range or edge limit beyond about 30 m. There is no evidence that the
Ouster invents pedestrians.

The flip side matters as much. Without the filter, NewSense also emits about 4000 static ped tracks per epoch B, of
which 87% go unconfirmed. **No single NewSense score threshold separates its real pedestrians from its ghosts on
29.10.**

## 6. Bias in metrics and the decision rule

**Rows that favour NewSense by construction or by analysis choice:**

| Row | Mechanism | Evidence |
| :--- | :--- | :--- |
| `gap_*`, `class_multi_share` (already flagged by the notebook) | NewSense never leaves gaps and has one class per track | 0.0000 in every 29.10 epoch-B row |
| `handovers_per_100` | Per-track denominator inflated by static ghosts; class switches not counted | Ped row not robust: Ouster wins per tracked minute (1.08 vs 0.88) and on moving and confirmed tracks; NewSense wins on moving-only and confirmed-only tracks |
| `flicker_track_share` | Same denominator dilution | Partly robust: on confirmed tracks only, NewSense 0.033 vs Ouster 0.132 [ped], so NewSense still wins |
| `confirmation_rate_moving` | Score filter removes real low-score NewSense pedestrians | Bike becomes a tie with raw NewSense; ped narrows to 0.912 vs 0.790 |
| `jitter_rms_m`, `implausible_step_share` | **Inference:** NewSense positions look heavily smoothed (tracker output), while Ouster positions are cluster centroids. Smoothness is not positional accuracy, and the code cannot tell the two apart | ped jitter 0.063 vs 0.124 m; bike implausible 0 vs 0.0002 is practically a tie |
| `confirmation_rate_static` (unscored) | Leaving it out hides NewSense static ghosts | NewSense static-ped confirmation 0.226 (filtered) and 0.131 (raw) |

**Rows that favour Ouster:** `flicker_det_share`, mildly. Ouster flicker tracks are short, so their detection share is
small. The Ouster filter (3.9) is also a mild bias against NewSense.

**Decision rule.**
- The 2/3 majority and the check without structural rows are reasonable.
- The fragmentation veto is defensible: it is the team's stated main complaint, and it is the most robust result.
- Two weaknesses:
  - The rows are not independent. Fragmentation has 3 rows, flicker 2 and gaps 2, so a metric family's vote counts
    2–3 times.
  - Close, small-sample rows count as full wins. Bike flicker: NewSense 0.065 [95% CI 0.047–0.088] vs Ouster 0.074
    [0.051–0.106]. Bike handovers: 33 of 553 [4.3–8.3%] vs 18 of 361 [3.2–7.7%]. Both are statistically
    indistinguishable.

**Alternative tallies** (epoch B, filtered, ped and bike; shown for comparison, not as a replacement):

| Weighting | NewSense | Ouster | Tie | Leader's share | Meets 2/3? |
| :--- | ---: | ---: | ---: | ---: | :--- |
| Notebook, all 24 rows | 15 | 9 | 0 | 62% NewSense | No |
| Notebook, without structural rows (18) | 9 | 9 | 0 | 50% | No |
| One vote per metric family, no structural rows (12 families: flicker, implausible, jitter, handovers, frag, confirmation × 2 groups; a split family counts as a tie) | 7 | 3 | 2 | 58% NewSense | No |
| Without structural rows, corrected for sections 3.5, 3.6 and 3.1, with statistically indistinguishable rows as ties (ped handovers, bike implausible, bike flicker_track, bike handovers and bike confirmation → tie) | 5 | 8 | 5 | 44% Ouster | No |

**Inference:** no reasonable weighting gives either sensor a 2/3 majority, so **MIXED is robust**. Once the biases
above are corrected, the direction moves from "NewSense ahead" to "Ouster slightly ahead". Ouster's wins (all
fragmentation) are the robust ones. NewSense's robust wins are flicker on confirmed tracks [ped], jitter (with the
smoothing caveat) and moving-ped confirmation (narrower without the filter).

## 7. Supporting checks

- **Night check.** There are 7 night cells from 29 static VRU tracks (22 ped and 7 bike, median 19 s).
  - **Data:** the NewSense static ghost spot at **(18.7, 0.7)** lies 0.4 m from a night cell. It holds 82 static ped
    tracks and 20 min *[B]*, and 12 of the 20 NewSense video candidates (11 in epoch A, 1 in epoch B). **Inference:** a fixed-structure
    ghost.
  - **Data:** the dominant epoch-B spot at **(−16.3, 1.8)** lies **18 m from any night cell**. It holds 595 static
    ped tracks, 78 min in total, and 54% of all unmatched static NewSense ped detections *[B]*.
  - **Inference:** either real people waiting, which the Ouster may absorb into its static background (a common
    LiDAR behaviour, not verified here), or a daytime-only ghost such as a reflection or shadow. **This spot is the
    single most important video check.**
  - The night table agrees: 49.6% of unconfirmed static detections lie in night cells in epoch A, but only 15.5% in
    epoch B.
- **28.10 vs 29.10.** The days are **not comparable as configured** (section 3.3: scores fixed at 1.0 and no
  Motorcycle class on 28.10). On a like-for-like basis, raw 29.10 against 28.10 *[B, ped]*:
  - flicker 0.076 vs 0.084;
  - ped tracks 4879 vs 3073;
  - bike tracks 667 vs 989. Fewer cyclists on 29.10 is consistent with cyclists being relabelled Motorcycle on that
    day.
  - Vehicle flicker doubles, from 0.019 to 0.040.

  **Inference:** NewSense behaviour, especially class assignment, differs between the days. 28.10 cannot validate
  29.10.
- **VRU counts** *[filtered, valid traversals ≥ 2 s and ≥ 3 m]*. In epoch B: ped NewSense 647 vs Ouster 690, bike 335
  vs 310. In epoch A: ped 383 vs 545, bike 292 vs 306. The per-window correlation is 0.78 (ped) and 0.72 (bike).
  - **Data:** the fragmenting sensor does **not** count more. The filter also removes 181 low-score moving ped tracks
    *[B]*.
  - **Inference, not tested:** many of its fragments are probably shorter than the 2 s and 3 m traversal limits. **Inference:** VRU counts from either sensor are of similar magnitude, but NewSense counts depend strongly on
  the score threshold.

## 8. Video check list

Clip naming assumption (from AGENT.md, unverified): `Standard_SCU{3K2,4YV}_2026-10-29_0600.00N.mp4` are one-hour clips
starting at 06:00 CET, so `.003` is 08:00–09:00, `.004` is 09:00–10:00, `.005` is 10:00–11:00 and `.006` is 11:00–12:00.
The offset is the minutes and seconds within that hour. Check both cameras. Positions are in the common frame (m),
so first locate the two ghost spots in the image to calibrate.

**NewSense tracks** (decide whether the static clusters and low-score tracks are real)

| # | Epoch | NewSense tid | CET | Clip @ offset | Position | Why it matters |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| N1 | B | 136172 ped, static | 09:02:54–09:06:17 | `.004` @ 02:54 | (−16.3, 1.8) | Main static cluster (595 tracks, 54% of unconfirmed static). Real people waiting, or a ghost? Decides whether NewSense static output is usable. |
| N2 | B | 130790 ped, static | 08:46:28–08:48:32 | `.003` @ 46:28 | (−16.3, 1.8) | Second sample at the same spot |
| N3 | B | 125506 ped, static | 08:30:56–08:33:03 | `.003` @ 30:56 | (18.7, 0.7) | Night-cell spot: confirm a fixed structure with nobody there |
| N4 | A | 117071 ped, static | 08:06:19–08:10:05 | `.003` @ 06:19 | (18.7, 0.7) | Same spot, epoch A (12 of 20 candidates are here) |
| N5 | B | 21091 bike, moving | 10:06:19–10:08:41 | `.005` @ 06:19 | (−33.2, −10.2) | The only long *moving* NewSense-only VRU: a real cyclist the Ouster missed? |
| N6 | A | 99301 ped, static | 07:24:14–07:25:58 | `.002` @ 24:14 | (−28.7, −11.8) | Third spot, near night-cell cluster at (−29, −17) and (−33, −5) |
| N7 | B | low-score ped tracks matched to Ouster 226639 | 09:48:31–09:50:20 | `.004` @ 48:31 | (−27.7, −13.2) | Ouster says ped. NewSense saw it only at score 0.21 (4 IDs). Is a < 0.25 NewSense track a real person? Decides the filter question (section 5). |
| N8 | B | low-score ped tracks matched to Ouster 110399 | 08:33:14–08:34:30 | `.003` @ 33:14 | (−10.4, −26.2) | Same question, a different sidewalk (score 0.21, 5 IDs) |

**Ouster tracks** (fragmentation and true misses)

| # | Epoch | Ouster tid | CET | Clip @ offset | Position | Why it matters |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| O1 | B | 91444 ped | 08:16:18–08:16:34 | `.003` @ 16:18 | (−7.4, 15.2) | Isolated, 5 NewSense IDs (2 concurrent). Expect **one** person, which confirms NewSense fragmentation |
| O2 | B | 92112 ped | 08:17:10–08:17:41 | `.003` @ 17:10 | (−36.2, −4.7) | Isolated, 7 NewSense IDs |
| O3 | B | 277765 ped | 10:13:49–10:14:46 | `.005` @ 13:49 | (20.0, 7.1) | Isolated, 6 NewSense IDs, on the other side of the intersection |
| O4 | B | 104439 ped | 08:28:00–08:28:22 | `.003` @ 28:00 | (−29.4, −11.8) | Crowded, 4 NewSense IDs. If this is a **group**, the merged-object hypothesis holds for crowds |
| O5 | B | 167887 ped | 09:17:50–09:18:00 | `.004` @ 17:50 | (−32.1, −20.0) | Crowded, 4 NewSense IDs. Same test |
| O6 | B | 381083 ped | 11:15:29–11:16:38 | `.006` @ 15:29 | (−10.2, −25.8) | Unconfirmed even by raw NewSense (18%, mostly "Motorcycle"). Real pedestrian, or something else? |
| O7 | B | 180262 ped (with 180221) | 09:25:17–09:26:27 | `.004` @ 25:17 | (−31.0, −16.4) | Two Ouster pedestrians 1.2 m apart. NewSense confirms one (raw 0.76) and not the other (0.30). Does **NewSense** merge pairs? |
| O8 | B | 331448 ped | 10:44:40–10:46:29 | `.005` @ 44:40 | (0.8, −19.1) | 109 s moving, raw NewSense only 48%. NewSense range or occlusion gap? |
| O9 | A | 47495 ped | 07:41:07–07:43:21 | `.002` @ 41:07 | (6.9, −11.5) | 133 s, 0% matched in epoch A (frame-drop period; raw not checked) |
| O10 | A | 45181 ped | 07:40:17–07:42:26 | `.002` @ 40:17 | (−27.4, −15.7) | 129 s, 0% matched; the same south-west sidewalk as the epoch-B misses |

**Sources.** N1–N6, O6 and O8–O10 come from `video_check_candidates.csv`. O7 is the partner of candidate 180221.
O1–O5, N7 and N8 come from my own checks (fragmentation cases and low-score matches) and are not in the CSV.

**Decision value:**
- N1, N2, N7 and N8 decide whether NewSense's detection advantage is real.
- O1–O5 decide whether fragmentation is NewSense's fault. If O1–O3 each show one person, fragmentation is confirmed.
- About 2 hours of targeted viewing covers all 18.

## 9. Recommendation to the team

**Plain language.**
1. The comparison was run carefully. Its data checks pass, and the result "mixed evidence" holds up under every
   alternative scoring I tried.
2. The team's complaint about NewSense is **confirmed by the data**. One person or cyclist typically appears under
   2–3 NewSense IDs: sometimes two IDs on the same person at once, often with contradicting labels such as
   "cyclist" and "motorcycle", and sometimes one ID replacing another. This is not caused by the Ouster merging
   people into groups. The Ouster keeps one ID per person far more often (about 1.2–1.4 IDs per person).
3. NewSense's apparent advantages (fewer very short tracks, smoother paths, confirming more of the Ouster's
   pedestrians) are partly produced by how we analysed it:
   - we threw away NewSense tracks below confidence 0.25. That removes more than half of its pedestrian tracks.
     Most of them are motionless and unconfirmed, but about one in five of its walking pedestrians goes too, and
     with them many of the Ouster's pedestrians that NewSense actually did see;
   - its many motionless "pedestrians" make per-track averages look better;
   - its smooth paths may be smoothing rather than accuracy.
4. NewSense also produces a large number of motionless pedestrian tracks that the Ouster does not see, concentrated
   at a few fixed spots. One of these spots is also "occupied" at night, so it is a false detection.
5. NewSense's data on 28.10 has a different format (no confidence values, no motorcycle class), so it cannot be used
   to back up 29.10.

**Recommendation.**
- **Lean towards Ouster** for VRU trajectory work, because trajectory analysis ("when and where") needs one ID per
  person, and that is where the Ouster is clearly better.
- Before committing, do the **video check in section 8**. About 2 hours of viewing on 18 tracks can confirm or
  overturn the open points.
- Specifically, confirm whether the motionless pedestrians at (−16.3, 1.8) are real people waiting. If they are,
  the Ouster may be missing people who stand still, which matters for "where do pedestrians wait".
- If the project needs counts of people standing still, or coverage of the near-field area within about 10 m of the
  NewSense sensor (where only 49% of NewSense's moving pedestrians are confirmed by the Ouster *[B, filtered]*, which may
  be an Ouster blind spot or a NewSense artefact),
  that is the one area where NewSense could add value. It would need its own validation.
- **Do not** compare the sensors again using 28.10 NewSense data as it is.

## 10. Video check results (added 2026-11-17)

All 18 checks of section 8 were watched by one team member in the dashboard's **Video check** page (both cameras,
with an Ouster / NewSense replay on one clock). Answers are in `video_check/results.csv`. O1, N2, N8 and O7 were marked
"quite unclear"; O7, N6 and O10 could not be decided. Video quality is 720 × 480.

| Question | Checks | Answer | Meaning |
| :--- | :--- | :--- | :--- |
| Is NewSense fragmentation real (isolated people)? | O1, O2, O3 | O1: 1 person (unclear), O3: 1 person; O2: 2 people | **Yes** for single people: one person, 5 and 6 NewSense IDs. O2 shows the Ouster merging two people into one track |
| Does the Ouster merge groups in crowds? | O4, O5 | group, group | **Yes.** Part of NewSense's extra IDs in crowds are real extra people |
| Main static cluster (−16.3, 1.8): people or ghost? | N1, N2 | nobody, nobody (N2 unclear) | **Ghost.** NewSense's largest static-pedestrian source is false |
| Night-cell spot (18.7, 0.7) | N3, N4 | someone standing (08:31), nobody (08:06) | Mostly a fixed-structure ghost; a real person stood there once |
| Third spot (−28.7, −11.8) | N6 | unclear | No conclusion |
| Are low-score (< 0.25) NewSense tracks real? | N7, N8 | yes, yes (N8 unclear) | **Yes.** The 0.25 filter removes real moving pedestrians (section 5 confirmed) |
| Does NewSense merge a pair? | O7 | other (unclear) | No conclusion |
| One-sensor-only movers | N5, O6, O8, O9, O10 | N5 real cyclist; O6 pedestrian; O8, O9 real pedestrians; O10 unclear | Both sensors miss real road users sometimes: Ouster missed a cyclist (N5, west edge); NewSense missed O8 and O9 and labelled the O6 pedestrian "Motorcycle" |

**What changes in this review.**
- Section 4 concluded that the merged-group explanation "is not supported", from Ouster box sizes. The video
  contradicts that for groups: in both crowd checks and in O2 the Ouster tracked several people as one object. The box
  size test was weak (section 4, point 2), and this is where it failed. The isolated-object result (NewSense 1.92 against
  Ouster 1.16 IDs per object) still stands, and O1 and O3 confirm it. The crowded-case gap (2.44 against 1.33) is partly
  real people, not only NewSense fragmentation.
- Section 7's open question is answered: the static cluster at (−16.3, 1.8) is a ghost, so NewSense has no proven
  advantage for "where do pedestrians wait" there.
- Section 5's inference is confirmed: low-score NewSense tracks include real walking people.

**Updated recommendation (replaces section 9's "lean towards Ouster ... before committing, do the video check").**
- **Use the Ouster for pedestrian and cyclist trajectories.** It keeps one ID per person far more often, and
  NewSense's main static output is false.
- **Caveat: Ouster pedestrian counts in groups are a minimum**, because it merges people who walk together.
- **If NewSense data is used, do not filter by score.** A 0.25 cut removes real walking people and keeps static
  ghosts. Filter static tracks at the known ghost spots and use movement instead. This also applies to the team
  dashboard, which currently drops NewSense detections below 0.25 (36% of rows).
- Both sensors miss real road users at the edges of their view; neither is complete on its own.
- The evidence is one viewer and 18 moments: the direction is clear, the sizes are not proven.

