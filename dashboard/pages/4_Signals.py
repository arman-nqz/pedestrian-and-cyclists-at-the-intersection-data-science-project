"""Signals: which light serves which crossing, how many start on red, and a signal timeline (06:00 to 13:00)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for signals.py

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

import signals as sg  # noqa: E402
from lib import data, filters, video  # noqa: E402

st.set_page_config(page_title="Signals - K305", layout="wide")
st.title("Traffic signals: who crosses on green, who on red?")
f = filters.sidebar(show_time=False)

try:
    meta = data.meta()
    sig = pd.read_parquet(data._need(data.DATA / "signals.parquet"))
    groups = json.loads(data._need(data.DATA / "signal_groups.json").read_text(encoding="utf-8"))
    visits = pd.read_parquet(data._need(data.DATA / f"crossing_visits_{f['variant']}.parquet"))
except data.MissingData as e:
    st.error(str(e))
    st.stop()
mp = data.CONFIG / "signal_mapping.json"
mapping = json.loads(mp.read_text(encoding="utf-8"))["crossings"] if mp.exists() else {}
off = meta["utc_offset_s"]
t_lo, t_hi = sig["t"].min(), sig["t"].max() + 1
st.caption(f"Signal log {sig['local'].iat[0]} to {sig['local'].iat[-1]} local time, one row per second. Crossings X1 to X5 "
           "come from the zones (Space page). Variant: " + f"`{f['variant']}`.")

# --- 1. mapping
st.subheader("Which signal serves which crossing (inferred)")
rows = []
for x, by_cls in sorted(mapping.items()):
    for cls, m in by_cls.items():
        rows.append({"crossing": x, "class": cls, "signal group": m["group"], "switches with": ", ".join(m["members"]),
                     "entries on its green": f"{m['green_share']:.0%}", "group green overall": f"{m['green_base']:.0%}",
                     "clear": "yes" if m["clear"] else "no", "runner-up": (m["runner_up"] or {}).get("group"),
                     "entries": m["entries"]})
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    lag = next(iter(next(iter(mapping.values())).values()))["lag_s"]
    st.caption(f"No official signal plan is in the data. For each crossing, the pedestrian / cyclist signal group (F*, R1) "
               f"whose green best explains when people step onto it is chosen (`signal_mapping.py`). Best clock offset "
               f"{lag:+d} s (it mixes a clock difference and the time people need to reach the crossing). "
               "Check this against the junction plan.")
else:
    st.warning("No mapping yet. Run `python signal_mapping.py`.")
    st.stop()

# --- 2. red-light starts
st.subheader("Crossings that start on red")
clear = {(x, c): m for x, by in mapping.items() for c, m in by.items() if m["clear"]}
if not clear:
    st.info("No crossing has a clear signal mapping.")
else:
    v = visits[(visits["t_enter"] >= t_lo) & (visits["t_enter"] < t_hi)]
    out = []
    for (x, cls), m in clear.items():
        sub = v[(v["crossing"] == x) & (v["cls"] == cls)].copy()
        if sub.empty:
            continue
        sub["state"] = sg.state_at(sig, m["group"], sub["t_enter"].to_numpy(), m["lag_s"])
        sub["hour"] = ((sub["t_enter"] + off) % 86400 // 3600).astype(int)
        sub["crossing"], sub["class"] = x, cls
        out.append(sub)
    if out:
        o = pd.concat(out)
        o["red"] = o["state"].isin(["R", "r"])
        tab = o.groupby(["crossing", "class"]).agg(entries=("red", "size"), on_red=("red", "sum")).reset_index()
        tab["share on red"] = (tab["on_red"] / tab["entries"]).map("{:.0%}".format)
        st.dataframe(tab, hide_index=True, width="stretch")
        h = o.groupby(["hour", "class"])["red"].mean().reset_index()
        fig = go.Figure()
        for cls in h["class"].unique():
            s = h[h["class"] == cls]
            fig.add_trace(go.Bar(x=s["hour"].map(lambda x: f"{x:02d}:00"), y=s["red"], name=cls,
                                 marker_color=data.COLORS.get(cls), hovertemplate="%{x}: %{y:.0%} on red<extra>" + cls + "</extra>"))
        fig.update_layout(barmode="group", height=320, yaxis_tickformat=".0%", yaxis_title="share starting on red",
                          margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width="stretch")
        st.caption("Only crossings with a clear mapping. 'Start' = the moment a track enters the crossing area; a person "
                   "who steps on just before red counts as green. Tracks can be cut in pieces, so one person can count "
                   "more than once.")

# --- 3. timeline
st.subheader("Signal timeline")
c1, c2 = st.columns([2, 1])
start_local = c1.slider("Start (local time)", min_value=6 * 60, max_value=13 * 60 - 5, value=7 * 60 + 20, step=1,
                        format="%d", help="minutes after midnight", key="sig_start")
span = c2.select_slider("Length (minutes)", options=[2, 5, 10, 15], value=5)
c1.caption(f"{video.hms(start_local * 60)} to {video.hms((start_local + span) * 60)}")
t0 = sig["t"].iat[0] + (start_local * 60 - 6 * 3600)
w = sig[(sig["t"] >= t0) & (sig["t"] < t0 + span * 60)]
shown = [g for g in groups if g.startswith(("F", "R"))] + [g for g in groups if g.startswith("K")]
color = {"G": "#2e9e44", "R": "#d33a2c", "A": "#f2b632", "S": "#f28c28"}
fig = go.Figure()
for i, g in enumerate(shown):
    st_ = w[g].astype(str).to_numpy()
    tt = (w["t"].to_numpy() - t0) / 60
    change = np.r_[0, np.flatnonzero(st_[1:] != st_[:-1]) + 1, len(st_)]
    for a, b in zip(change[:-1], change[1:]):
        x1 = tt[b] if b < len(tt) else span
        fig.add_trace(go.Bar(x=[x1 - tt[a]], y=[g], base=[tt[a]], orientation="h", marker_color=color.get(st_[a], "#999"),
                             showlegend=False, hovertemplate=f"{g} ({', '.join(groups[g])}): {sg.STATES.get(st_[a], st_[a])}"
                                                             f"<br>%{{base:.1f}} to {x1:.1f} min<extra></extra>"))
lane = {x: m for x, by in mapping.items() for c, m in by.items() if m["clear"] and c == "Pedestrian"}
for x, m in lane.items():
    e = visits[(visits["crossing"] == x) & (visits["t_enter"] >= t0) & (visits["t_enter"] < t0 + span * 60)]
    if len(e):
        fig.add_trace(go.Scatter(x=(e["t_enter"] - t0) / 60, y=[m["group"]] * len(e), mode="markers",
                                 marker=dict(symbol="line-ns-open", size=14, color="black"), name=f"entries {x}",
                                 hovertemplate=f"{x}: %{{customdata}} enters<extra></extra>", customdata=e["cls"]))
fig.update_layout(barmode="overlay", height=30 * len(shown) + 80, margin=dict(l=10, r=10, t=10, b=10),
                  xaxis_title="minutes from start", yaxis=dict(autorange="reversed"), bargap=0.25,
                  legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig, width="stretch")
st.caption("Green / red / amber / red-amber per signal group (F = pedestrian, R1 = probably cyclist, K = vehicle). "
           "Black ticks: pedestrians and cyclists entering a crossing, on the row of its inferred signal group "
           "(entries are not shifted by the clock offset).")
if st.button("Watch this moment in the video"):
    st.session_state["video_time"] = start_local * 60
    st.switch_page("pages/5_Video.py")
