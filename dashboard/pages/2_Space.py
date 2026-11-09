"""Space: where do VRUs go? Density maps on the K305 map."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for zones.py

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

import zones as zn  # noqa: E402
from lib import data, filters, plots  # noqa: E402

LIM = plots.LIM
st.set_page_config(page_title="Space - K305", layout="wide")
st.title("Where do pedestrians and cyclists go?")
f = filters.sidebar()

try:
    dens = data.density(f["variant"])
    pas = data.passes(f["variant"])
except data.MissingData as e:
    st.error(str(e))
    st.stop()

# the density files are per hour; use every hour that overlaps the selected time range
h0, h1 = f["t_from"] // 4, math.ceil(f["t_to"] / 4)
hours = list(range(h0, h1))
hour_note = f"{h0:02d}:00 to {h1:02d}:00" if hours else "no hours"

c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.4])
metric = c1.radio("Show", ["Time spent", "Tracks passing"], horizontal=True,
                  help="**Time spent**: seconds of presence per m2; a person waiting 60 s counts 60 times more than one "
                       "passing for 1 s. **Tracks passing**: distinct tracks that touch the cell (each hour counted "
                       "separately), so waiting people count once.")
cell = c2.select_slider("Cell size (m)", options=[0.5, 1.0, 2.0], value=1.0)
log = c3.toggle("Log color scale", value=True)
mode = c4.radio("Mode", ["Classes together", "Side by side", "Difference"], horizontal=True)
o1, o2 = st.columns(2)
show_osm = o1.checkbox("OpenStreetMap roads and footways", value=True)
show_zones = o2.checkbox("Crossings and arms", value=True)

if not f["classes"]:
    st.info("Choose at least one class in the sidebar.")
    st.stop()


def grid(classes):
    """Value per cell for the chosen classes and hours. Returns (grid, unit)."""
    n = int(2 * LIM / cell)
    g = np.zeros((n, n))
    if metric == "Time spent":
        d = dens[dens["cls"].isin(classes) & dens["hour"].isin(hours)]
        k = int(round(cell / 0.5))
        np.add.at(g, ((d["iy"] // k).to_numpy(), (d["ix"] // k).to_numpy()), d["dwell_s"].to_numpy())
        return g / cell ** 2, "s per m2"
    d = pas[(pas["cell_m"] == cell) & pas["cls"].isin(classes) & pas["hour"].isin(hours)]
    np.add.at(g, (d["iy"].to_numpy(), d["ix"].to_numpy()), d["tracks"].to_numpy())
    return g, f"tracks per {cell:g} m cell"


def heatmap(g, unit, zmin, zmax, colorscale="Magma", diverging=False, showscale=True):
    n = g.shape[0]
    centers = -LIM + (np.arange(n) + 0.5) * cell
    if diverging:
        z, cd = np.where(g == 0, np.nan, g), g
        return go.Heatmap(x=centers, y=centers, z=z, customdata=cd, zmid=0, zmin=zmin, zmax=zmax, colorscale="RdBu_r",
                          colorbar=dict(title=unit), showscale=showscale,
                          hovertemplate="x %{x:.1f} m, y %{y:.1f} m<br>%{customdata:+.3f} " + unit + "<extra></extra>")
    zero = g <= 0
    if log:
        z = np.where(zero, np.nan, np.log10(np.where(zero, 1, g)))
        lo, hi = math.floor(np.log10(max(zmin, 1e-6))), math.ceil(np.log10(max(zmax, 1e-6)))
        ticks = list(range(lo, hi + 1))
        cb = dict(title=unit, tickvals=ticks, ticktext=[f"{10 ** t:g}" for t in ticks])
        zr = (np.log10(max(zmin, 1e-6)), np.log10(max(zmax, 1e-6)))
    else:
        z, cb, zr = np.where(zero, np.nan, g), dict(title=unit), (zmin, zmax)
    return go.Heatmap(x=centers, y=centers, z=z, customdata=g, zmin=zr[0], zmax=zr[1], colorscale=colorscale,
                      colorbar=cb, showscale=showscale,
                      hovertemplate="x %{x:.1f} m, y %{y:.1f} m<br>%{customdata:,.2f} " + unit + "<extra></extra>")


def finish(fig, cols):
    for c in range(1, cols + 1):
        kw = {"row": 1, "col": c} if cols > 1 else {}
        if show_osm or show_zones:
            plots.base_map(fig, show_osm=show_osm, show_zones=show_zones, **kw)
        fig.update_xaxes(range=[-LIM, LIM], title="x (m)", constrain="domain", **kw)
        fig.update_yaxes(range=[-LIM, LIM], title="y (m)" if c == 1 else None, scaleanchor=f"x{c if c > 1 else ''}", constrain="domain", **kw)
    fig.update_layout(height=640 if cols == 1 else 560, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.08), plot_bgcolor="#f4f6f8")
    return fig


if mode == "Classes together":
    g, unit = grid(f["classes"])
    pos = g[g > 0]
    if pos.size == 0:
        st.info("No data for this selection.")
        st.stop()
    fig = go.Figure(heatmap(g, unit, float(pos.min()), float(np.quantile(pos, 0.995))))
    fig.update_layout(title=", ".join(f["classes"]))
    st.plotly_chart(finish(fig, 1), width="stretch")
else:
    pick = st.columns(2)
    choices = f["classes"] if len(f["classes"]) >= 2 else data.CLASSES
    a = pick[0].selectbox("Class A", choices, index=0)
    b = pick[1].selectbox("Class B", [c for c in choices if c != a], index=0)
    ga, unit = grid([a])
    gb, _ = grid([b])
    if mode == "Side by side":
        pos = np.r_[ga[ga > 0], gb[gb > 0]]
        if pos.size == 0:
            st.info("No data for this selection.")
            st.stop()
        zmin, zmax = float(pos.min()), float(np.quantile(pos, 0.995))
        fig = make_subplots(rows=1, cols=2, subplot_titles=(a, b), horizontal_spacing=0.06)
        fig.add_trace(heatmap(ga, unit, zmin, zmax), row=1, col=1)
        fig.add_trace(heatmap(gb, unit, zmin, zmax, showscale=False), row=1, col=2)
        st.plotly_chart(finish(fig, 2), width="stretch")
        st.caption("Both maps use the same color scale.")
    else:
        sa, sb = ga.sum(), gb.sum()
        if sa == 0 or sb == 0:
            st.info("One of the classes has no data in this selection.")
            st.stop()
        diff = 100 * (ga / sa - gb / sb)
        lim = float(np.quantile(np.abs(diff[diff != 0]), 0.99))
        fig = go.Figure(heatmap(diff, "percentage points", -lim, lim, diverging=True))
        fig.update_layout(title=f"Share of all {a} minus share of all {b} (red: more {a}, blue: more {b})")
        st.plotly_chart(finish(fig, 1), width="stretch")
        st.caption("Each class is first turned into shares of its own total, so a busy class does not dominate.")

st.caption(f"Variant `{f['variant']}`, hours {hour_note} (the maps use whole hours), cell {cell:g} m. "
           "Coordinates are sensor meters; the OSM layer is aligned to about 2 m.")

# --- crossings: how much of each class's time is spent on each crossing
z = data.zones()
if z:
    st.subheader("Time spent on the crossings")
    d = dens[dens["hour"].isin(hours) & dens["cls"].isin(data.VRU)]
    x = -LIM + (d["ix"].to_numpy() + 0.5) * 0.5
    y = -LIM + (d["iy"].to_numpy() + 0.5) * 0.5
    rows = []
    for c in z["crossings"]:
        inside = zn.point_in_polygon(x, y, c["polygon"])
        row = {"crossing": c["id"], "road": c["road"], "area (m2)": c["area_m2"]}
        for cls in data.VRU:
            m = (d["cls"] == cls).to_numpy()
            tot = d.loc[m, "dwell_s"].sum()
            row[f"{cls} time (s)"] = int(d.loc[m & inside, "dwell_s"].sum())
            row[f"{cls} share"] = f"{d.loc[m & inside, 'dwell_s'].sum() / tot:.1%}" if tot else "-"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Share = time spent inside the crossing / all time of that class at K305 in the selected hours. "
               "Crossings were found from the data (zones.py) and need a team check.")
