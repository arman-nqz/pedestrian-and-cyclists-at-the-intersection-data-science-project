"""Video: watch any moment between 06:00 and 13:00 from both Miovision cameras, with signal states and nearby events."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import signals as sg  # noqa: E402
from lib import data, video  # noqa: E402

st.set_page_config(page_title="Video - K305", layout="wide")
st.title("Video")

try:
    meta = data.meta()
except data.MissingData as e:
    st.error(str(e))
    st.stop()
day, off = meta["day"], meta["utc_offset_s"]

if "t" in st.query_params:  # shareable links: ?t=07:21:30
    try:
        st.session_state.setdefault("video_time", video.parse_hms(st.query_params["t"]))
    except ValueError:
        pass
st.session_state.setdefault("video_time", 7 * 3600 + 20 * 60)

c1, c2, c3, c4 = st.columns([1.2, 0.5, 0.5, 2])
text = c1.text_input("Local time (HH:MM:SS)", value=video.hms(st.session_state["video_time"]))
try:
    st.session_state["video_time"] = video.parse_hms(text)
except ValueError:
    st.error("Use the form HH:MM:SS, for example 07:21:30.")
if c2.button("-10 s"):
    st.session_state["video_time"] -= 10
    st.rerun()
if c3.button("+10 s"):
    st.session_state["video_time"] += 10
    st.rerun()
t_local = st.session_state["video_time"]
st.query_params["t"] = video.hms(t_local)
c4.caption(f"{day}, {video.hms(t_local)} local time. Recordings cover 06:00 to 13:00. Assumption: each video file "
           "holds exactly one hour from the full hour; check the clock shown in the picture.")

cols = st.columns(2)
for col, cam in zip(cols, video.CAMERAS):
    path, offset = video.video_for(day, t_local, cam)
    with col:
        st.markdown(f"**Camera {cam}**")
        if path is None:
            st.info("No video for this time (or the file is not in `database/miovision`).")
        else:
            st.video(str(path), start_time=offset)
            st.caption(f"`{path.name}` from {video.hms(offset)}")

# --- signal states at that second
sig_path = data.DATA / "signals.parquet"
mp = data.CONFIG / "signal_mapping.json"
if sig_path.exists():
    sig = pd.read_parquet(sig_path)
    epoch = sig["t"].iat[0] + (t_local - 6 * 3600)
    groups = json.loads((data.DATA / "signal_groups.json").read_text(encoding="utf-8"))
    mapping = json.loads(mp.read_text(encoding="utf-8"))["crossings"] if mp.exists() else {}
    serves = {}
    for x, by in mapping.items():
        for cls, m in by.items():
            if m["clear"]:
                serves.setdefault(m["group"], set()).add(x)
    st.subheader("Signal states at this second")
    rows = [{"group": g, "switches with": ", ".join(members), "state": sg.STATES.get(str(sg.state_at(sig, g, [epoch])[0]), "-"),
             "serves (inferred)": ", ".join(sorted(serves.get(g, [])))} for g, members in groups.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# --- events nearby
ev_path = data.DATA / "events_published_ttc.parquet"
if ev_path.exists():
    ev = pd.read_parquet(ev_path)
    ev["local_s"] = ((ev["t"] + off) % 86400).astype(int)
    near = ev[(ev["local_s"] - t_local).abs() <= 120].sort_values("local_s")
    st.subheader("Near-miss events within 2 minutes (original pipeline)")
    if near.empty:
        st.caption("None.")
    else:
        near = near.assign(time=near["local_s"].map(video.hms))
        st.dataframe(near[["time", "interaction_type", "min_ttc_sec", "duration_sec", "x_mid", "y_mid"]],
                     hide_index=True, width="stretch")
        pick = st.selectbox("Jump to event", near["time"].tolist())
        if st.button("Go to event (5 s before)"):
            st.session_state["video_time"] = video.parse_hms(pick) - 5
            st.rerun()
