"""Tests for the NSE vs Ouster comparison helpers (synthetic data, no files needed).

Run from the repo root:   python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import nse_ouster as no  # noqa: E402
import ouster_reader as orr  # noqa: E402


def synthetic_scene(seed=0, frames=300):
    """NSE rows of cars driving on two crossing roads plus a few pedestrians, 10 Hz."""
    rng = np.random.default_rng(seed)
    rows = []
    cars = []
    for k in range(40):  # cars entering at random times on two roads (different directions -> rotation is identifiable)
        horizontal = k % 2 == 0
        t_in = rng.uniform(0, max(frames / 10 - 8, 0.5))
        speed = rng.uniform(6, 12) * (1 if rng.random() < 0.5 else -1)
        lane = rng.uniform(-6, 6)
        cars.append((k, horizontal, t_in, speed, lane))
    for f in range(frames):
        t = 1000.0 + f / 10
        for k, horizontal, t_in, speed, lane in cars:
            s = (t - 1000.0 - t_in) * speed
            if t - 1000.0 < t_in or abs(s) > 40:
                continue
            x, y = (s - 20 * np.sign(speed), lane) if horizontal else (lane + 5, s - 20 * np.sign(speed))
            vx, vy = (speed, 0.0) if horizontal else (0.0, speed)
            rows.append((t, k, "Car", x, y, vx, vy))
        for p in range(3):
            rows.append((t, 100 + p, "Pedestrian", -10 + p * 3 + f * 0.01, 12.0, 1.0, 0.0))
    return pd.DataFrame(rows, columns=["t", "track_id", "class_name", "x", "y", "vx", "vy"])


def to_ouster(n, rot_deg, shift):
    """Inverse of no.to_nse: express NSE rows in a made-up Ouster frame."""
    R = no.rot(rot_deg)  # p = R(rot) (q - shift)
    p = (n[["x", "y"]].to_numpy() - shift) @ R.T
    v = n[["vx", "vy"]].to_numpy() @ R.T
    o = n.copy()
    o["x"], o["y"], o["vx"], o["vy"] = p[:, 0], p[:, 1], v[:, 0], v[:, 1]
    o["t"] = o["t"] + 0.03  # frames of the two systems are not exactly simultaneous
    o["x"], o["y"] = o["x"] + 0.03 * o["vx"], o["y"] + 0.03 * o["vy"]
    o["yaw"] = 0.0
    return o


class TransformTests(unittest.TestCase):
    def test_recovers_rotation_and_shift(self):
        n = synthetic_scene()
        o = to_ouster(n, 171.2, np.array([-18.6, 1.7]))
        tr = no.estimate_transform(n, o, step=2)
        self.assertAlmostEqual(tr["rotation_deg"] % 360, 171.2, delta=0.3)
        self.assertAlmostEqual(tr["shift_m"][0], -18.6, delta=0.2)
        self.assertAlmostEqual(tr["shift_m"][1], 1.7, delta=0.2)
        self.assertLess(tr["median_residual_m"], 0.2)

    def test_to_nse_round_trip(self):
        n = synthetic_scene(frames=20)
        o = to_ouster(n, 96.0, np.array([-7.4, -12.1]))
        back = no.to_nse(o.assign(t=n["t"], x=o["x"] - 0.03 * o["vx"], y=o["y"] - 0.03 * o["vy"]),
                         {"rotation_deg": 96.0, "shift_m": [-7.4, -12.1]})
        np.testing.assert_allclose(back[["x", "y"]].to_numpy(), n[["x", "y"]].to_numpy(), atol=1e-6)

    def test_matching_pairs_same_objects(self):
        n = synthetic_scene(frames=50)
        tr = {"rotation_deg": 30.0, "shift_m": [5.0, -3.0]}
        on = no.to_nse(to_ouster(n, 30.0, np.array([5.0, -3.0])), tr)
        m = no.match_frames(n, on)
        paired = m.dropna(subset=["dist_m"])
        self.assertGreater(len(paired) / (m["nse_group"] != "none").sum(), 0.95)
        self.assertLess(paired["dist_m"].median(), 0.05)


class ClassTests(unittest.TestCase):
    def test_ouster_class_mapping(self):
        self.assertEqual(orr.map_class("PERSON", "pedestrian"), "Pedestrian")
        self.assertEqual(orr.map_class("BICYCLE", "bicycle"), "Cyclist")
        self.assertEqual(orr.map_class("LARGE_VEHICLE", "bus"), "Bus")
        self.assertEqual(orr.map_class("LARGE_VEHICLE", "trailer"), "Truck")
        self.assertEqual(orr.map_class("UNKNOWN", ""), "Unknown")

    def test_groups(self):
        self.assertEqual(list(no.group(["Car", "Van", "Pedestrian", "Motorcycle", "Unknown", "Bus"])),
                         ["Vehicle", "Vehicle", "Pedestrian", "Motorcycle", "Unknown", "Vehicle"])


if __name__ == "__main__":
    unittest.main()
