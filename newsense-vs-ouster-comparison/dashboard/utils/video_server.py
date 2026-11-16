"""Read-only local video server for the ORIGINAL MioVision recordings (no copies, no transcoding).
Serves only the whitelisted files listed in data/video_index.json (SCU3K2) and config/cameras.json (SCU4YV), on 127.0.0.1, with HTTP Range support (needed for seeking).
Started automatically by the dashboard (utils/video_server.ensure_running) or stand-alone: python utils/video_server.py [port]
"""
import os, re, sys, json, threading, socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try: from .paths import find_video, CAM1_DIR          # package import (dashboard)
except ImportError: from paths import find_video, CAM1_DIR   # stand-alone: python utils/video_server.py
PORT = 8765
def whitelist():
    idx = json.load(open(os.path.join(HERE, 'data', 'video_index.json'), encoding='utf-8'))
    files = {p['static_name']: find_video(CAM1_DIR, p['file']) for p in idx['parts'].values()}
    cams = os.path.join(HERE, 'config', 'cameras.json')
    if os.path.exists(cams):
        for c in json.load(open(cams, encoding='utf-8'))['cameras'].values():
            for p in (c.get('parts') or {}).values(): files[p['static_name']] = find_video(c['video_dir'], p['file'])
    return files
class Handler(BaseHTTPRequestHandler):
    files = {}
    def log_message(self, *a): pass
    def _headers(self, code, length, extra=()):
        self.send_response(code); self.send_header('Content-Type', 'video/mp4'); self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Content-Length', str(length))
        for k, v in extra: self.send_header(k, v)
        self.end_headers()
    def do_HEAD(self): self.do_GET(head=True)
    def do_GET(self, head=False):
        name = self.path.lstrip('/').split('?')[0]
        path = self.files.get(name)
        if not path or not os.path.isfile(path): self.send_error(404); return
        size = os.path.getsize(path); rng = self.headers.get('Range'); start, end = 0, size - 1; code = 200; extra = []
        m = re.match(r'bytes=(\d*)-(\d*)', rng or '')
        if m:
            if m.group(1): start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
            else: start = size - int(m.group(2))
            end = min(end, size - 1)
            if start > end: self.send_error(416); return
            code = 206; extra = [('Content-Range', f'bytes {start}-{end}/{size}')]
        self._headers(code, end - start + 1, extra)
        if head: return
        with open(path, 'rb') as f:                       # read-only
            f.seek(start); left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError): pass
def port_open(port):
    with socket.socket() as s: return s.connect_ex(('127.0.0.1', port)) == 0
def ensure_running(port=PORT):
    if port_open(port): return port
    Handler.files = whitelist(); srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start(); return port
if __name__ == '__main__':
    p = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    Handler.files = whitelist(); print('serving', list(Handler.files), 'on', p); ThreadingHTTPServer(('127.0.0.1', p), Handler).serve_forever()
