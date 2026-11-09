"""NSE vs Ouster BlueCity on the four shared 10-minute windows (29 Oct 2026)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from lib import data, plots  # noqa: E402

st.set_page_config(page_title="NSE vs Ouster - K305", layout="wide")
st.title("NSE vs Ouster BlueCity: do they see the same road users?")

try:
    meta = data.compare("meta.json")
    summ = data.compare("summary.parquet")
    conf = data.compare("confusion.parquet")
    hist = data.compare("dist_hist.parquet")
    cnt = data.compare("counts_1s.parquet")
    dens = data.compare("density.parquet")
    area = data.compare("common_area.parquet")
    trk = data.compare("tracks.parquet")
except data.MissingData as e:
    st.error(str(e))
    st.stop()

GROUPS = ["Pedestrian", "Cyclist", "Motorcycle", "Vehicle", "Unknown"]
SYS_COLORS = {"NSE": "#2b7bd6", "Ouster": "#e8791b"}
wins = {w["id"]: f"{w['id']}  {w['start_local']} to {w['end_local']}" for w in meta["windows"]}
with st.sidebar:
    st.markdown("### Window")
    wid = st.radio("10-minute window (29 Oct, CET)", list(wins) + ["all"], format_func=lambda k: wins.get(k, "All four"),
                   label_visibility="collapsed")
sel = list(wins) if wid == "all" else [wid]

tr = meta["transforms"]
tr_txt = "; ".join(f"{k}: {tr[k]['rotation_deg']:.2f} deg, ({tr[k]['shift_m'][0]:.2f}, {tr[k]['shift_m'][1]:.2f}) m, "
                   f"residual {tr[k]['median_residual_m']:.2f} m" for k in sel)
if len(meta.get("frame_groups", [])) > 1:
    st.warning("The Ouster coordinate frame changed during the morning (window groups "
               f"{meta['frame_groups']}), probably when Ouster was restarted for the 08:18 recording. Each window uses "
               "its own transform.")
st.caption(
    f"Ouster positions are moved into the NSE frame with a rotation and shift found from moving vehicles seen by both "
    f"({tr_txt}). Detections are paired frame by frame "
    f"when they are mutual nearest neighbours within {meta['radius_m']} m, whatever their class. Only the area both "
    f"systems cover is compared. NSE detections with a score below {meta['min_score_nse']} are left out; Ouster has no "
    "score filter.")

# --- headline table
s = summ[summ["window"].isin(sel)]
if wid == "all":
    w = s["frames"]
    agg = {}
    for g, sub in s.groupby("group"):
        ww = sub["frames"]
        agg[g] = {c: (np.average(sub[c].dropna(), weights=ww[sub[c].notna()]) if sub[c].notna().any() else None)
                  for c in ["nse_per_frame", "ouster_per_frame", "nse_matched_share", "ouster_matched_share",
                            "same_group_share", "median_dist_m"]}
    s = pd.DataFrame(agg).T.reindex(GROUPS).reset_index().rename(columns={"index": "group"})
else:
    s = s.set_index("group").reindex(GROUPS).reset_index()
area_m2 = summ[summ["window"].isin(sel)]["common_area_m2"].mean()

st.subheader("Detections per frame and how many are seen by both")
show = s[["group", "nse_per_frame", "ouster_per_frame", "nse_matched_share", "ouster_matched_share", "same_group_share",
          "median_dist_m"]].copy()
for c in ["nse_matched_share", "ouster_matched_share", "same_group_share"]:
    show[c] = show[c].map(lambda v: f"{v:.0%}" if pd.notna(v) else "-")
show = show.rename(columns={"nse_per_frame": "NSE per frame", "ouster_per_frame": "Ouster per frame",
                            "nse_matched_share": "NSE seen by Ouster", "ouster_matched_share": "Ouster seen by NSE",
                            "same_group_share": "same class (when paired)", "median_dist_m": "median distance (m)"})
st.dataframe(show, hide_index=True, width="stretch")
st.caption(f"Common area about {area_m2:.0f} m2. 'NSE seen by Ouster' = share of NSE detections with an Ouster detection "
           "within the radius; 'same class' = share of those pairs where both systems give the same group.")

# --- confusion
st.subheader("When both see an object, which class does each give it?")
c = conf[conf["window"].isin(sel)].groupby(["nse_group", "ouster_group"])["n"].sum().unstack(fill_value=0)
rows = [g for g in GROUPS + ["none"] if g in c.index]
cols = [g for g in GROUPS + ["none"] if g in c.columns]
c = c.reindex(index=rows, columns=cols, fill_value=0)
share = c.div(c.sum(axis=1).replace(0, np.nan), axis=0)
fig = go.Figure(go.Heatmap(z=share.to_numpy(), x=[f"Ouster: {x}" for x in cols], y=[f"NSE: {y}" for y in rows],
                           customdata=c.to_numpy(), colorscale="Blues", zmin=0, zmax=1,
                           text=[[f"{v:.0%}" if pd.notna(v) else "" for v in r] for r in share.to_numpy()],
                           texttemplate="%{text}", colorbar=dict(title="share of row"),
                           hovertemplate="%{y} / %{x}<br>%{customdata:,} detections (%{text})<extra></extra>"))
fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), yaxis_autorange="reversed")
st.plotly_chart(fig, width="stretch")
st.caption("Rows: class given by NSE; columns: class given by Ouster; 'none' = not seen by the other system. Each row "
           "adds up to 100%. Ouster has no motorcycle class and labels many objects UNKNOWN.")

# --- time series
st.subheader("Detections over time")
g_sel = st.radio("Group", GROUPS[:4], horizontal=True)
ts = cnt[cnt["window"].isin(sel) & (cnt["group"] == g_sel)].copy()
fig = make_subplots(rows=len(sel), cols=1, shared_xaxes=True, subplot_titles=[wins[x] for x in sel], vertical_spacing=0.08)
for r, w_ in enumerate(sel, start=1):
    for sysname in ("NSE", "Ouster"):
        d = ts[(ts["window"] == w_) & (ts["system"] == sysname)].sort_values("second")
        fig.add_trace(go.Scatter(x=d["second"] / 60, y=d["per_frame"], mode="lines", name=sysname, showlegend=(r == 1),
                                 line=dict(color=SYS_COLORS[sysname], width=1.6)), row=r, col=1)
fig.update_layout(height=240 * len(sel), margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))
fig.update_xaxes(title_text="minutes into the window", row=len(sel), col=1)
fig.update_yaxes(title_text="per frame")
st.plotly_chart(fig, width="stretch")

# --- maps
st.subheader("Where each system sees them")
g_map = st.radio("Group ", GROUPS, horizontal=True, index=0)
dd = dens[dens["window"].isin(sel) & (dens["group"] == g_map)]
n_cells = int(2 * 46 / 0.5)
grids = {}
for sysname in ("NSE", "Ouster"):
    g = np.zeros((n_cells, n_cells))
    sub = dd[dd["system"] == sysname]
    np.add.at(g, (sub["iy"].to_numpy(), sub["ix"].to_numpy()), sub["dwell_s"].to_numpy())
    grids[sysname] = g
pos = np.r_[grids["NSE"][grids["NSE"] > 0], grids["Ouster"][grids["Ouster"] > 0]]
if pos.size:
    centers = -46 + (np.arange(n_cells) + 0.5) * 0.5
    zmax = np.log10(np.quantile(pos, 0.995))
    fig = make_subplots(rows=1, cols=2, subplot_titles=("NSE", "Ouster (moved into the NSE frame)"), horizontal_spacing=0.06)
    for k, sysname in enumerate(("NSE", "Ouster"), start=1):
        g = grids[sysname]
        z = np.where(g > 0, np.log10(np.where(g > 0, g, 1)), np.nan)
        fig.add_trace(go.Heatmap(x=centers, y=centers, z=z, customdata=g, zmin=np.log10(pos.min()), zmax=zmax,
                                 colorscale="Magma", showscale=(k == 2), colorbar=dict(title="s (log10)"),
                                 hovertemplate="x %{x:.1f}, y %{y:.1f}<br>%{customdata:.1f} s<extra></extra>"), row=1, col=k)
        plots.base_map(fig, show_zones=False, row=1, col=k)
        mask = area[area["window"] == sel[0]]
        fig.update_xaxes(range=[-46, 46], constrain="domain", row=1, col=k)
        fig.update_yaxes(range=[-46, 46], constrain="domain", scaleanchor=f"x{k if k > 1 else ''}", row=1, col=k)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=40, b=10), showlegend=False, plot_bgcolor="#f4f6f8")
    st.plotly_chart(fig, width="stretch")
    st.caption("Time spent per 0.5 m cell in the selected window(s), same color scale for both. The maps are not limited "
               "to the common area, so differences at the edges show where one system sees further.")
else:
    st.info("No detections of this group in the selected window(s).")

# --- distances and tracks
left, right = st.columns(2)
with left:
    st.subheader("Distance between paired detections")
    h = hist[hist["window"].isin(sel)].groupby(["group", "dist_m"])["n"].sum().reset_index()
    fig = go.Figure()
    for g in GROUPS[:4]:
        d = h[h["group"] == g]
        if len(d):
            fig.add_trace(go.Scatter(x=d["dist_m"], y=d["n"] / d["n"].sum(), mode="lines", name=g,
                                     line=dict(color=data.COLORS.get(g, "#7f8c99"))))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="distance (m)", yaxis_title="share",
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Tracks: how fragmented is each system?")
    t = trk[trk["window"].isin(sel)].groupby(["stage", "group", "system"]).agg(
        tracks=("tracks", "sum"), median_duration_s=("median_duration_s", "median")).reset_index()
    piv = t.pivot_table(index=["group", "stage"], columns="system", values=["tracks", "median_duration_s"])
    piv.columns = [f"{a.replace('median_duration_s', 'median s')} {b}" for a, b in piv.columns]
    piv = piv.reindex([(g, s_) for g in GROUPS for s_ in ("raw ids", "stitched", "clean")]).dropna(how="all")
    st.dataframe(piv.round(1), width="stretch")
    st.caption("Tracks in the common area: raw ids from each system, then after our stitching and the `clean` filter. "
               "Fewer, longer tracks mean less fragmentation.")

st.info("**Read with care.** Pairing uses distance only, so two people walking together can be swapped. Ouster's "
        "UNKNOWN objects and the missing motorcycle class make class shares look worse than they are. Only four "
        "10-minute windows in the morning are compared.")
