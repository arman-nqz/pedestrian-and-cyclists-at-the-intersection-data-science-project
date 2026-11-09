"""Time: when do VRUs appear? Counts per 15 minutes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from lib import data, filters  # noqa: E402

st.set_page_config(page_title="Time - K305", layout="wide")
st.title("When do pedestrians and cyclists use K305?")
f = filters.sidebar()

try:
    cn = data.counts(f["variant"])
except data.MissingData as e:
    st.error(str(e))
    st.stop()

arms = ["all"] + [a for a in cn["arm"].unique() if a not in ("all", "core")]
c1, c2, c3 = st.columns(3)
metric = c1.radio("Count", ["started", "present"], horizontal=True,
                  help="**started**: tracks that begin in the 15 minutes. **present**: tracks seen at any time in the 15 minutes.")
arm = c2.selectbox("Entry arm", arms, help="arm where the track starts (from the zones); `all` = every track")
per_hour = c3.toggle("Sum per hour", value=False)

sel = cn[(cn["cls"].isin(f["classes"])) & (cn["arm"] == arm) & (cn["bin"] >= f["t_from"]) & (cn["bin"] < f["t_to"])].copy()
if sel.empty:
    st.info("Nothing selected. Choose at least one class in the sidebar.")
    st.stop()
if per_hour:
    sel["bin"] = sel["bin"] // 4 * 4
    sel = sel.groupby(["cls", "bin"], as_index=False)[metric].sum() if metric == "started" else \
        sel.groupby(["cls", "bin"], as_index=False)[metric].max()
sel["time"] = sel["bin"].map(data.bin_label)

fig = go.Figure()
# approximate daylight for Aschaffenburg on 14 Oct (sunrise about 07:40, sunset about 18:35 local)
for x0, x1 in (("00:00", "07:40"), ("18:35", "23:59")):
    fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(30,40,80,0.08)", line_width=0, layer="below")
for cls in f["classes"]:
    s = sel[sel["cls"] == cls]
    fig.add_trace(go.Scatter(x=s["time"], y=s[metric], mode="lines+markers", name=cls,
                             line=dict(color=data.COLORS[cls], width=2.5), marker=dict(size=4),
                             hovertemplate=f"{cls}<br>%{{x}}: %{{y}} tracks<extra></extra>"))
step = "hour" if per_hour else "15 minutes"
fig.update_layout(height=430, margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                  yaxis_title=f"tracks {metric} per {step}", xaxis_title="local time (shaded: dark, approx.)",
                  legend=dict(orientation="h", y=1.08))
st.plotly_chart(fig, width="stretch")
st.caption(f"Variant `{f['variant']}`; each stitched track counts once. Unit: tracks {metric} per {step}.")

st.subheader("Peak windows")
rows = []
for cls in f["classes"]:
    s = sel[sel["cls"] == cls].sort_values(metric, ascending=False).head(3)
    for r in s.itertuples():
        rows.append({"class": cls, "start": r.time, metric: getattr(r, metric)})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

with st.expander("Data table"):
    st.dataframe(sel.pivot_table(index="time", columns="cls", values=metric, aggfunc="sum").fillna(0).astype(int),
                 width="stretch")
