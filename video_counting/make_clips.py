"""Cut the Miovision video into one clip per counting minute and gate, with the gate line and the SENSOR clock drawn in.

The camera clocks run behind the LiDAR clocks, so a minute of sensor time is not the same minute on the video's
burned-in clock. Each clip is cut so its frames cover one sensor-time minute (plus 5 s either side, marked
"DON'T COUNT"), and the big yellow clock shows sensor time. Count by the yellow clock only.

Run: python video_counting/make_clips.py    (needs opencv-python, numpy; writes video_counting/clips/*.mp4)
"""
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "database" / "miovision" / "K305" / "2026_10_29"
OUT = Path(__file__).resolve().parent / "clips"

# Video burned-in clock = sensor (Ouster) time + offset. Measured 2026-11-19 by correlating per-second image motion
# with Ouster moving-object counts over 07:34:30-07:44 (peak r ~0.45), then checked on Ouster gate crossings.
# Accurate to about +-1 s: objects within ~1 s of a minute boundary may belong to the neighbouring minute.
OFFSET_S = {"SCU4YV": -80.0, "SCU3K2": -55.0}

# Ground plane (Ouster x, y in m, frame of analysisByArman GATES) -> 720x480 image pixels. Fitted by matching
# Ouster objects to video detections (SCU3K2: 480 matches, SCU4YV: 33 matches, final tolerance 18 px).
HOMOGRAPHY = {
    "SCU3K2": [[-7.289231363573728, 22.650816225135653, 381.6763973783354],
               [-6.208280398018221, -1.8837807383589524, 233.31858943580227],
               [-0.04342359481847898, 0.0074531175301440055, 1.0]],
    "SCU4YV": [[6.8174549205837245, -16.120552142142422, 594.1199551810968],
               [0.15519120494197733, -1.2063262933026364, 129.6035972267389],
               [0.028275187588203892, -0.0036299916122884547, 1.0]],
}

# gate -> (camera, end points in Ouster coordinates). gate_1 is unchanged from analysisByArman GATES.
# gate_2 is MOVED from ((-12,-10),(-6,-18)) (fog at the image edge, not countable) to the cycle/foot crossing over the
# main road, which SCU3K2 sees clearly. The line spans the crossing's full width and runs parallel to the car lanes
# (VRUs cross at 37 deg, cars drive at 127 deg), so only pedestrians and cyclists cross it.
GATES = {
    "gate_1": ("SCU4YV", ((-16.0, 4.0), (-4.0, 16.0))),
    "gate_2": ("SCU3K2", ((12.71, -7.69), (7.59, -0.9))),
}
MINUTES = [f"07:{m:02d}" for m in range(35, 44)]
MARGIN_S, SCALE = 5, 2


def hms(s):
    return f"{int(s) // 3600:02d}:{int(s) % 3600 // 60:02d}:{s % 60:04.1f}"


def make_clip(gate, minute):
    cam, ends = GATES[gate]
    line = cv2.perspectiveTransform(np.float32(ends).reshape(-1, 1, 2), np.array(HOMOGRAPHY[cam])).reshape(-1, 2)
    line = (line * SCALE).astype(int)
    h, m = map(int, minute.split(":"))
    s0 = h * 3600 + m * 60                                     # sensor-time start of the counting minute
    cap = cv2.VideoCapture(str(VIDEO / f"Standard_{cam}_2026-10-29_0600" / f"Standard_{cam}_2026-10-29_0600.002.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS)
    clock0 = 7 * 3600 + 1                                      # burned-in clock at frame 0 of clip .002 (07:00:01)
    f0 = int((s0 - MARGIN_S + OFFSET_S[cam] - clock0) * fps)
    f1 = int((s0 + 60 + MARGIN_S + OFFSET_S[cam] - clock0) * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{minute.replace(':', '')}_{gate}_{cam}.mp4"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (720 * SCALE, 480 * SCALE))
    for f in range(f0, f1):
        ok, img = cap.read()
        if not ok:
            raise RuntimeError(f"video ended early: {path.name} frame {f}")
        img = cv2.resize(img, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
        sensor = f / fps + clock0 - OFFSET_S[cam]
        inside = s0 <= sensor < s0 + 60
        cv2.line(img, tuple(line[0]), tuple(line[1]), (0, 0, 255), 3)
        cv2.putText(img, gate, tuple(line[1] + [8, -8]), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.rectangle(img, (0, 0), (720 * SCALE, 46), (0, 0, 0), -1)
        label = f"SENSOR {hms(sensor)}   COUNT MINUTE {minute}   {gate}" if inside else \
            f"SENSOR {hms(sensor)}   OUTSIDE {minute} - DON'T COUNT"
        cv2.putText(img, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255) if inside else (150, 150, 150), 2)
        out.write(img)
    out.release()
    return path


if __name__ == "__main__":
    for gate in GATES:
        for minute in MINUTES:
            print(make_clip(gate, minute), flush=True)
