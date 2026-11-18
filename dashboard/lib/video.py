"""Miovision video lookup: which file and offset show a given local time (29 Oct 2026, cameras SCU3K2 and SCU4YV).

Assumption (same as near_miss_analysis.map_timestamp_to_video): recording starts at 06:00 local time and each MP4
part (.001, .002, ...) holds exactly one hour. Check against the clock shown in the video.
"""
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = ROOT / "database" / "miovision" / "K305"
CAMERAS = ["SCU3K2", "SCU4YV"]
START_S, END_S = 6 * 3600, 13 * 3600
# The two cameras' clocks do not agree: SCU3K2's picture runs 24 s behind SCU4YV (seen in the footage, 2026-11-17).
# Seconds added to each camera's video time; adjustable per session in the sidebar ("Camera sync").
CAMERA_OFFSET_S = {"SCU3K2": 24.0, "SCU4YV": 0.0}
# Video against the sensor and signal data: seconds added to the data time to find the same moment in the video
# (seen in the footage, 2026-11-17). Default of the Replay page's "Video offset"; also used by Video and Video check.
SENSOR_OFFSET_S = -79.0


def cam_offset(camera):
    return float(st.session_state.get(f"cam_sync_{camera}", CAMERA_OFFSET_S[camera]))


def offset_controls():
    """Sidebar inputs for the per-camera offsets. Kept in a plain session key so they survive page switches."""
    with st.sidebar.expander("Camera sync"):
        for cam in CAMERAS:
            st.session_state[f"cam_sync_{cam}"] = st.number_input(
                f"{cam} offset (s)", value=cam_offset(cam), step=1.0,
                help="Seconds added to this camera's video time. Positive if its picture runs behind the other camera "
                     "(or behind the sensors).")


def video_for(day, local_s, camera):
    """(path or None, offset seconds) for a local time of day in seconds, including the camera's sync offset."""
    local_s = local_s + cam_offset(camera)
    if not START_S <= local_s < END_S:
        return None, None
    part = int((local_s - START_S) // 3600) + 1
    offset = int(local_s - START_S - (part - 1) * 3600)
    folder = VIDEO_DIR / day.replace("-", "_") / f"Standard_{camera}_{day}_0600"
    path = folder / f"Standard_{camera}_{day}_0600.{part:03d}.mp4"
    return (path if path.exists() else None), offset


def hms(s):
    s = int(s)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def parse_hms(text):
    h, m, s = (int(x) for x in text.strip().split(":"))
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError(text)
    return h * 3600 + m * 60 + s
