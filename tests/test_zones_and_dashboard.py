"""Tests for zones.py helpers, and a smoke test of the dashboard pages (skipped without built data or streamlit).

Run from the repo root:   python -m unittest discover -s tests -v
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import zones as zn  # noqa: E402

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]
ZONES = {
    "junction": {"center": [0.0, 0.0], "core_radius_m": 5.0,
                 "arms": [{"id": "E", "from_deg": 315, "to_deg": 45}, {"id": "N", "from_deg": 45, "to_deg": 135},
                          {"id": "W", "from_deg": 135, "to_deg": 225}, {"id": "S", "from_deg": 225, "to_deg": 315}]},
    "crossings": [{"id": "X1", "polygon": [[20, -2], [24, -2], [24, 2], [20, 2]]}],
}


class ZoneTests(unittest.TestCase):
    def test_point_in_polygon(self):
        inside = zn.point_in_polygon([5, 15, -1, 9.9], [5, 5, 5, 0.1], SQUARE)
        self.assertEqual(inside.tolist(), [True, False, False, True])

    def test_arm_of_uses_angle_and_core(self):
        arms = zn.arm_of([20, 0, -20, 0, 1], [0, 20, 0, -20, 1], ZONES)
        self.assertEqual(arms.tolist(), ["E", "N", "W", "S", "core"])

    def test_arm_sector_wraps_around_zero(self):
        self.assertEqual(zn.arm_of([20], [-5], ZONES).tolist(), ["E"])

    def test_crossing_of(self):
        self.assertEqual(zn.crossing_of([22, 0], [0, 0], ZONES).tolist(), ["X1", None])

    def test_convex_hull_of_square_points(self):
        pts = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0.5, 0.5]])
        self.assertEqual(len(zn.convex_hull(pts)), 4)

    def test_bearing_conversion(self):
        # with no rotation, sensor +y (90 deg) is north and +x (0 deg) is east
        tr = {"rotation_deg": 0.0, "mirror": False}
        self.assertAlmostEqual(zn.sensor_angle_to_bearing(90, tr), 0.0)
        self.assertAlmostEqual(zn.sensor_angle_to_bearing(0, tr), 90.0)


HAVE_DATA = (ROOT / "dashboard" / "data" / "meta.json").exists()
HAVE_ST = importlib.util.find_spec("streamlit") is not None and importlib.util.find_spec("plotly") is not None


@unittest.skipUnless(HAVE_DATA and HAVE_ST, "needs dashboard/data (run build_dashboard_data.py) and streamlit + plotly")
class DashboardSmokeTests(unittest.TestCase):
    def test_every_page_runs_without_errors(self):
        from streamlit.testing.v1 import AppTest
        pages = [ROOT / "dashboard" / "Overview.py", *sorted((ROOT / "dashboard" / "pages").glob("*.py"))]
        for p in pages:
            with self.subTest(page=p.name):
                at = AppTest.from_file(str(p), default_timeout=120).run()
                self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
                self.assertEqual(len(at.error), 0, [e.value for e in at.error])


if __name__ == "__main__":
    unittest.main()
