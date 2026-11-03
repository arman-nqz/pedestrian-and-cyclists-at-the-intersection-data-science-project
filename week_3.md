# Week 3 Progress Report

## Pedestrians and Cyclists at the Intersection — When and Where?

**Dataset:** K305 intersection
**Observation date:** 14 October 2026
**Project stage:** Extended analysis and visualisation of full-day results

### 1. Objective

The objective of this week's work was to extend the analysis of the existing full-day intersection data and make the detected interaction patterns easier to interpret through statistical summaries and visualisations.

The work focused on processing existing event CSV files rather than rerunning the computationally expensive detection pipeline.

### 2. Work Completed

The following work was completed:

1. Developed a separate Python script, `analyze_full_day_results.py`, to analyse existing full-day event results.
2. Summarised consolidated Time-to-Collision (TTC) events by interaction type.
3. Calculated descriptive TTC statistics, including the median, mean, minimum, and quartiles.
4. Generated a summary of TTC events by hour.
5. Created a TTC comparison visualisation for different road-user combinations.
6. Created a graph showing hourly interaction patterns.
7. Created a spatial visualisation of detected interactions.
8. Generated a Markdown findings report documenting the results and methodological limitations.

### 3. Results

The existing full-day results contain 2,583 consolidated TTC events.

The five most frequent interaction types were:

| Interaction type     | Event count | Share of TTC events |
| -------------------- | ----------: | ------------------: |
| Car vs. Pedestrian   |       1,024 |              39.64% |
| Cyclist vs. Car      |         760 |              29.42% |
| Truck vs. Pedestrian |         212 |               8.21% |
| Bus vs. Pedestrian   |         175 |               6.78% |
| Van vs. Pedestrian   |         145 |               5.61% |

Car–pedestrian and cyclist–car interactions together account for approximately 69.1% of the consolidated TTC events.

The median minimum TTC across the detected events was approximately 0.567 seconds, and the mean was approximately 0.637 seconds.

The hourly results showed the largest event counts at 07:00, 13:00, and 16:00, with 300, 295, and 286 events respectively.

The existing PET-proxy event file contained 22,192 recorded events. The median PET-proxy value was approximately 1.100 seconds.

### 4. Visualisations Produced

Three additional visualisations were generated:

* `ttc_by_interaction_type.png` — compares TTC distributions across interaction types.
* `hourly_interactions.png` — illustrates how consolidated TTC event counts vary by hour.
* `spatial_hotspots.png` — visualises the spatial distribution of detected events.

These visualisations provide complementary perspectives on the detected interactions: interaction type, time of occurrence, and spatial concentration.

### 5. Methodological Limitations

The results require cautious interpretation:

* TTC events are algorithm-generated candidate interactions, not confirmed collisions.
* PET is based on a 2-metre grid-cell occupancy proxy and is not a definitive engineering PET measurement.
* Event counts have not been normalised by traffic volume or road-user exposure.
* The analysis covers one observation day and cannot establish whether the same patterns occur on other days.
* Spatial concentrations represent event counts rather than exposure-adjusted risk.
* The analysis does not independently validate the underlying detection algorithms.

### 6. Next Steps

The next phase will focus on improving the reliability and scientific interpretation of the results.

Planned tasks include:

1. Reviewing the generated visualisations and verifying their interpretation.
2. Investigating the temporal and spatial patterns of pedestrian and cyclist interactions.
3. Reviewing the assumptions and limitations of the TTC and PET-proxy methods.
4. Identifying a feasible approach to validate a sample of detected interactions.
5. Improving the reproducibility and documentation of the analysis.
6. Preparing the results for the final project presentation.

### 7. Deliverables

The new analysis deliverables are:

* `analyze_full_day_results.py`
* `output/extended_analysis/interaction_type_summary.csv`
* `output/extended_analysis/hourly_interaction_summary.csv`
* `output/extended_analysis/ttc_by_interaction_type.png`
* `output/extended_analysis/hourly_interactions.png`
* `output/extended_analysis/spatial_hotspots.png`
* `output/extended_analysis/findings.md`

The work adds a separate post-processing analysis stage to the project without repeating the full-day detection run.

### 8. Summary

This week's contribution extends the existing full-day results with additional statistical summaries, temporal analysis, spatial visualisation, and documented findings.

The results provide a basis for further investigation into the detected pedestrian, cyclist, and vehicle interactions. Further validation and exposure analysis are required before drawing conclusions about actual collision risk.
