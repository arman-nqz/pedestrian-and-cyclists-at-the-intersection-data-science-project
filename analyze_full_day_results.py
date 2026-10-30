
"""
Analyze the existing full-day TTC and PET-proxy results.

This script does NOT rerun the original traffic analysis.
It reads the existing event CSV files and creates:
- Summary tables
- Hourly interaction analysis
- TTC distribution plot
- Hourly interaction plot
- Spatial hotspot plot
- Markdown findings report

Run from the project root:
    .venv\\Scripts\\python.exe analyze_full_day_results.py
"""

from pathlib import Path
import json

import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent

INPUT_DIR = (
    PROJECT_DIR
    / "output"
    / "full_day_20261026_204014_631230"
)

OUTPUT_DIR = PROJECT_DIR / "output" / "extended_analysis"

TTC_FILE = INPUT_DIR / "near_miss_ttc_events.csv"
PET_FILE = INPUT_DIR / "near_miss_pet_proxy_events.csv"

TTC_THRESHOLD_SECONDS = 1.5
PET_THRESHOLD_SECONDS = 1.5

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Load and validate existing results
# ---------------------------------------------------------

def load_results():
    """Load the saved event tables without rerunning the analysis."""

    if not TTC_FILE.exists():
        raise FileNotFoundError(f"TTC results not found: {TTC_FILE}")

    if not PET_FILE.exists():
        raise FileNotFoundError(f"PET results not found: {PET_FILE}")

    ttc = pd.read_csv(TTC_FILE)
    pet = pd.read_csv(PET_FILE)

    required_ttc = {
        "timestamp_local",
        "interaction_type",
        "min_ttc_sec",
        "x_mid",
        "y_mid",
    }

    required_pet = {
        "pet_sec",
        "interaction_type",
        "is_near_miss_pet_proxy",
    }

    missing_ttc = required_ttc - set(ttc.columns)
    missing_pet = required_pet - set(pet.columns)

    if missing_ttc:
        raise ValueError(f"TTC CSV is missing columns: {sorted(missing_ttc)}")

    if missing_pet:
        raise ValueError(f"PET CSV is missing columns: {sorted(missing_pet)}")

    ttc["min_ttc_sec"] = pd.to_numeric(
        ttc["min_ttc_sec"], errors="coerce"
    )

    ttc["x_mid"] = pd.to_numeric(ttc["x_mid"], errors="coerce")
    ttc["y_mid"] = pd.to_numeric(ttc["y_mid"], errors="coerce")

    ttc["timestamp"] = pd.to_datetime(
        ttc["timestamp_local"], errors="coerce", utc=True
    ).dt.tz_convert("Europe/Berlin")

    ttc["hour"] = ttc["timestamp"].dt.hour

    pet["pet_sec"] = pd.to_numeric(pet["pet_sec"], errors="coerce")

    return ttc, pet


# ---------------------------------------------------------
# 1. Interaction type summary
# ---------------------------------------------------------

def create_interaction_summary(ttc):
    """Summarise consolidated TTC events by interaction type."""

    summary = (
        ttc.groupby("interaction_type", dropna=False)
        .agg(
            event_count=("min_ttc_sec", "size"),
            median_ttc_sec=("min_ttc_sec", "median"),
            mean_ttc_sec=("min_ttc_sec", "mean"),
            minimum_ttc_sec=("min_ttc_sec", "min"),
            q25_ttc_sec=("min_ttc_sec", lambda x: x.quantile(0.25)),
            q75_ttc_sec=("min_ttc_sec", lambda x: x.quantile(0.75)),
        )
        .reset_index()
        .sort_values("event_count", ascending=False)
    )

    summary["share_percent"] = (
        summary["event_count"] / len(ttc) * 100
    ).round(2)

    summary.to_csv(
        OUTPUT_DIR / "interaction_type_summary.csv",
        index=False,
    )

    return summary


# ---------------------------------------------------------
# 2. Hourly interaction summary
# ---------------------------------------------------------

def create_hourly_summary(ttc):
    """Count consolidated TTC events by hour and interaction type."""

    valid = ttc.dropna(subset=["hour"]).copy()
    valid["hour"] = valid["hour"].astype(int)

    hourly = (
        valid.groupby(["hour", "interaction_type"])
        .size()
        .rename("event_count")
        .reset_index()
    )

    hourly.to_csv(
        OUTPUT_DIR / "hourly_interaction_summary.csv",
        index=False,
    )

    return hourly


# ---------------------------------------------------------
# 3. TTC distribution graph
# ---------------------------------------------------------

def plot_ttc_distributions(ttc, summary):
    """Plot TTC distributions for the most frequent interaction types."""

    top_types = summary.head(6)["interaction_type"].tolist()

    plot_data = [
        ttc.loc[
            ttc["interaction_type"] == interaction,
            "min_ttc_sec",
        ].dropna().values
        for interaction in top_types
    ]

    if not top_types:
        return

    fig, ax = plt.subplots(figsize=(12, 7))

    ax.boxplot(
        plot_data,
        tick_labels=top_types,
        showfliers=False,
    )

    ax.axhline(
        TTC_THRESHOLD_SECONDS,
        linestyle="--",
        label=f"TTC threshold: {TTC_THRESHOLD_SECONDS}s",
    )

    ax.set_title("TTC Distribution by Interaction Type")
    ax.set_xlabel("Interaction type")
    ax.set_ylabel("Minimum TTC (seconds)")
    ax.tick_params(axis="x", rotation=35)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "ttc_by_interaction_type.png",
        dpi=200,
    )
    plt.close(fig)


# ---------------------------------------------------------
# 4. Hourly interaction graph
# ---------------------------------------------------------

def plot_hourly_interactions(hourly):
    """Plot hourly event counts for the most frequent types."""

    if hourly.empty:
        return

    totals = (
        hourly.groupby("interaction_type")["event_count"]
        .sum()
        .sort_values(ascending=False)
    )

    top_types = totals.head(5).index.tolist()

    pivot = (
        hourly[hourly["interaction_type"].isin(top_types)]
        .pivot(
            index="hour",
            columns="interaction_type",
            values="event_count",
        )
        .fillna(0)
        .reindex(range(24), fill_value=0)
    )

    fig, ax = plt.subplots(figsize=(13, 7))

    pivot.plot(kind="line", marker="o", ax=ax)

    ax.set_title("Hourly TTC Events by Interaction Type")
    ax.set_xlabel("Hour of day (Germany local time)")
    ax.set_ylabel("Consolidated TTC event count")
    ax.set_xticks(range(24))
    ax.grid(alpha=0.25)
    ax.legend(title="Interaction type")

    fig.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "hourly_interactions.png",
        dpi=200,
    )
    plt.close(fig)


# ---------------------------------------------------------
# 5. Spatial hotspot graph
# ---------------------------------------------------------

def plot_spatial_hotspots(ttc):
    """
    Plot TTC event locations.

    This is an event-density plot, not a risk-normalised map.
    """

    spatial = ttc.dropna(subset=["x_mid", "y_mid"]).copy()

    if spatial.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 8))

    hb = ax.hexbin(
        spatial["x_mid"],
        spatial["y_mid"],
        gridsize=30,
        mincnt=1,
    )

    fig.colorbar(hb, ax=ax, label="Number of TTC events")

    ax.set_title("Spatial Concentration of Candidate TTC Events")
    ax.set_xlabel("x coordinate (metres, as recorded)")
    ax.set_ylabel("y coordinate (metres, as recorded)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "spatial_hotspots.png",
        dpi=200,
    )
    plt.close(fig)


# ---------------------------------------------------------
# 6. Preliminary findings report
# ---------------------------------------------------------

def create_findings_report(ttc, pet, interaction_summary):
    """Write a concise report with descriptive findings."""

    total_ttc = len(ttc)
    total_pet = len(pet)

    ttc_below_threshold = int(
        (ttc["min_ttc_sec"] < TTC_THRESHOLD_SECONDS).sum()
    )

    pet_below_threshold = int(
        (pet["pet_sec"] < PET_THRESHOLD_SECONDS).sum()
    )

    if not interaction_summary.empty:
        top = interaction_summary.iloc[0]
        top_name = str(top["interaction_type"])
        top_count = int(top["event_count"])
        top_share = float(top["share_percent"])
    else:
        top_name = "Not available"
        top_count = 0
        top_share = 0.0

    median_ttc = ttc["min_ttc_sec"].median()
    mean_ttc = ttc["min_ttc_sec"].mean()

    median_pet = pet["pet_sec"].median()

    report = f"""# Extended Full-Day Results

## Scope

This report summarises the existing full-day event CSVs for intersection K305
on 14 October 2026. It does not rerun the original detection pipeline.

## TTC results

- Consolidated TTC events: {total_ttc:,}
- Events with minimum TTC below {TTC_THRESHOLD_SECONDS:.1f} seconds: {ttc_below_threshold:,}
- Median minimum TTC: {median_ttc:.3f} seconds
- Mean minimum TTC: {mean_ttc:.3f} seconds
- Most frequent interaction type: {top_name} ({top_count:,} events; {top_share:.2f}%)

## PET-proxy results

- Recorded PET-proxy events: {total_pet:,}
- PET-proxy values below {PET_THRESHOLD_SECONDS:.1f} seconds: {pet_below_threshold:,}
- Median PET-proxy value: {median_pet:.3f} seconds

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
"""

    (OUTPUT_DIR / "findings.md").write_text(
        report,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    print("Loading existing full-day results...")

    ttc, pet = load_results()

    print(f"TTC event rows: {len(ttc):,}")
    print(f"PET-proxy event rows: {len(pet):,}")

    summary = create_interaction_summary(ttc)
    hourly = create_hourly_summary(ttc)

    plot_ttc_distributions(ttc, summary)
    plot_hourly_interactions(hourly)
    plot_spatial_hotspots(ttc)

    create_findings_report(ttc, pet, summary)

    print("\nTop interaction types:")
    print(summary.head(10).to_string(index=False))

    print("\nAnalysis complete.")
    print(f"Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

