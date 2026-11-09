"""Miovision video lookup: which file and offset show a given local time (29 Oct 2026, cameras SCU3K2 and SCU4YV).

Assumption (same as near_miss_analysis.map_timestamp_to_video): recording starts at 06:00 local time and each MP4
part (.001, .002, ...) holds exactly one hour. Check against the clock shown in the video.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = ROOT / "database" / "miovision" / "K305"
CAMERAS = ["SCU3K2", "SCU4YV"]
START_S, END_S = 6 * 3600, 13 * 3600


def video_for(day, local_s, camera):
    """(path or None, offset seconds) for a local time of day in seconds."""
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
