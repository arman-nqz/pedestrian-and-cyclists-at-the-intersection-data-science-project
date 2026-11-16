# Pedestrians and Cyclists at the Intersection: When and Where?
## A comparison of the Newsense and Ouster traffic sensors at intersection K305 (Würzburger Str./Ring, Aschaffenburg)

**Final research report.** Version 2, 2026-11-14.

* Version 1 (2026-11-13) is kept unchanged in `~/Downloads/K305_Analysis_Outputs/` (package root).
* V2 applies the 13 corrections confirmed by the final-package audit; each is listed in `V2_CHANGE_LOG.md`.
* That audit re-implemented the key calculations from the raw data, but it was carried out by the same analyst. It is **not an independent external review**, and this package is **not** described as fully scientifically validated (`V2_VALIDATION_REPORT.md` lists what could not be verified).

* Every number comes from a reproducible script under `stage4_traffic_analysis/`; source files are named in each section.
* Figures are in `final_figures/` (PNG; SVG originals are in the checkpoint folders).
* Evidence levels: **[M]** measured, **[E]** estimated, **[I]** indicative (small or single-rater sample), **[U]** unverified or not measurable.

---

## 1. Executive summary

**Question.** Which of two sensor systems, Newsense and Ouster, is more suitable for analysing pedestrians and cyclists, and under which conditions?

**Ground rules.**

* Neither sensor is ground truth.
* More detections do not mean better detection.
* No overall winner is forced.

**The comparison base is narrow.** Both sensors overlap for only **83 minutes** (29 Oct 2026, 07:12–08:35) in a **2,780 m²** common area. The only independent reference is one hazy video camera.

**Main findings:**

1. **Newsense's "2.5× more pedestrians" is mostly static false objects, not extra people.**
   * The surplus is stationary: 85 % of unconfirmed Newsense pedestrian observations are stationary, and 78 % lie in 10 spots.
   * The largest spot is a traffic-signal pole, video-confirmed [I].
   * For **moving** pedestrians, Newsense records *less* movement than Ouster in the same area and time: 9.5 vs 14.2 km of robust moving path (0.67×) [M].
   * This corrects an earlier audit statement ("equal total path"), which was a position-jitter artefact (CORR-01).
2. **Ouster tracks are longer and more continuous.**
   * Pedestrian tracks last a median 9.3 s vs 4.7 s.
   * Newsense breaks moving tracks more often per km in every group [M]. At a 2 s window: pedestrians 1.6×, cyclists 3.1–3.7×, vehicles 3.4×. The size depends on how Ouster UNKNOWN fragments are counted (pedestrians 1.2–1.9×, vehicles 2.0–3.4×); the direction does not.
   * **Newsense recycles track IDs**: within 83 min, 639 IDs were reused for other objects (636 after more than 60 s) and 59 were swapped instantly between a vehicle and a cyclist. Ouster did neither. It re-attached the same ID after a 5–30 s loss 359 times, each flagged by its own re-find field; whether it was always the same object is not verified [M].
3. **Newsense is steadier, but steadier is not more accurate.**
   * Newsense positions never jump and scatter only 2–3 cm at rest; Ouster pedestrian positions show 1–2 m jumps in 6–22 % of tracks, depending on the threshold [M].
   * But Newsense's reported *speeds* are noisier, and its velocity starts at 0 for the first 0.5 s of every track.
   * The two sensors filter differently. Neither can be shown to be more accurate without a surveyed reference [U].
4. **Pedestrian vs cyclist classification is unreliable in both.**
   * 39 % of Newsense "cyclists" are "persons" to Ouster.
   * Newsense also reports the same road user as two classes at once (628 persistent pairs vs 1 for Ouster).
   * Ouster starts 73 % of its pedestrian tracks as UNKNOWN.
   * Video could not settle who is right [M/I].
5. **Coverage and availability point in opposite directions.**
   * Ouster covers about 3.5× the area (to about 97 m vs about 40–47 m) [M].
   * Newsense delivered two full mornings and supports time-of-day analysis: a stable 07:30–07:45 peak of pedestrians and cyclists on both days [M].
   * Ouster delivered 84 minutes with 4.9 % dropped frames.
6. **Safety indicators are sensor-dependent.**
   * Both sensors produce similar numbers of severe candidate interactions (TTC < 1.5 s: 31 vs 35) but **mostly different events**: only 11–23 % have any TTC event (< 3 s) at the same place and time in the other sensor, and only 1 of 31 and 1 of 35 are severe (< 1.5 s) in both.
   * Stationary "pedestrians" add many indicator events in Newsense (TTC < 3 s: 789 vs 193 in Ouster). 388 of the 789 lie at the 10 known Newsense ghost locations; the others are not shown to be spurious and may include real waiting pedestrians.
   * Conflict studies need video confirmation whichever sensor is used [M].
7. **Timing.**
   * Both sensors' timestamps are about 2.8 s later than the video-derived reference for the same motion [M].
   * The cause is unknown, so the approved clock model was left unchanged.

**Application-specific recommendation** (section 19):

* **Ouster** is preferable for trajectory-based pedestrian and cyclist studies: movement paths, track continuity, coverage of the full junction, transparency about predicted positions.
* **Newsense** is preferable for long-duration counting and time-of-day patterns of *moving* road users, *provided* static detections are removed and IDs are segmented.
* **Neither** is ready for unsupervised conflict or near-miss analysis.

---

## 2. Research question and objectives

* **Central question:** pedestrians and cyclists at K305: when and where? How well do the Newsense and Ouster systems capture them, and which is suitable for which application?
* **Objectives:** a fair, evidence-based comparison over 19 aspects (§18), including detection, classification, tracking, trajectory quality, coverage, movement patterns, interactions, data quality and practical usability. The result must be understandable to non-specialists.
* **Principles** (`stage4_traffic_analysis/COMPARISON_FRAMEWORK.md` v2):
  * identical definitions, common period and common region
  * agreement is not accuracy
  * every count has a stated unit
  * smoothness is not accuracy
  * every problem goes in the register, regardless of which sensor it hurts

## 3. Dataset

Stage 1 / 2 / 2B.

* **Size:** 2,197 data files, 47.90 GB. Integrity was verified by SHA-256, and all files match the Google Drive originals.
* **Newsense:**
  * object lists at 10 Hz, 28 and 29 Oct (gaps 28 Oct 13:10–15:29 and 16:45–19:44)
  * counting zones 1–23, environment and visibility streams
  * analysed: 06:00–13:00 on both days
* **Ouster:**
  * object logs for 29 Oct 07:11:44–08:34:59 only (84 min), 10 Hz
  * 4 × 10-minute PCAP captures
  * configuration files (extrinsics, event zones)
* **MioVision video:** cameras SCU3K2 (used) and SCU4YV (excluded: unresolved clock).
* **Signals:** VRS5000 export, 1 s rows, with signal states and detector occupancy.
* **Not available:**
  * an official intersection map (GE-01)
  * Newsense system documentation
  * Ouster world-frame compass convention
  * signal-export conventions (SG-01)

## 4. Sensor descriptions (as far as the data documents them)

| | Newsense | Ouster |
|---|---|---|
| Output | Object list: id, class (Car/Van/Truck/Bus/Motorcycle/Pedestrian/Cyclist), 3D box, velocity, score | Object list: id, class (VEHICLE/LARGE_VEHICLE/PERSON/BICYCLE/UNKNOWN), position, dimensions, velocity, update time (coasting visible); raw PCAP |
| Sensor technology / position | **Not documented in the dataset.** Frame origin estimated at Ouster-world (−18.1, 4.6) m. | Sensor id 992519001027 at Ouster-world (−13.8, 5.7) m (extrinsics); mounting height 4.55 m (config); host clock, no PTP/GPS |
| Detection range observed | ~40–47 m (sharp edge; possibly configured) | to ~97 m |
| Documentation | none (frame, units, zones inferred) | partial (configs, vendor fields) |

No vendor specification was used, and none is claimed.

## 5. Geometry and coordinate systems

Checkpoint C1.

* Both frames are in metres.
* Newsense → Ouster transform: rotation 171.395°, translation (−18.110, 4.567) m, scale 0.99958, no mirror. Median residual 0.15 m [M].
* All comparisons use Ouster-world metres.
* **North is unverified and no map exists**, so the report uses no compass directions or street names.
* **Common region:** cells covered by both sensors, 2,780 m² (VRU-specific 1,144 m²). Results outside it are coverage findings, not performance.
* **Coverage (correction CC-13):** C1 §9 item 7 ("Ouster coverage is smaller than Newsense's") is withdrawn by the versioned note `checkpoint1_geometry/C1_CORRECTION_NOTE_01_coverage.md`. Its 22 % measures where stationary Newsense vehicles lie (unmatched, in cells without Ouster vehicle-class detections), not footprint area. Ouster's detection footprint is 3.5× larger (2.3–4.8× depending on definition). Whether the local stationary Newsense vehicles that Ouster does not report as vehicles are real is unresolved.

## 6. Clock and timing limitations

Stage 3, C2, C2 audit.

* Newsense, Ouster and the signal export agree within ±1 s (Newsense) and ±1.5 s (Ouster) [M].
* The SCU3K2 video clock lags by about 51 s with a −13.3 ppm drift. It is modelled in `clock_model_v2.json` (approved; **unchanged**).
* **CK-01:** for the same motion, both sensors' timestamps are **2.81 s** (sample sd 0.12 s) later than the video-derived reference.
  * This is robust to three different video registrations and to both travel directions [M].
  * The proposed explanation, "the signal export's detector columns lag its state columns", is **not supported** (loop release 4–5 s).
  * The cause is open.
* **Consequences:**
  * The +2.81 s is used only for looking up video frames.
  * Sensor ↔ signal timing stays at ±1–1.5 s, so **no signal-violation or phase-specific conflict analysis is possible**.
* **Decisive test proposed:** start-up after a *visible* green light measured entirely in video, compared with sensor start-up after the export's green.

## 7. Detection comparison

Sources: C2, C2 audit, CORR-01. Figures F06, F07.

* **Agreement** (class-agnostic matching within 2 m, same frames, 47,297 frame pairs):

  | Group | Newsense observations confirmed by Ouster | Ouster observations confirmed by Newsense |
  |---|---|---|
  | Pedestrians | 29.7 % | 72.1 % |
  | Cyclists | 47.6 % | 69.9 % |
  | Vehicles | 64.8 % | 59.0 % |

  Varying the gate (1–3 m) and offset changes these by ≤ 3 pp [M].
* **The pedestrian count ratio depends on the unit** (F06):

  | Unit | Newsense / Ouster |
  |---|---|
  | Observations | 2.53 |
  | Moving observations (> 0.5 m/s) | 0.80 |
  | Observations outside 10 hotspots | 1.15 |
  | Moving tracks | 0.91 |
  | **Robust moving path** | **0.67** (9.5 vs 14.2 km) |

  The observation ratio at > 0.3 m/s (1.12) is not used as a movement measure: it includes slow speeds produced by Newsense position jitter (CORR-01). Movement-based measures give 0.67–0.91.

* **Cyclists:** robust moving path 10.6 vs 10.2 km (1.04×) **only when Newsense Motorcycle is counted as cyclist** (6.5 + 4.1 km). The Cyclist label alone gives 6.5 vs 10.2 km (**0.64×**). Pedestrians and cyclists together give 20.1 vs 24.3 km (0.83×), or 0.62× if Ouster UNKNOWN movement is added.
* **Vehicles:** 113.8 vs 126.3 km (0.90×).
* **Interpretation.** Newsense reports far more pedestrian *observations* but less pedestrian *movement*. The surplus is stationary objects at fixed points. Where both detect an object, they agree. The video (§15) shows each sensor misses some real moving pedestrians that the other sees. **Detection rates against ground truth could not be estimated** [U].

## 8. Classification comparison

* **Vehicle vs non-vehicle:** 98.8 % / 99.0 % agreement *given that both detected the object* [M]. Subclasses agree less: Newsense Bus/Truck ↔ Ouster LARGE_VEHICLE only 54 %.
* **Pedestrian vs cyclist** (matched pairs):
  * Newsense Pedestrian → Ouster PERSON 76 %
  * Newsense Cyclist → Ouster PERSON 39 % and BICYCLE 46 %
  * Newsense Motorcycle → Ouster BICYCLE 63 % [M]
* **Double labels:** Newsense reports one road user as two classes at once (Cyclist+Pedestrian, Cyclist+Motorcycle). There are 628 persistent pairs, vs 1 for Ouster [M].
* **Ouster UNKNOWN:** 10.4 % of observations in the region. 73 % of Ouster pedestrian tracks *start* as UNKNOWN before becoming PERSON, so per-observation Ouster counts under-count persons at track starts [M].
* **Video:** only 1 of 17 class-conflict tiles was decidable (two cyclists; the Newsense label was right). **Who is right on pedestrian vs cyclist is unresolved** [I].

## 9. Track-level comparison

Source: C3 v2. Figures F08, F09, F10.

| Measure (common region unless stated) | Newsense | Ouster |
|---|---|---|
| Median track duration, pedestrian / cyclist / vehicle (s) | 4.7 / 4.6 / 6.4 | 9.3 / 9.7 / 8.7 |
| Moving-track breaks with nearby continuation per robust km (T = 2 s), pedestrian / cyclist (NS incl. Motorcycle) / vehicle | 33.4 / 28.5 / 5.7 | 20.8 / 9.1 / 1.7 |
| Moving vehicle tracks starting inside the area | 21 % | 1.5 % |
| IDs reused for another object (of which after > 60 s) / instantaneous swaps (own coverage) | 639 (636) / 59 | 0 / 0 |
| Same ID re-attached after a 5–30 s loss (Ouster re-find flag; same object not verified) | 0 (the 2 events of this length are reused IDs) | 359 |
| Label changes within a track | never (new ID instead) | 75 % of pedestrian tracks |
| Predicted (coasted) samples flagged | not available | 2.2 % pedestrians, 19 % UNKNOWN (region) |

* The earlier "ID reuse 766 vs 176" mixed these different phenomena. It is replaced by the table above (AN-03).
* Break rates use a stitching *analysis*. Nothing was joined. Windows of 1–3 s give the same ranking.
* **Corrected in V2 (CORR-02):** the cyclist rate is 28.5 per robust km with Cyclist + Motorcycle in both links and km, or 33.9 for the Cyclist label alone (V1: 20.9, from a mismatched numerator and denominator).
* Ratios depend on how Ouster UNKNOWN fragments are attributed (pedestrians 1.2–1.9×, vehicles 2.0–3.4×); the ranking does not.

## 10. Trajectory quality

Figures F11, F12; C2 audit, C3, C4.

| Measure | Newsense | Ouster |
|---|---|---|
| Pedestrian tracks with a position jump: > 12 m/s & > 1 m / > 2 m / > 3 m | 0 / 0 / 0 % | 22.2 / 6.2 / 1.4 % |
| Jumps involving a predicted sample | — | 32 % |
| Jitter of stationary objects (vehicles / pedestrians, RMS) | 3.0 / 2.4 cm | 4.7 / 6.1 cm |
| Speed-signal noise while moving (pedestrians / cyclists / vehicles) | 0.77 / 1.33 / 1.46 m/s² | 0.58 / 0.79 / 0.81 m/s² |
| Velocity at track start | 0 for about 0.5 s (artefact) | normal |

* **Reading:** Newsense positions are smoother; Ouster speeds are smoother. Ouster's large jumps occurred inside groups of road users (video 2/2), which suggests re-association between neighbours (hypothesis).
* **No accuracy statement is possible.** Where both sensors detect an object, positions differ by a median 0.10–0.16 m and pedestrian speeds by about ±0.4 m/s (p5–p95).

## 11. Spatial and temporal behaviour

C5/C6. Figures F01–F05, F16, F17.

* **Where:**
  * Both sensors show the same movement corridors: two diagonal crossing corridors plus paths along the approach legs. These coincide with the Ouster-configured crosswalk polygons, which are configured rather than surveyed.
  * Ouster follows them much farther out.
* **Blind-spot candidates:**
  * In 321 common-region cells, 59 % show similar amounts of moving pedestrian and cyclist path.
  * Ouster dominates at the outer edge, near Newsense's range limit.
  * Newsense dominates near the sensor masts, which may be a near-field blind or occluded zone for Ouster. That area overlaps a Newsense hotspot, so this is unresolved [I].
* **Waiting:**
  * Ouster's stationary pedestrians sit at the corridor ends (plausible waiting areas).
  * Newsense's stationary "pedestrians" (4× more pedestrian-seconds) form compact blobs at fixed objects. They cannot be read as waiting behaviour.
* **When** (Newsense only; Ouster has 84 min):
  * moving pedestrian and cyclist activity peaks at **07:30–07:45 on both days**, at about 3× the late-morning level
  * daily totals agree within 5 % between days
  * Newsense pedestrian/cyclist counting zones also peak at 07:00–08:00
  * the static-hotspot level is **2.4× higher on 29 Oct**, consistent with a configuration change (score field also changed)
* **No compass directions or origin–destination matrix per leg is given**, because the leg geometry is unverified.

## 12. Pedestrian and cyclist analysis (synthesis)

| | Pedestrians | Cyclists |
|---|---|---|
| Amount of movement captured (robust path, NS vs OU) | 9.5 vs 14.2 km: Ouster more | 10.6 vs 10.2 km (similar) only with NS Motorcycle included; Cyclist label alone 6.5 vs 10.2 km (0.64×) |
| Static false objects | Newsense many (signal pole and others) | Newsense some (Cyclist/Motorcycle at hotspots) |
| Track continuity | Ouster better (breaks 20.8 vs 33.4 per km) | Ouster better (9.1 vs 28.5) |
| Classification | Both problematic; the boundary with cyclists differs | Both problematic |
| Daily patterns | Newsense only | Newsense only |

## 13. Vehicle interactions

C7 v2. Figures F13, F14.

* **Surrogate indicators** computed with identical rules (TTC, PET with paths crossing at ≥ 30°, proximity; moving vs stationary VRU).
* **Moving pedestrians and cyclists:**

  | Indicator | Newsense | Ouster |
  |---|---|---|
  | TTC < 3 s | 296 | 291 |
  | TTC < 1.5 s | 31 | 35 |
  | PET < 2 s (crossing) | 12 | 19 |
  | Distance < 3 m | 15 | 17 |

* **Stationary pedestrians and cyclists:** TTC < 3 s **789 vs 193**. 388 of the Newsense ones (49 %) lie at the 10 known static hotspots (for example vehicles passing the signal pole). The others, and Ouster's, are not shown to be spurious and may include real waiting pedestrians.
* **Large vehicles:** 5 (Newsense) and 5 (Ouster) severe TTC events involved trucks or buses.
* **Correction AN-07:** PET v1 also counted same-direction following, which inflated Ouster cyclist events (85 → 19). It is corrected in v2, and v1 is kept.

## 14. Potential conflict analysis

* **Agreement between sensors on severe events is low.** For each severe moving-VRU event of one sensor:
  * the other sensor has an event of the same kind at **any level** (TTC < 3 s, PET < 3 s) within 2 s and 5 m: TTC 7/31 (23 %) and 4/35 (11 %); PET 5/12 (42 %) and 5/19 (26 %); proximity 3/15 (20 %) and 1/17 (6 %)
  * the other sensor's event is **also severe** (TTC < 1.5 s, PET < 2 s): TTC 1/31 and 1/35 (3 %); PET 4/12 and 4/19
* A single-sensor conflict list is therefore **not reproducible** with the other sensor.
* Video: a VRU is visible at 5 of 9 decidable candidate positions. **No near-miss is confirmed**, because single frames cannot show it.
* Braking proxies are rare (2 and 5 events) and unreliable given the speed noise.
* **Not possible:** signal-phase context (CK-01, SG-01), turning movements and stop-line crossings (GE-01).

## 15. Video validation

C2, C2 audit, round 2. Figures F19–F23. **All labelling was done by a single rater.** No second rater took part.

* **Round 1** (C2, detection-weighted):
  * Newsense-only 0/12, Ouster-only 0/12, agreed 8/12 persons confirmed
  * most tiles were undecidable
* **Round 2** (stratified, track-level):
  * Newsense-only 2/11 (2 of 5 decidable)
  * Ouster-only 3/8 (3 of 4 decidable)
  * **agreed 0/12**, so the video cannot confirm even jointly detected pedestrians in most of the view
  * hotspots: the signal pole was re-confirmed (no person); the neighbouring hotspots showed no person in 4 decidable frames
* **Conclusion:**
  * The available camera supports **case checks**: the signal-pole ghost; real persons missed by the other sensor; jumps inside groups.
  * It does **not** support detection or false-positive rates [I].
* **Needed:** short clips, near-field strata, two or more raters, a better or additional camera.

## 16. Data quality and reliability

Final register (v4): 56 entries.

| Source | Entries | Open |
|---|---|---|
| Newsense | 16 | 6 |
| Ouster | 18 | 9 |
| Shared / methodology | 22 | 8 |

* **Newsense:** gaps on 28 Oct; no documentation; range limit; static false pedestrians; double labels; fragmentation; ID recycling; score semantics changed between days; velocity starts at 0; indicator events from static false objects. Only 2 dropped frames in the common period.
* **Ouster:** only 84 minutes; 4.9 % dropped frames and two 7.5 s gaps; a processing alert at 07:16–07:17; UNKNOWN class; label switching; position jumps; predictions (flagged); compass convention undocumented.
* **Shared:** no map; signal-export conventions; video clock; CK-01; plus methodological items AN-01–09, including the corrections made during this work (CORR-01, AN-07) and from the final-package audit (CORR-02 / AN-10, AN-11, AN-12; AN-13 precision; AN-14 audit independence).

## 17. Limitations and uncertainties

See `FINAL_LIMITATIONS_AND_UNCERTAINTIES.md`. In brief:

* 83 minutes of overlap, one morning, one site
* no ground truth
* a single hazy camera and a single rater
* no surveyed map
* timing open (CK-01)
* two sensors with different, undocumented processing chains

## 18. Final sensor comparison

Full table: `FINAL_SENSOR_COMPARISON.csv` (30 metrics, each with method, sample size, uncertainty, fairness and source).

**Scorecard by aspect.** The aspects are not combined into an overall score.

| # | Aspect | Leans to | Evidence | Note |
|---|---|---|---|---|
| 1 | Detection performance (general) | Unresolved | [M] agreement only | Each misses some objects the other sees |
| 2 | Object classification (vehicle vs non-vehicle) | Similar | [M] | Subclasses weaker in both |
| 3 | Pedestrian detection | **Ouster** (moving pedestrians); Newsense surplus is static | [M] + [I] | No detection rate measurable |
| 4 | Cyclist detection | Depends on label mapping | [M] | Similar movement only if NS Motorcycle counts as cyclist (1.04×); Cyclist label alone 0.64×; pedestrians + cyclists combined 0.83× |
| 5 | Pedestrian vs cyclist classification | Unresolved; Newsense double labels | [M] | Video undecidable |
| 6 | Tracking ID reliability | **Ouster** | [M] | Newsense recycles IDs |
| 7 | Fragmentation and ID reuse | **Ouster** | [M] | Stitching analysis; size depends on Ouster UNKNOWN attribution |
| 8 | Trajectory completeness | **Ouster** | [M] | Longer tracks, larger area |
| 8b | Trajectory smoothness | Split: Newsense positions, Ouster speeds | [M] | Not accuracy |
| 9 | Position accuracy | Not comparable | [U] | Precision proxy: Newsense steadier |
| 10 | Velocity estimation | Not comparable (accuracy) | [U] | Ouster steadier; Newsense start artefact |
| 11 | Spatial coverage | **Ouster** | [M] | Near-mast zone unresolved |
| 12 | Temporal coverage / availability | **Newsense** (in this dataset) | Fact | Deployment difference |
| 13 | VRU movement patterns | Ouster spatially; Newsense temporally | [M] | — |
| 14 | Traffic density and distribution | Ouster (area); Newsense (time) | [M] | Newsense density inflated by static objects |
| 15 | VRU–vehicle interactions | Similar counts; low agreement | [M] | — |
| 16 | Conflicts / near-misses | Neither ready | [M]/[I] | Video confirmation needed |
| 17 | Data quality / reliability | Mixed: Ouster more transparent; Newsense more continuous | [M] | — |
| 18 | Technical limitations / processing | Ouster (documentation, flags) | Fact | Newsense needs ID segmentation and static filtering |
| 19 | Suitability for traffic-safety research | Ouster for trajectory work; neither alone for conflicts | Synthesis | See §19 |

## 19. Recommendations

| Question | Answer | Confidence |
|---|---|---|
| Which is more suitable for pedestrian detection? | **Ouster** for moving pedestrians (more movement captured, more continuous tracks, no static false pedestrians). Newsense's raw pedestrian counts are unusable without removing stationary detections. | Medium (no ground truth) |
| Which is more suitable for cyclist detection? | **Not decidable from movement alone:** similar only if Newsense Motorcycle is counted as cyclist (1.04×); the Cyclist label alone gives 0.64×. Both have pedestrian/cyclist label problems. Ouster tracks are more continuous (breaks 9.1 vs 28.5 per km). | Low–medium |
| Which provides better tracking? | **Ouster**: no ID recycling, fewer breaks, longer tracks, IDs re-attached after short losses (same object not verified) | Medium–high |
| Which provides more useful trajectories? | **Ouster** for paths and speeds (longer, steadier speeds, coasting flagged); filter or flag its 1–2 m jumps. Newsense trajectories are smooth but short and fragmented. | Medium |
| Which has better spatial coverage? | **Ouster** (3.5× area) | High |
| Which is more suitable for traffic-safety research? | **Neither alone.** Ouster is the better trajectory basis, but candidate conflicts from either sensor must be video-confirmed. Newsense's static objects inflate conflict-indicator counts. | Medium |
| Main limitations | Newsense: static false pedestrians, ID recycling, fragmentation, double labels, limited range, no documentation. Ouster: short data period, dropped frames and gaps, UNKNOWN class, label switches, 1–2 m jumps in groups. | — |
| When is each preferable? | **Newsense:** long-term counting and time-of-day patterns of moving road users near its position, once stationary detections are removed and IDs segmented. **Ouster:** trajectory, path-choice, crossing and interaction studies over the whole junction. | Medium |
| What could not be answered | Absolute accuracy; true detection and false-positive rates; who is right on pedestrian vs cyclist; signal-related behaviour; confirmed near-misses | — |

**Next steps that would raise confidence most:**

1. Clip-based video review with two raters of the 66 severe TTC candidates and the 31 severe PET candidates, plus a stratified near-field sample.
2. The CK-01 decisive timing test.
3. An official map.
4. A longer simultaneous recording, with Ouster running for at least several hours.
5. Newsense documentation (range setting, filtering, ID policy).

## 20. References and technical documentation

**Project documents** (all under `~/Downloads/K305_Analysis_Outputs/`):

* `stage1_inventory_review/STAGE1_inventory_review.md`
* `stage2_integrity/`, `stage2_archive_verification/STAGE2B_archive_verification_report.md`
* `stage3_clock_assessment/STAGE3_corrected_clock_assessment.md`, `v2/clock_model_v2.json`
* `stage4_traffic_analysis/checkpoint1_geometry/C1_geometry_validation_report.md` and `C1_CORRECTION_NOTE_01_coverage.md` (V2)
* `stage4_traffic_analysis/checkpoint2_sensor_validation/C2_sensor_validation_report.md`, `comparison_dataset_specification.md`
* `stage4_traffic_analysis/checkpoint2_audit/C2_INDEPENDENT_AUDIT_REPORT.md`, `C2_AUDIT_ACCEPTANCE_AND_CHANGELOG.md`
* `stage4_traffic_analysis/checkpoint3_tracks/C3_track_level_comparison_report_v3.md` (current; v2 = `C3_track_level_comparison_report.md`; v1 kept)
* `stage4_traffic_analysis/checkpoint4_position_velocity/C4_position_velocity_note.md`
* `stage4_traffic_analysis/checkpoint5_spatial_temporal/C5_C6_spatial_temporal_report.md`
* `stage4_traffic_analysis/checkpoint7_interactions/C7_interactions_conflict_indicators_report_v3.md` (current; previous version kept)
* `stage4_traffic_analysis/checkpoint_video2/VIDEO_VALIDATION_ROUND2_report.md`
* `stage4_traffic_analysis/corrections/CORR-01_total_path_length_v2.md` (v1 kept), `CORR-02_cyclist_break_rate.md`
* `stage4_traffic_analysis/final_audit/` (final-package audit: report, confirmed corrections, unresolved issues, reproduction table)
* In this V2 folder: `FINAL_ISSUE_AND_CORRECTION_REGISTER.md`, `FINAL_SENSOR_COMPARISON.csv`, `FINAL_VALIDATION_SUMMARY.md`, `FINAL_LIMITATIONS_AND_UNCERTAINTIES.md`, `V2_CHANGE_LOG.md`, `V2_VALIDATION_REPORT.md`

**Method notes:**

* TTC, PET and proximity are standard surrogate safety indicators. Here they are used only as candidate flags with stated thresholds.
* Clopper–Pearson exact intervals are used for video proportions.

**No external literature was consulted during this run, and no literature values are cited.** The physical priors used in the timing audit (typical start-up delays) are explicitly labelled as assumptions.
