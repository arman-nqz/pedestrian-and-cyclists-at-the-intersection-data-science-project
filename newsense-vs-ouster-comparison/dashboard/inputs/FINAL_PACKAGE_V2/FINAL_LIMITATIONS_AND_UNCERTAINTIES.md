# Final limitations and uncertainties

Date: 2026-11-14 (final package V2; V1 of 2026-11-13 kept). Ordered by their effect on the conclusions.

| # | Limitation | Effect on conclusions | What would remove it | Register |
|---|---|---|---|---|
| 1 | **Only 83 minutes of simultaneous data** (one weekday morning, 29 Oct 07:12–08:35) | Every cross-sensor result is one short sample. Weather, light and demand variation are untested. Small event counts (for example 31 vs 35 severe TTC). | A longer simultaneous recording | OU-01 |
| 2 | **No ground truth** | Only agreement, steadiness and coverage are measurable. Detection rates, false-positive rates and position or speed accuracy are not. | Annotated video or a surveyed reference | AN-09, MV-03/04 |
| 3 | **Video reference is weak**: one camera, haze, far field, 20–60 px projection bias; single frames | Most tiles undecidable; even jointly detected pedestrians were unconfirmed in round 2 (0/12) | Clips, near-field sampling, a better camera, survey points | AN-01, AN-09, MV-04 |
| 4 | **Single rater** for all video labels (the analyst) | No inter-rater agreement; subjective calls on ambiguous tiles | A second independent rater and κ | AN-01 |
| 5 | **No official map, north unverified** | No compass directions, leg names, stop lines or crosswalk geometry; no origin–destination matrices; no stop-line or red-light analysis | Official map | GE-01, OU-07 |
| 6 | **Timing inconsistency CK-01** (2.81 s video ↔ sensors, cause unknown); sensor ↔ signal ±1–1.5 s | No phase-specific behaviour or conflict analysis. Video look-ups rely on an empirical offset. | Decisive video start-up test; export documentation | CK-01, SG-01 |
| 7 | **Undocumented processing in both sensors** (filtering, ID policy, Newsense range) | Smoothness, fragmentation and coverage differences may reflect settings, not hardware | Vendor documentation and configuration | NS-05, NS-07, OU-07 |
| 8 | **Newsense configuration apparently changed between days** (score semantics, hotspot level 2.4×) | Newsense static artefacts cannot be corrected with a fixed rule; two-day patterns of *stationary* pedestrians are not comparable | Vendor change log | NS-09, NS-13 |
| 9 | **Class taxonomies differ** (no Ouster motorcycle; Ouster UNKNOWN) | Coarse groups only; Newsense Motorcycle excluded from interaction analysis | — | NS-08 |
| 10 | **Common region is small** (2,780 m²; VRU part 1,144 m²) and bounded by Newsense's range | Ouster's far-field quality is not cross-checked | Second reference sensor or video covering the far field | OU-12 |
| 11 | **Method choices**: matching gate, jump thresholds, stitching window, TTC/PET thresholds, crossing angle, robust-path rule | Values shift; sensitivity is reported for each, and rankings were stable except where stated | — | AN-02, AN-05, AN-06, AN-07 |
| 12 | **Ouster data gaps** (4.9 % missing frames, two 7.5 s gaps, alert 07:16–07:17) | Masked for both sensors; small loss of data | — | OU-02, OU-03 |
| 13 | **Audit independence**: the final-package audit re-implemented key results from raw data, but it was done by the same analyst; several results were not re-implemented | Shared conceptual errors could survive; the package is not fully scientifically validated | External review re-running the scripts | AN-14 |
| 14 | **Class attribution of Ouster UNKNOWN fragments** | Fragmentation ratios are ranges (pedestrians 1.2–1.9×), not single values | Labelled sample of UNKNOWN↔PERSON continuations | NS-12, AN-10 |
| 15 | **Threshold ties and timestamp rounding** (0.1 s sampling) | ±1 event in PET and re-attachment counts; about 1 % in robust path | Thresholds off the sampling grid | AN-13 |

## Uncertainty statements per main conclusion

| Conclusion | Main uncertainty |
|---|---|
| The Newsense pedestrian surplus is static false objects | Only 1 hotspot is fully video-confirmed; waiting pedestrians are mixed in |
| Ouster captures more moving-pedestrian movement (0.67×) | Ouster could include merged or fragmented moving objects; no ground truth |
| Ouster tracks are more continuous | Stitching rules are approximate; Ouster may merge people in groups; magnitude depends on UNKNOWN attribution (pedestrians 1.2–1.9×) |
| Classification problems in both | Who is right is unknown; the cyclist movement comparison depends on whether Newsense Motorcycle counts as cyclist (1.04× vs 0.64×) |
| Conflict events are sensor-specific | Small numbers; agreement window choices; agreement on severity is only 1/31 and 1/35 (TTC) |
| Newsense time-of-day peak at 07:30–07:45 | One sensor, two days |
