# Unresolved issues after the final-package audit (2026-11-14)

These cannot be settled with the available data or were outside what this audit reproduced. Nothing here is classified as an error or a false positive.

| ID | Issue | Why it is open | What would resolve it |
|---|---|---|---|
| U-01 | **Which sensor's moving-pedestrian path is closer to reality** (NS/OU 0.60–0.72) | <ul><li>No ground truth.</li><li>Ouster could over-count (1–2 m jumps, merged groups); a jump cap changes little (0.70).</li><li>Newsense could under-count (range edge, fragmentation).</li></ul> | Surveyed reference trajectories, or clip-based manual tracking of a sample of pedestrians in both sensors |
| U-02 | **Newsense-only stationary vehicles** in three cells around (−27…−25, 25) and (−29, 33), 30–40 m from the Ouster sensor | Could be occlusion or a blind spot of Ouster, or Newsense false objects. They are outside the usable camera view. | Field check or a camera covering that area. The official map would show whether these are parking or queue positions. |
| U-03 | **Size of the fragmentation difference** (pedestrians 1.2–1.9×, VRU 1.2–1.9×, vehicles 2.0–3.3×) | It depends on whether Ouster UNKNOWN fragments belong to pedestrians or vehicles; neither is observable | A labelled sample of UNKNOWN→PERSON link pairs (video clips) |
| U-04 | **Whether Ouster's 359 re-finds are the same physical object** | Vendor flag only; 31 % same group within 5 m | Clip review of a sample of re-find events |
| U-05 | **Newsense id policy** (re-issues older id numbers; vehicle↔cyclist id swaps) | No Newsense documentation | Vendor documentation |
| U-06 | **Reality of all conflict candidates**; which sensor's severe events are real | Agreement on severity is about 3 %; single-frame video cannot show near-misses | Two-rater clip review of the 66 TTC and 31 PET severe candidates |
| U-07 | **Share of the 789 / 193 stationary-VRU TTC events that are real waiting pedestrians** | Only one hotspot is video-confirmed as static | Clip review stratified by hotspot and non-hotspot cells |
| U-08 | **Sensitivity of threshold-based counts to timestamp precision** (± 1 events, about 1 % path) | Inherent to 10 Hz sampling | Report thresholds off the sampling grid in future versions |
| U-09 | **Results not reproduced by this audit** | Outside the requested scope or not recomputable without new labelling: <ul><li>C2 matching percentages (29.7 / 72.1 / 47.6 / 69.9 / 64.8 / 59.0 %)</li><li>classification confusion (39 %, 54 %)</li><li>628 double-label pairs</li><li>track durations (4.7 / 9.3 s)</li><li>jump shares</li><li>C4 jitter</li><li>speed noise</li><li>C5/C6 maps and time-of-day</li><li>all video labels</li><li>CK-01 timing</li></ul> | A further re-implementation pass, or review by a second analyst |
| U-10 | **Independence of this audit** | Written by the same analyst (Claude) as the original analysis. It re-implements from raw data, but shared conceptual errors could survive. | A human or second-party reviewer re-running `final_audit/scripts/fa1`–`fa7` and the original scripts |
| U-11 | **PPTX not opened in PowerPoint** (carried over) | No PowerPoint in this environment | Open the deck and check for a repair prompt |
| U-12 | **Open items carried over from the final register** | Unchanged by this audit: <ul><li>no second rater</li><li>CK-01 cause</li><li>no official map (GE-01)</li><li>signal-export conventions (SG-01)</li><li>Ouster far-range quality (OU-12)</li></ul> | As listed in `FINAL_LIMITATIONS_AND_UNCERTAINTIES.md` |
