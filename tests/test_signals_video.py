"""Tests for signals.py (synthetic signal log) and the video lookup.

Run from the repo root:   python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dashboard"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import signals as sg  # noqa: E402
from lib import video  # noqa: E402


def synthetic_log(seconds=3600, t0=1_000_000.0):
    """90 s cycle: F1/F2 green 0-20 s, F3 green 40-70 s, K1 green 20-60 s, plus a detector column."""
    t = t0 + np.arange(seconds)
    c = np.arange(seconds) % 90
    f12 = np.where(c < 20, "G", "R")
    f3 = np.where((c >= 40) & (c < 70), "G", "R")
    k1 = np.where((c >= 20) & (c < 60), "G", np.where(c == 60, "A", "R"))
    return pd.DataFrame({"t": t, "F1": f12, "F2": f12, "F3": f3, "K1": k1, "D1": (c % 7 == 0) * 100})


class SignalTests(unittest.TestCase):
    def test_groups_join_identical_columns_and_skip_detectors(self):
        g = sg.signal_groups(synthetic_log())
        self.assertEqual(g, {"F1": ["F1", "F2"], "F3": ["F3"], "K1": ["K1"]})

    def test_state_at(self):
        log = synthetic_log()
        st = sg.state_at(log, "F3", [log["t"].iat[0] + 45, log["t"].iat[0] + 10, log["t"].iat[0] + 10.9])
        self.assertEqual(list(st), ["G", "R", "R"])
        self.assertIsNone(sg.state_at(log, "F3", [log["t"].iat[0] - 5])[0])

    def test_infer_mapping_finds_the_serving_group_and_offset(self):
        log = synthetic_log()
        rng = np.random.default_rng(1)
        # people step onto crossing A 3 s after F3 turns green (sensor clock), 10% walk on red
        cycles = log["t"].iat[0] + 90 * np.arange(1, 38)
        on_green = cycles[:, None] + 40 + 3 + rng.uniform(0, 20, size=(len(cycles), 3))
        on_red = log["t"].iat[0] + rng.uniform(0, 3500, size=11)
        t_enter = np.r_[on_green.ravel(), on_red]
        entries = pd.DataFrame({"crossing": "A", "cls": "Pedestrian", "t_enter": t_enter})
        groups = sg.signal_groups(log)
        res = sg.infer_mapping(entries, log, {k: v for k, v in groups.items() if k.startswith("F")})
        best = res.iloc[0]
        self.assertEqual(best["group"], "F3")
        self.assertGreater(best["green_share"], 0.8)


class VideoTests(unittest.TestCase):
    def test_video_parts_and_offsets(self):
        day = "2026-10-29"
        _, off = video.video_for(day, 6 * 3600, "SCU3K2")
        self.assertEqual(off, 0)
        p, off = video.video_for(day, 8 * 3600 + 22 * 60 + 10, "SCU3K2")
        self.assertEqual(off, 22 * 60 + 10)
        if p is not None:
            self.assertTrue(p.name.endswith(".003.mp4"))
        self.assertEqual(video.video_for(day, 13 * 3600, "SCU3K2"), (None, None))
        self.assertEqual(video.video_for(day, 5 * 3600, "SCU3K2"), (None, None))

    def test_hms_round_trip(self):
        for s in (0, 3599, 7 * 3600 + 21 * 60 + 30):
            self.assertEqual(video.parse_hms(video.hms(s)), s)
        with self.assertRaises(ValueError):
            video.parse_hms("25:00:00")


class ReplayTests(unittest.TestCase):
    def test_window_merges_chunks_on_one_clock(self):
        from lib import replay
        start = 7 * 3600 + 20 * 60
        if not replay.chunk_path("clean", start).exists():
            self.skipTest("no replay data built")
        w = replay.window("clean", start, 10)
        self.assertEqual(w["local0"], start)
        self.assertTrue(all(b > a for a, b in zip(w["T"], w["T"][1:])))  # no jump back at the chunk border
        self.assertLess(w["T"][0], 1)
        self.assertGreater(w["T"][-1], 590)
        self.assertEqual(len(w["T"]), len(w["F"]))


if __name__ == "__main__":
    unittest.main()
