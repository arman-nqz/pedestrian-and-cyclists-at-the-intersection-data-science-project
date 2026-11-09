"""K305 VRU dashboard: Overview page.  Run:  streamlit run dashboard/Overview.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from lib import data, filters  # noqa: E402

st.set_page_config(page_title="K305 VRU dashboard", layout="wide")

st.title("Pedestrians and cyclists at K305: when and where?")
st.caption("Roadside LiDAR object lists, intersection K305 (Dr.-Willi-Reiland-Ring / Würzburger Straße, Aschaffenburg), "
           "14 October 2026, 10 Hz.")

f = filters.sidebar(show_time=False, show_classes=False)

try:
    meta = data.meta()
    tt = data.tracks(f["variant"])
    cn = data.counts(f["variant"])
except data.MissingData as e:
    st.error(str(e))
    st.stop()

if meta.get("partial"):
    st.warning(f"This data bundle is a partial build ({meta['window']}). Numbers do not cover the whole day.")

st.subheader(f"Tracks per class (variant `{f['variant']}`)")
cols = st.columns(len(data.VRU) + 1)
for c, cls in zip(cols, data.VRU):
    n = int((tt["cls"] == cls).sum())
    s = cn[(cn["cls"] == cls) & (cn["arm"] == "all")].copy()
    s["hour"] = s["bin"] // 4
    peak = int(s.groupby("hour")["started"].sum().idxmax()) if n else None
    c.metric(cls, f"{n:,}", help="tracks over the whole day")
    if peak is not None:
        c.caption(f"busiest hour {peak:02d}:00 to {peak + 1:02d}:00")
vru_share = tt["cls"].isin(data.VRU).mean()
cols[-1].metric("VRU share of tracks", f"{vru_share:.0%}", help="pedestrian, cyclist and motorcycle tracks / all tracks")

st.subheader("Key findings")
findings = data.content("findings.md")
st.markdown(findings or "_No findings written yet: add `dashboard/content/findings.md`._")

filters.limits_box()

with st.expander("Build information"):
    st.json({k: meta[k] for k in ("built_utc", "git_commit", "rows", "default_variant", "partial") if k in meta})
