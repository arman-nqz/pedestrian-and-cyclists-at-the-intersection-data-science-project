"""Data quality: what cleaning and stitching did to the numbers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from lib import data, filters, plots  # noqa: E402

st.set_page_config(page_title="Data quality - K305", layout="wide")
st.title("Data quality: what the cleaning does")
f = filters.sidebar(show_time=False, show_classes=False)

try:
    q = data.quality()
except data.MissingData as e:
    st.error(str(e))
    st.stop()

raw = q["raw"]
c = st.columns(4)
c[0].metric("Detections", f"{raw['rows']:,}")
c[1].metric("Duplicate rows removed", f"{raw.get('duplicate_rows_removed', 0):,}")
c[2].metric("Segments (split at gaps > 1 s)", f"{q['stitching']['segments']:,}")
c[3].metric("Joins made by stitching", f"{q['stitching']['joins']:,}")

st.subheader("Tracks per class at each stage")
stages = q["tracks_per_stage"]
df = pd.DataFrame(stages).reindex(data.CLASSES)
fig = go.Figure()
for name, color in (("segments", "#b0bec5"), ("stitched", "#1c7293"), ("clean", "#12263a")):
    fig.add_trace(go.Bar(x=df.index, y=df[name], name=name, marker_color=color,
                         hovertemplate="%{x}: %{y:,} tracks<extra>" + name + "</extra>"))
fig.update_layout(barmode="group", height=380, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="tracks", yaxis_type="log",
                  legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig, width="stretch")
st.caption("Log scale. `segments`: split at gaps; `stitched`: pieces joined; `clean`: stitched minus tracks with "
           f"< {q['parameters']['min_frames']} frames or < {q['parameters']['min_extent_m']} m of movement.")
st.dataframe(df.astype(int), width="stretch")

st.subheader("How much do the filter settings matter?")
sens = pd.DataFrame(q["sensitivity"])
st.dataframe(sens[["min_frames", "min_extent_m", "tracks"] + data.VRU], hide_index=True, width="stretch")
st.caption("Tracks left after stitching for different minimum frame counts and minimum movement. "
           "People who wait at the curb barely move, so a high movement threshold removes them.")

st.subheader("Stitching")
left, right = st.columns(2)
with left:
    gh = q["stitching"]["gap_histogram"]
    centers = [(a + b) / 2 for a, b in zip(gh["bin_edges_s"][:-1], gh["bin_edges_s"][1:])]
    g = go.Figure(go.Bar(x=centers, y=gh["joins"], marker_color="#1c7293"))
    g.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title="Length of the gaps that were bridged",
                    xaxis_title="gap (s)", yaxis_title="joins")
    st.plotly_chart(g, width="stretch")
    syn = pd.DataFrame(q["synthetic_cut_test"])
    st.markdown("**Synthetic test:** holes of 0.5 to 3 s were cut into long real tracks; share repaired correctly "
                "and share joined to the wrong partner.")
    st.dataframe(syn.rename(columns={"cls": "class", "recall": "repaired", "wrong": "wrong join"}), hide_index=True,
                 width="stretch")
with right:
    mp = pd.DataFrame(q["stitching"]["join_midpoints"])
    m = go.Figure()
    plots.base_map(m)
    for cls in data.CLASSES:
        s = mp[mp["cls"] == cls]
        if len(s):
            m.add_trace(go.Scattergl(x=s["x"], y=s["y"], mode="markers", name=cls,
                                     marker=dict(size=3, color=data.COLORS[cls], opacity=0.5)))
    plots.square_axes(m)
    m.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10), title="Where joins happen (sample)",
                    legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(m, width="stretch")

st.subheader("Known issues")
for issue in q.get("known_issues", []):
    st.markdown(f"- {issue}")
st.caption("The stitching on real data has no ground truth; the synthetic test is optimistic because real losses "
           "happen in crowded or occluded places.")
