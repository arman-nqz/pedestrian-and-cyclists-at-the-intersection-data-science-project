"""Conflicts: near-miss candidates from the original pipeline (TTC and PET), when and where, with a jump to the replay."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from lib import data, filters, plots, video  # noqa: E402

st.set_page_config(page_title="Conflicts - K305", layout="wide")
st.title("Where and when do VRUs meet motor traffic?")
f = filters.sidebar(show_classes=False)
st.warning("These are **candidates** found by an algorithm, not confirmed conflicts. Counts are not divided by traffic "
           "volume (more people, more events). Thresholds of the original pipeline: TTC below 1.5 s, PET below 1.5 s. "
           "Check single events in the replay and video.")

metric = st.radio("Measure", ["TTC (time to collision)", "PET (post-encroachment time)"], horizontal=True)
ttc = metric.startswith("TTC")
try:
    ev = pd.read_parquet(data._need(data.DATA / f"events_published_{'ttc' if ttc else 'pet'}.parquet"))
    off = data.meta()["utc_offset_s"]
except data.MissingData as e:
    st.error(str(e))
    st.stop()
val, x, y = ("min_ttc_sec", "x_mid", "y_mid") if ttc else ("pet_sec", "zone_x", "zone_y")
if "t_end" not in ev:
    ev["t_end"] = ev["t"]
ev["local_s"] = ((ev["t"] + off) % 86400).astype(float)
ev["hour"] = (ev["local_s"] // 3600).astype(int)

types = ev["interaction_type"].value_counts()
c1, c2 = st.columns([3, 1])
pick = c1.multiselect("Class pairs", list(types.index), default=list(types.index),
                      format_func=lambda s: f"{s.replace('_vs_', ' / ')} ({types[s]:,})")
limit = c2.slider(f"{'TTC' if ttc else 'PET'} at most (s)", 0.0, 1.5, 1.5, 0.1)
lo, hi = f["t_from"] * 900, f["t_to"] * 900
sel = ev[ev["interaction_type"].isin(pick) & (ev[val] <= limit) & (ev["local_s"] >= lo) & (ev["local_s"] < hi)]
st.caption(f"{len(sel):,} of {len(ev):,} events, {video.hms(lo)} to {video.hms(min(hi, 86399))} (sidebar time filter).")
if sel.empty:
    st.info("No events for this selection.")
    st.stop()

palette = ["#d62728", "#1f77b4", "#ff7f0e", "#9467bd", "#2ca02c", "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]
color = {t: palette[i % len(palette)] for i, t in enumerate(types.index)}

left, right = st.columns([3, 2])
with left:
    st.subheader("Where")
    fig = go.Figure()
    for t, s in sel.groupby("interaction_type"):
        fig.add_trace(go.Scattergl(
            x=s[x], y=s[y], mode="markers", name=t.replace("_vs_", " / "),
            marker=dict(color=color[t], size=np.clip(12 - 6 * s[val], 4, 12), opacity=0.6, line=dict(width=0)),
            customdata=np.c_[s["local_s"].map(video.hms), s[val]],
            hovertemplate="%{customdata[0]}<br>" + ("TTC" if ttc else "PET") + " %{customdata[1]:.2f} s<extra>" + t + "</extra>"))
    plots.base_map(fig)
    plots.square_axes(fig)
    fig.update_layout(height=620, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, width="stretch")
    st.caption("Bigger dot = smaller " + ("TTC" if ttc else "PET") + ". " +
               ("Position: middle point between the two objects." if ttc else "Position: centre of the 2 m cell both objects passed."))
with right:
    st.subheader("When")
    h = sel.groupby(["hour", "interaction_type"]).size().unstack(fill_value=0).reindex(range(24), fill_value=0)
    hf = go.Figure([go.Bar(x=[f"{i:02d}" for i in h.index], y=h[t], name=t.replace("_vs_", " / "), marker_color=color[t])
                    for t in h.columns])
    hf.update_layout(barmode="stack", height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="hour (local)",
                     yaxis_title="events", showlegend=False)
    st.plotly_chart(hf, width="stretch")
    st.subheader("Pairs")
    tab = sel.groupby("interaction_type")[val].agg(events="size", median="median").sort_values("events", ascending=False)
    tab.index = tab.index.str.replace("_vs_", " / ")
    st.dataframe(tab.rename(columns={"median": f"median {'TTC' if ttc else 'PET'} (s)"}).round(2), width="stretch")

st.subheader("Events")
cols = ["local_time", "interaction_type", val, "track_id_1", "track_id_2", x, y] + (["duration_sec"] if ttc else [])
show = sel.sort_values(val).assign(local_time=lambda d: d["local_s"].map(video.hms))[cols + ["local_s", "t", "t_end"]]
picked = st.dataframe(show[cols].round(2), hide_index=True, width="stretch", height=320,
                      on_select="rerun", selection_mode="single-row")
rows = picked.selection.rows if picked else []
if not rows:
    st.caption("Select a row to replay it. Sorted by severity; click a column header to sort.")
else:
    r = show.iloc[rows[0]]
    in_video = video.START_S <= r["local_s"] < video.END_S
    st.markdown(f"**{r['local_time']}**, {r['interaction_type'].replace('_vs_', ' / ')}, "
                f"{'TTC' if ttc else 'PET'} {r[val]:.2f} s, tracks {r['track_id_1']} and {r['track_id_2']}"
                + ("" if in_video else " (no video at this time)"))
    if st.button("Replay this event (from 5 s before)", type="primary"):
        st.session_state["video_time"] = int(r["local_s"]) - 5
        st.session_state["replay_event"] = {
            "local_s": float(r["local_s"]), "local_end": float(r["local_s"] + r["t_end"] - r["t"]),
            "x": float(r[x]), "y": float(r[y]), "ids": [int(r["track_id_1"]), int(r["track_id_2"])],
            "label": f"{r['interaction_type'].replace('_vs_', ' / ')}, {'TTC' if ttc else 'PET'} {r[val]:.2f} s"}
        st.switch_page("pages/5_Replay.py")
