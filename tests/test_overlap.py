"""overlaps(): a pedestrian and a car crossing the same cell 1 s apart give PET 1 s; 5 s apart gives nothing.

Run from the repo root:   python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import build_dashboard_data as b  # noqa: E402


def walk(trk, cls, t0, x0, y0, vx, vy, n=20):
    t = t0 + 0.1 * np.arange(n)
    return pd.DataFrame({"trk": trk, "cls": cls, "t": t, "x": x0 + vx * (t - t0), "y": y0 + vy * (t - t0)})


class OverlapTests(unittest.TestCase):
    def test_pet_in_shared_cell(self):
        b.UTC_OFFSET_S = 3600
        t0 = 1_793_260_000.0
        ped = walk(1, "Pedestrian", t0, 0.5, -3, 0, 1.5, n=40)      # passes (0.5, 0.5) at about t0 + 2.3 s
        car = walk(2, "Car", t0 + 3.4, -5, 0.5, 10, 0, n=12)        # passes (0.5, 0.5) at about t0 + 3.95 s
        far = walk(3, "Car", t0 + 9, -5, 0.5, 10, 0, n=12)          # same cell, 6 s later
        o = b.overlaps(pd.concat([ped, car, far]), cell=1.0, max_pet=3.0)
        cell = o[(o["ix"] == int((0.5 + b.LIM) // 1)) & (o["iy"] == int((0.5 + b.LIM) // 1))]
        self.assertEqual(int(cell["pairs"].sum()), 1)
        self.assertEqual(cell["cls"].iat[0], "Pedestrian")
        self.assertLessEqual(float(cell["pet_bin"].iat[0]), 1.5)


if __name__ == "__main__":
    unittest.main()
