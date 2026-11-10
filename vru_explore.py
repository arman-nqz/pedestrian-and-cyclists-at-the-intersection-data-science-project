import json
import pandas as pd

path = "database/k305_object_list_2026-10-14_aggregation_5min/k305_object_list_2026-10-14_08-00_to_08-04.json"

with open(path) as f:
    data = json.load(f)

print("Top-level keys:", list(data.keys()))   # to check the structure

rows = []
for frame in data["frames"]:
    for o in frame["objects"]:
        pos = o["bounding_box"]["position"]
        rows.append((frame["timestamp_local"], o["track_id"], o["class_name"], pos["x"], pos["y"]))

df = pd.DataFrame(rows, columns=["time", "track_id", "cls", "x", "y"])

print("\nSightings per type:")
print(df.cls.value_counts())
print("\nReal number of individuals per type:")
print(df.groupby("cls").track_id.nunique())
