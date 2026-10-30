
import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path(r"E:\k305_object_list_2026-10-14_aggregation_5min")

VEHICLES = {"Car", "Van", "Truck", "Bus", "Motorcycle"}
VULNERABLE_USERS = {"Pedestrian", "Cyclist"}

files = sorted(DATA_DIR.glob("*.json"))

if not files:
    raise FileNotFoundError(f"No JSON files found in {DATA_DIR}")

results = []

for file_path in files:
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        frames = data.get("frames", [])
        total_observations = 0
        class_counts = Counter()
        unique_tracks = set()

        for frame in frames:
            for obj in frame.get("objects", []):
                class_name = obj.get("class_name", "Unknown")
                track_id = obj.get("track_id")

                total_observations += 1
                class_counts[class_name] += 1

                # Track ID 0 may mean an unassigned identity.
                if track_id not in (None, 0, "0"):
                    unique_tracks.add((class_name, track_id))

        traffic_observations = sum(
            count for name, count in class_counts.items()
            if name in VEHICLES or name in VULNERABLE_USERS
        )

        road_user_observations = sum(
            count for name, count in class_counts.items()
            if name in VULNERABLE_USERS
        )

        results.append({
            "file": file_path.name,
            "frames": len(frames),
            "observations": total_observations,
            "traffic_observations": traffic_observations,
            "road_user_observations": road_user_observations,
            "unique_tracks": len(unique_tracks),
            "classes": class_counts,
        })

    except (json.JSONDecodeError, OSError) as exc:
        print(f"Skipping {file_path.name}: {exc}")

if not results:
    raise RuntimeError("No files could be analysed.")

# Primary ranking: total observations of recognised road-user classes.
results.sort(
    key=lambda item: item["traffic_observations"],
    reverse=True
)

print("\nTOP 10 BUSIEST FIVE-MINUTE INTERVALS")
print("=" * 75)

for rank, result in enumerate(results[:10], start=1):
    print(
        f"{rank:2}. {result['file']}\n"
        f"    Frames: {result['frames']:,} | "
        f"Traffic observations: {result['traffic_observations']:,} | "
        f"Pedestrian/cyclist observations: "
        f"{result['road_user_observations']:,} | "
        f"Class-specific track IDs: {result['unique_tracks']:,}"
    )

peak = results[0]

print("\nPEAK INTERVAL")
print("=" * 75)
print(peak["file"])
print("Class observation counts:")
for name, count in peak["classes"].most_common():
    print(f"  {name}: {count:,}")

output_file = Path("peak_traffic_results.csv")

with output_file.open("w", newline="", encoding="utf-8") as f:
    import csv

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "file",
            "frames",
            "observations",
            "traffic_observations",
            "road_user_observations",
            "unique_tracks",
        ],
    )
    writer.writeheader()

    for result in results:
        writer.writerow({
            key: result[key]
            for key in writer.fieldnames
        })

print(f"\nFull ranking saved to: {output_file.resolve()}")
