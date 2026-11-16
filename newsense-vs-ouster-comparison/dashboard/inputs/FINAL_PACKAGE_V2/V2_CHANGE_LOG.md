# Final package V2: change log

* **Date:** 2026-11-14
* **Basis:** the final-package audit, `stage4_traffic_analysis/final_audit/` (`FINAL_PACKAGE_INDEPENDENT_AUDIT_REPORT.md`, `CONFIRMED_CORRECTIONS.md`).
* **All 13 confirmed corrections are applied.**
* **V1 is unchanged.** It stays in `~/Downloads/K305_Analysis_Outputs/`: the `FINAL_*` files, `K305_Newsense_vs_Ouster_Final_Presentation.pptx` and `final_figures/`. This is verified by SHA-256 against `stage4_traffic_analysis/final_v2/V1_PACKAGE_MANIFEST.sha256` (see `V2_VALIDATION_REPORT.md`).
* **`clock_model_v2.json` is unchanged.**
* **No unresolved issue was turned into a finding.** The open items are listed in `stage4_traffic_analysis/final_audit/UNRESOLVED_ISSUES.md` and remain open in register v4.
* **Status of the evidence:** the audit re-implemented the key calculations from the raw data, but it was done by the **same analyst**. It is not an independent external review, and the package is **not** fully scientifically validated (AN-14).

**Rebuild:** `zsh stage4_traffic_analysis/final_v2/build_v2_all.sh`.

* All text edits are made by `final_v2/apply_v2_text_corrections.py`. Each edit must match its source text exactly once, or the script stops. The edits are logged in `final_v2/v2_text_edit_log.csv`.
* The figures are built by `final_v2/build_v2_figures.py`, the table by `final_v2/build_final_comparison_v2.py`, and the deck by `final_v2/build_pptx_v2.py`.

## Corrections

| ID | Correction | Evidence | Affected files (V2 and versioned checkpoint files) | Impact on conclusions |
|---|---|---|---|---|
| **CC-03** (calculation error) | Newsense cyclist breaks per robust km. V1 divided Cyclist-only links by Cyclist + Motorcycle km (20.9). V2 uses the same classes on both sides: **28.5** (Cyclist + Motorcycle) and **33.9** (Cyclist only) vs Ouster 9.1. T = 1 / 3 s: 19.1 / 31.3 and 23.0 / 36.7. | New `corrections/corr02_cyclist_break_rate.py` → `corr02_breaks_per_robust_km.json`, from the same inputs as CORR-01. Raw re-implementation (audit `fa6`) gives 28.3 / 33.5 / 8.9, within 1 %. | F09 (regenerated); slides 9 and 18; report §1, §9, §12, §19; CSV fragmentation row; register NS-12 and new AN-10; `corrections/CORR-02_cyclist_break_rate.md` (new); `CORR-01_total_path_length_v2.md`; `C3_track_level_comparison_report_v3.md` | Direction unchanged (Newsense fragments more). The cyclist difference is **larger** than stated: 3.1–3.7× instead of 2.3×. |
| **CC-04** | Cyclist robust path 1.04× holds only when Newsense Motorcycle is counted as cyclist. The Cyclist label alone gives **0.64×**; pedestrians + cyclists combined give 0.83× (0.62× with Ouster UNKNOWN). | `corr02_breaks_per_robust_km.json` (robust km: NS Cyclist 6.51, Motorcycle 4.07; OU 10.16); audit `fa4` | F07 (regenerated, both definitions); slide 15 scorecard ("Depends on label mapping"); report §7, §12, §18 (aspect 4), §19; CSV cyclist row and new combined-VRU row; register AN-06; CORR-01 v2; C3 v3 | "Cyclist detection: similar" becomes **depends on label mapping**. The claim is weakened, not reversed. Combined VRU movement is higher in Ouster. |
| **CC-05** | Fragmentation magnitudes are ranges, not fixed values. V1's "1.6× to 3×" conflicted with C3 v2's "2–2.7×, 2.5–4×". The size depends on how Ouster UNKNOWN fragments are attributed: pedestrians 1.2–1.9×, vehicles 2.0–3.4×; cyclists 3.1–3.7× (CORR-02). | Audit `fa6_fragmentation.json` (176 UNKNOWN→PERSON and 133 PERSON→UNKNOWN links at T = 2 s) | Report §1, §9, §18 (aspect 7); slide 9; CSV interpretation; limitations #14; C3 v3; CORR-01 v2; register NS-12 | Direction confirmed in every variant; sizes reported as ranges. |
| **CC-06** | C3 v2 still contained the withdrawn wording "NS-12: … pedestrians similar to Ouster". | Direct reading | `C3_track_level_comparison_report_v3.md` | None (a stale line removed). |
| **CC-01** | ID events: "637 recycled (> 60 s)" was 636 after > 60 s plus 1 at 57.5 s. With the 2 shorter cases (CC-02), **639 ids** were reused for other objects. The recycled ids changed class in 85 % of cases, not 81 % (81 % is the share over all 671 Newsense gap events). The 59 hand-overs are simultaneous **swaps** between a vehicle and a cyclist. | `c3_reappearance_classes.json` (LONG 636, MID 1, SHORT 2); audit `fa5_ids.json` | F08 (regenerated); slide 8; report §1, §9; CSV id row; register NS-15, AN-03; C3 v3 | Wording only; the conclusion that Newsense recycles ids is unchanged. |
| **CC-02** | Newsense "2 re-acquisitions" are reused ids (25 m away, class changed). Newsense re-acquisitions: 0. | Audit `fa5_ids.json` | F08; report §9; CSV; C3 v3 | None. |
| **CC-07** | "Ouster re-acquired the same object 359 times" becomes "re-attached the id after a 5–30 s loss 359 times, each flagged by Ouster's own `refind_time` field". The same physical object is not verified (only 31 % same class within 5 m). Ouster also bridges about 1,400 shorter 1–5 s gaps. | Audit `fa5_ids.json` | Slide 8 (also the title: "keeps its IDs stable"); F08; report §1, §9, §19; CSV; register OU-18, AN-03; C3 v3 | Weaker identity claim. The conclusion that Ouster ids are stable (no recycling) is unchanged. |
| **CC-08** | TTC agreement now has two definitions. **Any level:** 11–23 % of severe moving-VRU TTC events have any TTC < 3 s event of the other sensor within 2 s and 5 m (7/31, 4/35). **Also severe:** only **1/31 and 1/35** are < 1.5 s in both. PET: 5/12 and 5/19 at any level; 4/12 and 4/19 also severe. | New `checkpoint7_interactions/scripts/c7_agreement_v3.py` → `c7_agreement_v3.json` (from the unchanged v2 events); audit `fa7` | F15 (regenerated with both definitions); slide 13; report §1, §14; CSV agreement row; register AN-08; limitations; `C7_interactions_conflict_indicators_report_v3.md` | Agreement on severity is about 3 %, so "sensor-specific conflict lists" is **strengthened**. |
| **CC-09** | Stationary-VRU events are no longer all called "spurious". TTC < 3 s with stationary VRU: 789 (Newsense) vs 193 (Ouster). **388 of the 789** lie in the 10 known Newsense ghost cells (393 with 0.1 m-rounded event positions); Ouster has 9 there. The rest are not shown to be spurious. The CSV verdict changed from "Ouster" to "Unresolved". | Audit `fa7_interactions.json` (full-precision positions); `c7_agreement_v3.json` | Slide 13; report §1, §13, §16, §19; CSV row renamed; register NS-16; C7 v3 | The claim is weakened: inflation is documented only at the hotspots. |
| **CC-10** | Slide 18: "Total pedestrian path 1.00× → 0.67×" mixed two measures. It now reads "Pedestrian movement: total path (1.00×) → robust moving path (0.67×)". "PET 85 → 19" is labelled Ouster (Newsense 20 → 12). A third card was added for the final audit. | CORR-01; AN-07 | Slide 18; outline | None. |
| **CC-11** | "66 severe candidates" are the TTC events only (31 + 35). The 31 severe PET candidates (12 + 19) are now named as well. | `c7_agreement_v2.py` definition of severe | Slide 19; report §19; register AN-08; outline; C7 v3 | None. |
| **CC-12** | F06 now includes the robust moving path (0.67×) as an eleventh definition. The > 0.3 m/s ratio (1.12) is labelled as including Newsense jitter speeds. Slide 6 text: movement measures 0.67–0.91×. | CORR-01 decomposition (NS 1.87 km at 0.3–0.5 m/s) | F06 (regenerated); slide 6; report §7; outline | Removes an apparent conflict between slides 5 and 6. |
| **CC-13** | C1 §9 item 7, "Ouster coverage is smaller than Newsense's", is withdrawn by a **versioned correction note**. The C1 report is not edited. The 22 % measures where stationary Newsense vehicles lie (unmatched, in cells without Ouster vehicle-class detections), not area. The footprint is 3.5× (2.3–4.8× by definition). | Audit `fa3b_c1c_stationary.json` (22.2 % reproduced; 14 % against the any-object footprint), `fa3_coverage.json` | `checkpoint1_geometry/C1_CORRECTION_NOTE_01_coverage.md` (new); report §5; CSV footprint row; register OU-12 and new AN-12 | No number changes. The local Newsense-only stationary vehicles remain **unresolved** (U-02). |

## Register, framework and log

| File | Change |
|---|---|
| `stage4_traffic_analysis/register/` | Regenerated as **v4** by `build_register_v4.py` with `register_additions_final_audit.py`. The v3 outputs (final package V1) are archived in `register/archive/register_v3_final_package_V1/`. |
| Register entries | 56 entries (V1: 51). **New:** AN-10 (CORR-02), AN-11 (V1 wording), AN-12 (C1 coverage), AN-13 (threshold and timestamp precision, documented), AN-14 (same-analyst audit, open). **Updated:** NS-12, NS-15, NS-16, OU-12, OU-18, AN-03, AN-06, AN-08. |
| Register status | Open 23, Mitigated 12, Documented 11, Corrected 10 |
| `FINAL_ISSUE_AND_CORRECTION_REGISTER.md` (this folder) | Copy of register v4 |
| `stage4_traffic_analysis/COMPARISON_FRAMEWORK.md` | Updated to **v3**: new "corrected interpretations after the final-package audit" table and status rows. v2 is archived in `register/archive/COMPARISON_FRAMEWORK_v2_final_package_V1.md`. |
| `PROGRESS_LOG.md` | One row appended. The pre-V2 copy is in `register/archive/PROGRESS_LOG_before_V2.md`. |
| Checkpoint reports | **New versioned files:** `C3_track_level_comparison_report_v3.md`, `C7_interactions_conflict_indicators_report_v3.md`, `CORR-01_total_path_length_v2.md`, `CORR-02_cyclist_break_rate.md`, `C1_CORRECTION_NOTE_01_coverage.md`. The earlier versions are not edited. |

## Files in V2

| File | Status vs V1 |
|---|---|
| `FINAL_RESEARCH_REPORT.md` | Corrected (header, §1, §5, §7, §9, §12–§14, §16, §18–§20) |
| `FINAL_SENSOR_COMPARISON.csv` | Rebuilt: 31 rows (one new combined-VRU row); id, cyclist, fragmentation, agreement, stationary-event and footprint rows corrected |
| `FINAL_ISSUE_AND_CORRECTION_REGISTER.md` | Register v4 |
| `FINAL_LIMITATIONS_AND_UNCERTAINTIES.md` | Rows 13–15 added; uncertainty table updated |
| `FINAL_PRESENTATION_OUTLINE.md` | Slides 2, 6, 8, 9, 13, 15, 18 and 19 updated |
| `FINAL_VALIDATION_SUMMARY.md` | §3 rows added; new §5 (audit) and §6 (V2 validation) |
| `FINAL_PROJECT_STATUS.md` | Rewritten for V2 |
| `K305_Newsense_vs_Ouster_Final_Presentation_V2.pptx` | 19 slides. Corrected: 1 (footer), 2, 6, 8, 9, 13, 15, 18 and 19. |
| `final_figures/` | 23 PNG. F06, F07, F08, F09 and F15 regenerated; the other 18 are copied unchanged from V1. |
| `figure_sources/` | SVG and PNG of the 5 regenerated figures |
| `V2_CHANGE_LOG.md`, `V2_VALIDATION_REPORT.md` | New |
