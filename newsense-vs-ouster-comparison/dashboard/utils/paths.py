"""Where the dashboard finds its inputs. Plain Python (no Streamlit), so the launcher, build scripts, tests and video server can import it.

The prepared dashboard data (data/) and inputs (inputs/) ship with the dashboard, so NO dataset is needed to run it.
Camera video: put the MP4 files into dashboard/videos/ (see QUICK_START.md), or point to a full copy of the dataset folder
`all_data_for_four_teams` (only needed for video or to rebuild data/). The dataset folder is looked up in this order:
  1. environment variable K305_RAW_DATA_DIR
  2. dashboard/config/local_paths.json  {"raw_data_dir": "..."}   (written by `python run_dashboard.py --dataset PATH`; not in Git)
  3. fallback ~/Downloads/K305_Traffic_Data/all_data_for_four_teams

Everything else ships with the repository; advanced overrides: K305_OUTPUTS_DIR (derived analysis inputs), K305_V2_DIR (V2 package).
Only locations are configured here; no value or calculation changes.
"""
import os, json
DASH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.dirname(DASH)                      # newsense-vs-ouster-comparison/
LOCAL_CONFIG = os.path.join(DASH, 'config', 'local_paths.json')
DEFAULT_RAW = os.path.join(os.path.expanduser('~'), 'Downloads', 'K305_Traffic_Data', 'all_data_for_four_teams')
def _env(k):
    v = os.environ.get(k, '').strip().strip('"')
    return os.path.expanduser(v) if v else None
def _local(k):
    try:
        with open(LOCAL_CONFIG, encoding='utf-8') as f: v = (json.load(f).get(k) or '').strip()
        return os.path.expanduser(v) if v else None
    except (OSError, ValueError): return None
def raw_source():
    """(path, how it was configured) of the original dataset."""
    if _env('K305_RAW_DATA_DIR'): return _env('K305_RAW_DATA_DIR'), 'environment variable K305_RAW_DATA_DIR'
    if _local('raw_data_dir'): return _local('raw_data_dir'), 'config/local_paths.json'
    return DEFAULT_RAW, 'default location (not configured)'
OUT = _env('K305_OUTPUTS_DIR') or os.path.join(DASH, 'inputs')          # derived analysis inputs (ship with the dashboard)
S4 = os.path.join(OUT, 'stage4_traffic_analysis')
V2 = _env('K305_V2_DIR') or os.path.join(DASH, 'inputs', 'FINAL_PACKAGE_V2')   # corrected V2 results used by the dashboard
RAW = os.path.normpath(raw_source()[0])
DATA = os.path.join(DASH, 'data')                     # prepared dashboard data (ships with the dashboard; rebuildable from the dataset)
VIDEOS = _env('K305_VIDEO_DIR') or os.path.join(DASH, 'videos')   # simple place for the camera MP4 files (not in Git)
def find_video(subdir, name):
    """Location of one camera MP4: inside the configured dataset folder, else in dashboard/videos/ (flat or in its original folder)."""
    for p in (os.path.join(RAW, subdir, name), os.path.join(VIDEOS, name), os.path.join(VIDEOS, os.path.basename(subdir), name)):
        if os.path.isfile(p): return p
    return os.path.join(VIDEOS, name)
CAM1_DIR = 'mio vision/K305/2026_10_29/Standard_SCU3K2_2026-10-29_0600'
V2_PREFIX = 'FINAL_PACKAGE_V2/'
def resolve(rel):
    """Path of an entry of config/sources.json: V2 files resolve against V2, everything else against OUT."""
    return os.path.join(V2, rel[len(V2_PREFIX):]) if rel.startswith(V2_PREFIX) else os.path.join(OUT, rel)
# Files of the original dataset the dashboard uses (relative to RAW). Used by run_dashboard.py.
REQUIRED_FOR_BUILD = {
    'Newsense object lists, 29 Oct (288 JSON, ~4.6 GB)': ('newsense/object_list/k305_object_list_2026-10-29_aggregation_5min', '.json'),
    'Ouster object logs (14 .gz, ~0.6 GB; PCAP folders not needed)': ('ouster/ouster', '.gz'),
}
REQUIRED_FOR_VIDEO = {
    'Camera 1 video SCU3K2, 29 Oct (~1.2 GB)': ('mio vision/K305/2026_10_29/Standard_SCU3K2_2026-10-29_0600', '.mp4'),
    'Camera 2 video SCU4YV, 29 Oct (~1.2 GB)': ('mio vision/K305/2026_10_29/Standard_SCU4YV_2026-10-29_0600', '.mp4'),
}
