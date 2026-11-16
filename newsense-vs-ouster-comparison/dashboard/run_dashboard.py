"""Cross-platform launcher for the K305 Newsense vs Ouster dashboard (macOS, Windows, Linux).
Normally started by START_DASHBOARD.command (macOS) or START_DASHBOARD.bat (Windows).

  python run_dashboard.py                 start the dashboard and open it in the browser
  python run_dashboard.py --check         only check the installation, prepared data and camera videos
  python run_dashboard.py --no-browser    start without opening a browser tab
  python run_dashboard.py --port 8502     preferred port (default 8501; the next free port is used if busy)

Advanced (only with the original dataset `all_data_for_four_teams`):
  python run_dashboard.py --dataset "PATH"   save the dataset location (config/local_paths.json, not in Git)
  python run_dashboard.py --rebuild          rebuild the prepared data in data/ from the dataset (about 3 minutes)
"""
import os, sys, json, time, socket, argparse, subprocess, importlib, importlib.util, urllib.request, webbrowser
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
STEPS = ['b1_extract', 'b2_segments', 'b3_matching', 'b3b_candidates', 'b4_aggregates', 'b5_video_events']
NEEDED_VIDEO_PARTS = ('002', '003')    # the parts covering the shared sensor period 29 Oct 07:12-08:35 (camera clocks lag 51-80 s)
def say(msg=''): print(msg, flush=True)
def count(folder, ext):
    try: return sum(1 for f in os.listdir(folder) if f.lower().endswith(ext))
    except OSError: return 0
def free_port(start):
    for p in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0: return p
    return start
def main():
    ap = argparse.ArgumentParser(description='K305 dashboard launcher')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--no-browser', action='store_true')
    ap.add_argument('--port', type=int, default=8501)
    ap.add_argument('--dataset', help='path of the folder all_data_for_four_teams (optional)')
    ap.add_argument('--rebuild', action='store_true', help='rebuild data/ from the dataset')
    a = ap.parse_args()
    if sys.version_info < (3, 11): sys.exit(f'Python 3.11 or newer is required (this is {sys.version.split()[0]}).')
    missing = [m for m in ('streamlit', 'pandas', 'numpy', 'plotly', 'pyarrow') if importlib.util.find_spec(m) is None]
    if missing: sys.exit(f'Missing packages: {", ".join(missing)}. Run:  python -m pip install -r requirements.txt')
    from utils import paths as P
    if a.dataset:
        d = os.path.abspath(os.path.expanduser(a.dataset.strip().strip('"')))
        if os.path.isdir(os.path.join(d, 'all_data_for_four_teams')): d = os.path.join(d, 'all_data_for_four_teams')
        if not os.path.isdir(d): sys.exit(f'Folder not found: {d}')
        with open(P.LOCAL_CONFIG, 'w', encoding='utf-8') as f: json.dump({'raw_data_dir': d}, f, indent=1)
        say(f'Saved dataset location: {d}'); os.environ.pop('K305_RAW_DATA_DIR', None); importlib.reload(P)
    # 1. prepared data + inputs (ship with the dashboard)
    need = ['candidates.parquet', 'candidate_members.parquet', 'segments.parquet', 'obs_seg_NS.parquet', 'obs_seg_OU.parquet', 'match_edges.parquet',
            'events.parquet', 'agg_minute.parquet', 'heat.parquet', 'class_transitions.parquet', 'background.json', 'video_index.json', 'frames.json']
    lacking = [f for f in need if not os.path.isfile(os.path.join(P.DATA, f))]
    say(f'Prepared dashboard data: {"ok" if not lacking else "MISSING " + ", ".join(lacking)}')
    say(f'Research inputs (V2):    {"ok" if os.path.isfile(os.path.join(P.V2, "V2_CHANGE_LOG.md")) else "MISSING (inputs/FINAL_PACKAGE_V2)"}')
    # 2. camera videos (optional)
    vi = {'parts': {}}
    if os.path.isfile(os.path.join(P.DATA, 'video_index.json')):
        with open(os.path.join(P.DATA, 'video_index.json'), encoding='utf-8') as f: vi = json.load(f)
    with open(os.path.join(HERE, 'config', 'cameras.json'), encoding='utf-8') as f: cam2 = json.load(f)['cameras']['SCU4YV']
    vids = [(P.CAM1_DIR, m['file']) for p, m in vi['parts'].items() if p in NEEDED_VIDEO_PARTS] + [(cam2['video_dir'], m['file']) for p, m in cam2['parts'].items() if p in NEEDED_VIDEO_PARTS]
    have = [(n, P.find_video(d, n)) for d, n in vids]; ok_v = [n for n, p in have if os.path.isfile(p)]
    say(f'Camera videos:           {len(ok_v)} of {len(have)} found' + ('' if len(ok_v) == len(have) else '  (video panels stay empty without them; everything else works)'))
    for n, p in have: say(f'   [{"ok" if os.path.isfile(p) else "--"}] {n}' + (f'   ({p})' if os.path.isfile(p) else ''))
    if len(ok_v) < len(have): say(f'   -> copy the missing MP4 files into: {P.VIDEOS}')
    # 3. optional rebuild from the original dataset
    if a.rebuild or lacking:
        raw, how = P.raw_source(); raw = os.path.normpath(raw)
        ok = all(count(os.path.join(raw, rel), ext) for rel, ext in P.REQUIRED_FOR_BUILD.values())
        if not ok:
            sys.exit('\nThe prepared data is missing and cannot be rebuilt without the original dataset.\n'
                     'Download the project again (data/ is part of it), or point to the dataset: python run_dashboard.py --dataset "PATH" --rebuild')
        if a.check: say(f'Dataset for rebuilding: {raw} (ok)'); return
        os.makedirs(P.DATA, exist_ok=True); say(f'\nRebuilding data/ from {raw} (about 3 minutes; the dataset is only read) ...')
        env = dict(os.environ, K305_RAW_DATA_DIR=raw)
        for s in STEPS:
            say(f'== {s}')
            r = subprocess.run([sys.executable, '-X', 'utf8', '-I', os.path.join(HERE, 'build', f'{s}.py')], cwd=HERE, env=env)
            if r.returncode: sys.exit(f'Build step {s} failed (exit code {r.returncode}).')
    if a.check: return
    # 4. start
    port = free_port(a.port); url = f'http://localhost:{port}'
    say(f'\nStarting the dashboard at {url}\nKeep this window open while presenting. Close it (or press Ctrl+C) to stop.\n')
    env = dict(os.environ, PYTHONUTF8='1')
    proc = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'streamlit', 'run', os.path.join(HERE, 'app.py'), '--server.port', str(port),
                             '--server.address', 'localhost',          # only this computer can open it (not others on the same Wi-Fi)
                             '--server.headless', 'true', '--browser.gatherUsageStats', 'false'], cwd=HERE, env=env)
    try:
        if not a.no_browser:
            for _ in range(120):
                if proc.poll() is not None: break
                try:
                    if urllib.request.urlopen(f'{url}/_stcore/health', timeout=1).read() == b'ok': webbrowser.open(url); break
                except Exception: time.sleep(0.5)
        sys.exit(proc.wait())
    except KeyboardInterrupt:
        proc.terminate(); proc.wait()
if __name__ == '__main__': main()
