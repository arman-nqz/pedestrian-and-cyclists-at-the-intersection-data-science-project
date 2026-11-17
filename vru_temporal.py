"""Area 5: Temporal VRU Analysis (15-min volumes, peak hours, Ped vs Cyclist).

Reads output/vru_analysis/{vru_tracks,vru_counts_15min,vru_dwell_15min}.csv
and writes temporal summary tables + charts to output/vru_analysis/.
"""
import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = "output/vru_analysis"
MIN_MOVEMENT_M = 1.5  # threshold to separate moving VRUs from stationary objects


def main():
    tracks = pd.read_csv(os.path.join(OUT_DIR, "vru_tracks.csv"), index_col=0)
    tracks["t_start"] = pd.to_datetime(tracks["t_start"])
    tracks["window"] = tracks["t_start"].dt.floor("15min")

    # Separate moving VRUs from stationary detections (e.g., parked bikes/poles)
    moving = tracks[tracks["displacement_m"] >= MIN_MOVEMENT_M].copy()
    print(f"Total tracks: {len(tracks)} | Moving tracks (>= {MIN_MOVEMENT_M}m): {len(moving)}")

    # Build complete 96-slot 15-minute grid for the full day
    day_start = moving["window"].min().floor("D")
    full_grid = pd.date_range(day_start, periods=96, freq="15min")

    counts = (
        moving.groupby(["window", "cls"])
        .size()
        .unstack(fill_value=0)
        .reindex(full_grid, fill_value=0)
    )
    for col in ["Pedestrian", "Cyclist"]:
        if col not in counts.columns:
            counts[col] = 0
    counts["Total_VRU"] = counts["Pedestrian"] + counts["Cyclist"]

    dwell = (
        moving.groupby(["window", "cls"])["dwell_s"]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(full_grid, fill_value=0.0)
    )

    # Rolling 60-minute (4 x 15-min) peak hours
    rolling_1h = counts.rolling(4).sum().dropna()
    peak_summary = []
    for col in ["Pedestrian", "Cyclist", "Total_VRU"]:
        peak_end = rolling_1h[col].idxmax()
        peak_start = peak_end - pd.Timedelta(minutes=45)
        peak_val = int(rolling_1h.loc[peak_end, col])
        peak_summary.append({
            "Category": col,
            "Peak_Hour_Window": f"{peak_start.strftime('%H:%M')} - {(peak_end + pd.Timedelta(minutes=15)).strftime('%H:%M')}",
            "Peak_1h_Count": peak_val,
            "Share_of_Daily_Pct": round(100 * peak_val / counts[col].sum(), 1),
        })
    peak_df = pd.DataFrame(peak_summary)

    # Pedestrian vs. Cyclist behavioral & volume comparison
    comp_rows = []
    for cls in ["Pedestrian", "Cyclist"]:
        sub = moving[moving["cls"] == cls]
        mean_15m = counts[cls].mean()
        max_15m = counts[cls].max()
        comp_rows.append({
            "Class": cls,
            "Daily_Moving_Tracks": len(sub),
            "Mean_per_15min": round(mean_15m, 1),
            "Max_per_15min": int(max_15m),
            "Peak_to_Mean_Ratio": round(max_15m / mean_15m, 2) if mean_15m > 0 else 0,
            "Median_Duration_s": round(sub["duration_s"].median(), 1),
            "Median_Displacement_m": round(sub["displacement_m"].median(), 1),
            "Median_Speed_mps": round(sub["mean_speed_mps"].median(), 2),
            "Total_Dwell_Hours": round(sub["dwell_s"].sum() / 3600, 2),
        })
    comp_df = pd.DataFrame(comp_rows)

    # Save tables
    counts.to_csv(os.path.join(OUT_DIR, "temporal_15min_moving.csv"))
    peak_df.to_csv(os.path.join(OUT_DIR, "temporal_peak_hours.csv"), index=False)
    comp_df.to_csv(os.path.join(OUT_DIR, "temporal_ped_vs_cyclist.csv"), index=False)

    print("\n--- Peak 60-Minute Windows ---")
    print(peak_df.to_string(index=False))
    print("\n--- Pedestrian vs. Cyclist Comparison ---")
    print(comp_df.to_string(index=False))

    # Plot 15-minute volume and dwell-time curves
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)

    ax1.plot(counts.index, counts["Pedestrian"], label="Pedestrians", color="#1f77b4", linewidth=2)
    ax1.plot(counts.index, counts["Cyclist"], label="Cyclists", color="#ff7f0e", linewidth=2)
    ax1.set_ylabel("Unique Tracks / 15 min")
    ax1.set_title("Intersection K305 — 15-Minute VRU Volume & Occupancy (Oct 29, 2026)")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2.plot(dwell.index, dwell.get("Pedestrian", 0) / 60.0, label="Pedestrian Dwell (person-min)", color="#1f77b4", linewidth=2)
    ax2.plot(dwell.index, dwell.get("Cyclist", 0) / 60.0, label="Cyclist Dwell (cyclist-min)", color="#ff7f0e", linewidth=2)
    ax2.set_ylabel("Occupancy (person-min / 15 min)")
    ax2.set_xlabel("Local Time (CET)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=counts.index.tz))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    chart_path = os.path.join(OUT_DIR, "temporal_vru_profiles.png")
    plt.savefig(chart_path, dpi=200)
    print(f"\nSaved temporal tables and chart to {OUT_DIR}/")


if __name__ == "__main__":
    main()