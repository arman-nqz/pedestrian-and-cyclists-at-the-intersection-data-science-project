"""Area 4: Spatial VRU Density Heatmaps, Crosswalk Usage & VRU-Vehicle Overlap.

Reads output/vru_analysis/{vru_tracks,vru_points,vehicle_points}.csv
and writes compact spatial summary CSVs + PNG maps to output/vru_analysis/.
"""
import json
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT_DIR = "output/vru_analysis"
ZONES_PATH = "/content/drive/MyDrive/event_zones.json"  # optional polygon overlay
MIN_MOVEMENT_M = 1.5
CELL_SIZE = 0.5  # 0.5 m x 0.5 m spatial grid


def load_zones(path):
    """Load crosswalk/bike-lane polygons from event_zones.json if available."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = json.load(f)
    zones = {}
    items = raw.values() if isinstance(raw, dict) else raw
    for item in items:
        if isinstance(item, dict) and "name" in item and "points" in item:
            pts = np.array([[p["x"], p["y"]] if isinstance(p, dict) else p[:2] for p in item["points"]])
            if len(pts) >= 3:
                zones[item["name"]] = pts
    return zones


def draw_zones(ax, zones):
    for name, pts in zones.items():
        closed = np.vstack([pts, pts[0]])
        ax.plot(closed[:, 0], closed[:, 1], color="cyan", linewidth=1.8, linestyle="--")
        cx, cy = pts.mean(axis=0)
        ax.text(cx, cy, name, color="white", fontsize=8, fontweight="bold",
                ha="center", va="center", bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.6))


def main():
    tracks = pd.read_csv(os.path.join(OUT_DIR, "vru_tracks.csv"), index_col=0)
    moving_ids = set(tracks[tracks["displacement_m"] >= MIN_MOVEMENT_M].index)

    vru_pts = pd.read_csv(os.path.join(OUT_DIR, "vru_points.csv"), usecols=["track_id", "cls", "x", "y"])
    vru_pts = vru_pts[vru_pts["track_id"].isin(moving_ids)].copy()

    veh_path = os.path.join(OUT_DIR, "vehicle_points.csv")
    veh_pts = pd.read_csv(veh_path, usecols=["x", "y"]) if os.path.exists(veh_path) else pd.DataFrame(columns=["x", "y"])

    # Common 0.5 m x 0.5 m grid bounds
    all_x = pd.concat([vru_pts["x"], veh_pts["x"]]) if not veh_pts.empty else vru_pts["x"]
    all_y = pd.concat([vru_pts["y"], veh_pts["y"]]) if not veh_pts.empty else vru_pts["y"]
    x_min, x_max = np.floor(all_x.quantile(0.002)), np.ceil(all_x.quantile(0.998))
    y_min, y_max = np.floor(all_y.quantile(0.002)), np.ceil(all_y.quantile(0.998))

    x_edges = np.arange(x_min, x_max + CELL_SIZE, CELL_SIZE)
    y_edges = np.arange(y_min, y_max + CELL_SIZE, CELL_SIZE)
    zones = load_zones(ZONES_PATH)

    # 1. Pedestrian & Cyclist 2D Dwell-Time Heatmaps (10 Hz -> 0.1 s per point)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), sharex=True, sharey=True)
    grids = {}
    for ax, cls in zip(axes, ["Pedestrian", "Cyclist"]):
        sub = vru_pts[vru_pts["cls"] == cls]
        H, _, _ = np.histogram2d(sub["x"], sub["y"], bins=[x_edges, y_edges])
        dwell_s = H.T * 0.1
        grids[cls] = dwell_s

        masked = np.ma.masked_where(dwell_s <= 0, dwell_s)
        im = ax.pcolormesh(x_edges, y_edges, masked, cmap="hot_r", shading="auto",
                           vmax=np.percentile(dwell_s[dwell_s > 0], 98) if np.any(dwell_s > 0) else 1)
        draw_zones(ax, zones)
        ax.set_title(f"{cls} Spatial Dwell Density (s / 0.25 m²)")
        ax.set_xlabel("X (meters)")
        ax.set_ylabel("Y (meters)")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.25)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Total Dwell (s)")

    plt.suptitle("Intersection K305 — VRU Spatial Heatmaps (Oct 29, 2026)", fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "spatial_vru_heatmaps.png"), dpi=200)

    # 2. VRU-Vehicle Spatial Overlap Map
    if not veh_pts.empty:
        H_veh, _, _ = np.histogram2d(veh_pts["x"], veh_pts["y"], bins=[x_edges, y_edges])
        veh_s = H_veh.T * 1.0  # downsampled at 1 Hz -> 1.0 s per point
        vru_total_s = grids["Pedestrian"] + grids["Cyclist"]

        # Geometric mean exposure index where both VRUs and vehicles occupy the same cell
        overlap = np.sqrt(vru_total_s * veh_s)
        overlap_cells = int(np.sum(overlap > 0))
        vru_cells = int(np.sum(vru_total_s > 0))
        print(f"VRU-occupied cells: {vru_cells} | Shared VRU-Vehicle overlap cells: {overlap_cells} ({100*overlap_cells/max(vru_cells,1):.1f}%)")

        fig, ax = plt.subplots(figsize=(9, 7.5))
        ax.pcolormesh(x_edges, y_edges, np.ma.masked_where(veh_s <= 0, np.log1p(veh_s)),
                      cmap="Blues", alpha=0.45, shading="auto")
        im = ax.pcolormesh(x_edges, y_edges, np.ma.masked_where(overlap <= 0, np.log1p(overlap)),
                           cmap="magma_r", shading="auto")
        draw_zones(ax, zones)
        ax.set_title("Intersection K305 — VRU-Vehicle Spatial Overlap Hotspots")
        ax.set_xlabel("X (meters)")
        ax.set_ylabel("Y (meters)")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.25)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Overlap Exposure Index log(1 + √(t_VRU · t_Veh))")
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_DIR, "spatial_vru_vehicle_overlap.png"), dpi=200)

        # Save top 25 overlap hotspot coordinates as a tiny CSV
        yi, xi = np.where(overlap > 0)
        hotspots = pd.DataFrame({
            "x_center_m": x_edges[xi] + CELL_SIZE / 2,
            "y_center_m": y_edges[yi] + CELL_SIZE / 2,
            "vru_dwell_s": np.round(vru_total_s[yi, xi], 1),
            "vehicle_dwell_s": np.round(veh_s[yi, xi], 1),
            "overlap_index": np.round(overlap[yi, xi], 2),
        }).sort_values("overlap_index", ascending=False)
        hotspots.head(50).to_csv(os.path.join(OUT_DIR, "spatial_overlap_hotspots.csv"), index=False)

    print(f"Saved spatial maps and hotspot table to {OUT_DIR}/")


if __name__ == "__main__":
    main()