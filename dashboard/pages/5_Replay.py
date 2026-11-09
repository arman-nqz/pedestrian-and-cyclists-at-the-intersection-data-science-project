"""Replay: the tracked objects on the map, with both Miovision videos following the player's clock."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from lib import data, filters, replay, video  # noqa: E402

st.set_page_config(page_title="Replay - K305", layout="wide")
st.title("Replay with video")
f = filters.sidebar(show_time=False, show_classes=False)

try:
    meta = data.meta()
except data.MissingData as e:
    st.error(str(e))
    st.stop()
day = meta["day"]
variant = f["variant"]
if not (data.DATA / "replay" / variant).exists():
    st.warning(f"No replay files for `{variant}`; showing `clean`. Build others with "
               f"`python build_dashboard_data.py --steps replay --replay-variants {variant}`.")
    variant = "clean"

st.session_state.setdefault("video_time", 7 * 3600 + 20 * 60)  # shared with the Video and Signals pages
c1, c2, c3, c4, c5 = st.columns([1.2, 0.8, 0.5, 0.5, 1])
text = c1.text_input("Local time (HH:MM:SS)", value=video.hms(st.session_state["video_time"]))
try:
    st.session_state["video_time"] = video.parse_hms(text)
except ValueError:
    st.error("Use the form HH:MM:SS, for example 07:21:30.")
minutes = c2.select_slider("Window (min)", options=[5, 10], value=5)
t = st.session_state["video_time"]
start = t // replay.CHUNK_S * replay.CHUNK_S
if c3.button("◀ Previous"):
    st.session_state["video_time"] = max(0, start - minutes * 60)
    st.rerun()
if c4.button("Next ▶"):
    st.session_state["video_time"] = start + minutes * 60
    st.rerun()
ev_s = (st.session_state.get("replay_event") or {}).get("local_s", -1)
if start + minutes * 60 <= ev_s < start + minutes * 60 + 10:  # event just past the window end: show the next 5 min too
    minutes += 5
# one window stays inside one video file (files are one hour each)
minutes = min(minutes, (3600 - start % 3600) // 60)
tweak = c5.number_input("Video offset (s)", value=0.0, step=0.5,
                        help="Add this to the video time if the picture runs ahead (negative) or behind (positive) of the tracks.")

win = replay.window(variant, start, minutes)
if win is None:
    st.info(f"No tracks for {video.hms(start)}.")
    st.stop()
_, voff = video.video_for(day, start, video.CAMERAS[0])
paths = [video.video_for(day, t, cam)[0] for cam in video.CAMERAS]
sync = voff is not None and any(paths)

event = st.session_state.get("replay_event")
left, right = st.columns([3, 2])
with left:
    if event:
        e1, e2 = st.columns([4, 1])
        e1.markdown(f"Highlighted event at **{video.hms(event['local_s'])}**: {event['label']} (red rings, "
                    "dashed line between the two tracks)")
        if e2.button("Clear"):
            del st.session_state["replay_event"]
            st.rerun()
    # our own HTML (assets/player.html + prebuilt data); st.iframe keeps same-origin access for the video sync
    st.iframe(replay.player_html(win, t - start, (voff + tweak) if sync else None, event), height="content")
    st.caption(f"{day}, {video.hms(start)} to {video.hms(start + minutes * 60)} local time, variant `{variant}`, "
               f"{len(win['T']):,} frames. Circles: pedestrians, cyclists, motorcycles (with heading); boxes: motor vehicles.")
with right:
    for cam, p in zip(video.CAMERAS, paths):
        st.markdown(f"**Camera {cam}**")
        if p is None:
            st.info("No video for this time (or the file is not in `database/miovision`).")
        else:
            st.video(str(p), start_time=int(video.video_for(day, t, cam)[1]), muted=True)
    if sync:
        st.caption("Play, pause, the slider and the speed in the player also drive both videos. Untick "
                   "'Video follows' in the player to use the video controls on their own.")
