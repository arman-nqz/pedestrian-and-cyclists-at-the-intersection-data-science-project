# Extended Full-Day Results

## Scope

This report summarises the existing full-day event CSVs for intersection K305
on 14 October 2026. It does not rerun the original detection pipeline.

## TTC results

- Consolidated TTC events: 2,583
- Events with minimum TTC below 1.5 seconds: 2,583
- Median minimum TTC: 0.567 seconds
- Mean minimum TTC: 0.637 seconds
- Most frequent interaction type: Car_vs_Pedestrian (1,024 events; 39.64%)

## PET-proxy results

- Recorded PET-proxy events: 22,192
- PET-proxy values below 1.5 seconds: 21,603
- Median PET-proxy value: 1.100 seconds

## Interpretation and limitations

1. TTC results are algorithm-generated candidate interactions, not confirmed collisions.
2. PET uses a 2-metre grid-cell occupancy proxy and is not a definitive engineering PET measurement.
3. Event counts are not risk rates: road-user exposure and traffic volume have not been normalised.
4. The dataset represents one observation day, so results should not automatically be generalised to other days.
5. Spatial concentrations represent event counts, not exposure-adjusted risk.
6. The analysis depends on the accuracy of timestamps, object tracking, coordinates, velocities, and the configured thresholds.
7. These descriptive results do not independently validate the detection algorithms.

## Output files

- `interaction_type_summary.csv`
- `hourly_interaction_summary.csv`
- `ttc_by_interaction_type.png`
- `hourly_interactions.png`
- `spatial_hotspots.png`

These outputs should be reviewed before drawing stronger conclusions.
