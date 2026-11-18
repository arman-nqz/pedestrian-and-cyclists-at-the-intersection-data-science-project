"""Step 1: Inspect Ouster BlueCity raw schema and generate data_dictionary.csv.

Point RAW_DIR to your Ouster 07:34-07:44 folder on VM, Drive, or local disk.
"""
import glob
import json
import os
import pandas as pd

RAW_DIR = "/content/drive/MyDrive/ouster_10min"  # update path to your Ouster folder
OUT_DIR = "comparison_project/ouster_team"
os.makedirs(OUT_DIR, exist_ok=True)


def flatten_dict(d, parent_key="", sep="."):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "**/*.*"), recursive=True))
    data_files = [f for f in files if f.lower().endswith((".json", ".csv", ".parquet"))]
    print(f"Found {len(data_files)} data file(s):")
    for f in data_files[:10]:
        print(" ", f)

    if not data_files:
        raise SystemExit("No JSON/CSV/Parquet files found. Check RAW_DIR.")

    sample_file = data_files[0]
    print(f"\nInspecting sample file: {sample_file}")

    if sample_file.lower().endswith(".csv"):
        df = pd.read_csv(sample_file, nrows=100)
    elif sample_file.lower().endswith(".parquet"):
        df = pd.read_parquet(sample_file).head(100)
    else:
        with open(sample_file) as f:
            raw = json.load(f)
        # Handle either list of objects, dict with 'frames', or dict with 'objects'
        if isinstance(raw, list):
            records = [flatten_dict(r) for r in raw[:100]]
        elif "frames" in raw:
            records = []
            for fr in raw["frames"][:10]:
                base = {k: v for k, v in fr.items() if k != "objects"}
                for obj in fr.get("objects", []):
                    records.append({**flatten_dict(base), **flatten_dict(obj, "obj")})
        else:
            records = [flatten_dict(raw)]
        df = pd.DataFrame(records)

    print("\n--- Detected Fields & Sample Values ---")
    dict_rows = []
    for col in df.columns:
        sample_val = df[col].dropna().iloc[0] if not df[col].dropna().empty else "NULL"
        dtype = str(df[col].dtype)
        print(f"  {col:35s} | {dtype:10s} | sample: {sample_val}")
        dict_rows.append({
            "field_name": col,
            "meaning": "TODO: verify description",
            "data_type": dtype,
            "unit": "TODO: s / m / deg / ID / label",
            "coordinate_system": "Ouster sensor frame (verify vs event_zones.json)",
            "missing_invalid_notes": f"Nulls in sample: {int(df[col].isna().sum())}/{len(df)}",
            "sample_value": str(sample_val),
        })

    out_path = os.path.join(OUT_DIR, "data_dictionary.csv")
    pd.DataFrame(dict_rows).to_csv(out_path, index=False)
    print(f"\nSaved template data dictionary to {out_path}")


if __name__ == "__main__":
    main()
