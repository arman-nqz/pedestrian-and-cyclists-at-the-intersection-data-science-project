"""Traffic-signal log (VRS5000, one row per second, 06:00 to 13:00) and its link to the crossings.

    read_signals(path)            -> DataFrame: t (epoch s) plus one column per signal group / detector
    signal_groups(df)             -> independent signal timelines, e.g. {"F12": ["F12", "F13", "F14", "F15"], ...}
    state_at(df, group, times)    -> state (G, R, A, S, ...) of a group at given epoch times
    infer_mapping(entries, sig)   -> which pedestrian / cyclist signal group serves each crossing

Column meaning (from the names, not from an official plan): K = vehicle signal groups, F = pedestrian signal
groups, R1 = probably a cyclist signal, D / VD = detector occupancy (%), FT = probably push buttons, MP = measuring
points, SP = signal program, PH = phase. States: G green, R red, A amber, S red-amber, D dark, r/a/g flashing.
"""
import numpy as np
import pandas as pd

HEADER_ROW = 16  # row with "Datum, Uhrzeit, Tx, K1, ..." in the Excel export
STATES = {"G": "green", "R": "red", "A": "amber", "S": "red-amber", "D": "dark", "r": "red flashing",
          "a": "amber flashing", "g": "green flashing", "?": "unknown"}


def read_signals(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(min_row=HEADER_ROW, values_only=True))
    df = pd.DataFrame(rows[1:], columns=[str(c) for c in rows[0]])
    df = df[df["Timestamp"].notna()].copy()
    df["t"] = df["Timestamp"].astype("int64") / 1000.0
    df["local"] = df["Uhrzeit"].astype(str)
    return df.drop(columns=["Datum", "Uhrzeit", "Timestamp"]).reset_index(drop=True)


def signal_columns(df, prefix):
    """Columns of one kind whose values are signal states (letters)."""
    out = []
    for c in df.columns:
        if c.startswith(prefix) and c[len(prefix):len(prefix) + 1].isdigit():
            if df[c].astype(str).str.fullmatch(r"[GRASDrag?]").all():
                out.append(c)
    return out


def signal_groups(df, prefixes=("F", "R", "K")):
    """Group columns that switch identically; returns {representative: [members]} per prefix order."""
    groups = {}
    for p in prefixes:
        seen = {}
        for c in signal_columns(df, p):
            key = df[c].astype(str).str.cat()
            seen.setdefault(key, []).append(c)
        for members in seen.values():
            groups[members[0]] = members
    return groups


def state_at(df, col, times, lag_s=0.0):
    """State of `col` at each epoch time (the log has one row per second)."""
    t = df["t"].to_numpy()
    idx = np.searchsorted(t, np.asarray(times, float) + lag_s, side="right") - 1
    ok = (idx >= 0) & (np.asarray(times, float) + lag_s < t[-1] + 1)
    out = np.full(len(idx), None, dtype=object)
    out[ok] = df[col].astype(str).to_numpy()[idx[ok]]
    return out


def infer_mapping(entries, sig, groups, classes=("Pedestrian",), lags=range(-10, 11), min_entries=30):
    """For each crossing: the signal group whose green best explains when people enter it.

    Score = share of entries that start on green minus how often that group is green at all. (A ratio would favour
    groups that are almost never green.) One clock offset between log and sensor is chosen for the whole junction
    from `lags`, the one that maximizes the summed best score. Returns a DataFrame for that lag, best first.
    """
    e = entries[entries["cls"].isin(classes) & (entries["t_enter"] >= sig["t"].min()) & (entries["t_enter"] < sig["t"].max())]
    rows = []
    for crossing, sub in e.groupby("crossing"):
        if len(sub) < min_entries:
            continue
        for rep, members in groups.items():
            base = (sig[rep].astype(str) == "G").mean()
            if base == 0 or base == 1:
                continue
            for lag in lags:
                g = np.mean(state_at(sig, rep, sub["t_enter"].to_numpy(), lag) == "G")
                rows.append((crossing, rep, ",".join(members), lag, len(sub), g, base, g / base))
    res = pd.DataFrame(rows, columns=["crossing", "group", "members", "lag_s", "entries", "green_share", "green_base", "lift"])
    if res.empty:
        return res
    res["score"] = res["green_share"] - res["green_base"]
    per_lag = res.groupby(["lag_s", "crossing"])["score"].max().groupby("lag_s").sum()
    lag = int(per_lag.idxmax())
    out = res[res["lag_s"] == lag]
    return out.sort_values(["crossing", "score"], ascending=[True, False]).reset_index(drop=True)
