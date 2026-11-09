"""Tests for the track pipeline on the three sample files in database/ (00:00 to 00:14).

Run from the repo root:   python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import build_dashboard_data as bdd  # noqa: E402
import track_pipeline as tp  # noqa: E402
import track_stitching as tsx  # noqa: E402

SAMPLE_DIR = ROOT / "database" / "k305_object_list_2026-10-14_aggregation_5min"


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = tp.list_files(SAMPLE_DIR)
        cls.raw = tp.parse_files(cls.files, progress=False)
        cls.variants, cls.info = tp.make_variants(cls.raw)

    def test_parse_counts_every_object(self):
        n = 0
        for f in self.files:
            with open(f, encoding="utf-8") as fh:
                n += sum(len(fr["objects"]) for fr in json.load(fh)["frames"])
        self.assertEqual(len(self.raw), n)

    def test_variants_keep_all_rows_except_clean(self):
        expected = len(self.raw) - self.info["duplicates_removed"]
        self.assertEqual(len(self.variants["segmented"]), expected)
        self.assertEqual(len(self.variants["stitched"]), expected)
        self.assertLessEqual(len(self.variants["clean"]), len(self.raw))

    def test_stitching_only_reduces_track_count(self):
        seg = self.variants["segmented"]["trk"].nunique()
        stitched = self.variants["stitched"]["trk"].nunique()
        clean = self.variants["clean"]["trk"].nunique()
        self.assertLessEqual(stitched, seg)
        self.assertEqual(seg - stitched, len(self.info["links"]))
        self.assertLessEqual(clean, stitched)

    def test_duplicate_rows_are_removed(self):
        self.assertGreater(self.info["duplicates_removed"], 0)  # the sample files contain some

    def test_a_track_never_has_two_rows_at_the_same_time(self):
        for name, v in self.variants.items():
            dup = v.duplicated(["trk", "t"]).sum()
            self.assertEqual(dup, 0, name)

    def test_clean_tracks_respect_the_filters(self):
        tt = bdd.track_table(self.variants["clean"])
        self.assertTrue((tt["frames"] >= tp.MIN_FRAMES).all())
        self.assertTrue((tt["extent_m"] >= tp.MIN_EXTENT_M - 1e-3).all())

    def test_one_class_per_track(self):
        for name, v in self.variants.items():
            self.assertEqual(v.groupby("trk")["cls"].nunique().max(), 1, name)

    def test_track_table_and_counts_agree(self):
        tt = bdd.track_table(self.variants["stitched"])
        self.assertEqual(len(tt), self.variants["stitched"]["trk"].nunique())
        counts = bdd.counts_15min(tt)
        self.assertEqual(int(counts["started"].sum()), len(tt))
        self.assertTrue((counts["present"] >= counts["started"]).all())

    def test_density_conserves_dwell_time(self):
        v = self.variants["clean"]
        d = bdd.density(v)
        self.assertAlmostEqual(float(d["dwell_s"].sum()), len(v) * bdd.DT, delta=1.0)

    def test_passes_count_each_track_once_per_cell(self):
        v = self.variants["clean"]
        p = bdd.passes(v)
        n_tracks = v["trk"].nunique()
        for cell in (0.5, 1.0, 2.0):
            q = p[p["cell_m"] == cell]
            self.assertLessEqual(int(q["tracks"].max()), n_tracks)
        # bigger cells merge small ones, so the total of distinct tracks over all cells can only go down
        tot = p.groupby("cell_m")["tracks"].sum()
        self.assertGreaterEqual(tot[0.5], tot[1.0])
        self.assertGreaterEqual(tot[1.0], tot[2.0])

    def test_synthetic_cut_test_repairs_most_tracks(self):
        res = tsx.synthetic_cut_test(self.info["seg"], self.info["ep"], self.info["edge_r"], n=300)
        if len(res) >= 20:
            self.assertGreater(res["joined_right"].mean(), 0.5)
            self.assertLess(res["joined_wrong"].mean(), 0.1)


class StitchUnitTests(unittest.TestCase):
    """Small hand-made cases for the stitcher."""

    def _frame(self, rows):
        import pandas as pd
        cols = ["t", "track_id", "class_name", "x", "y", "vx", "vy", "length", "width"]
        d = pd.DataFrame(rows, columns=cols)
        d["yaw"] = 0.0
        d["file_idx"] = 0
        return d

    def _walker(self, tid, t0, t1, x0, speed=1.0, cls="Pedestrian"):
        # walks along +x at `speed` m/s, 10 Hz
        rows = []
        for k in range(int(round((t1 - t0) * 10)) + 1):
            t = t0 + k * 0.1
            rows.append((t, tid, cls, x0 + speed * (t - t0), 0.0, speed, 0.0, 0.7, 0.6))
        return rows

    def test_gap_in_one_walk_is_joined(self):
        rows = self._walker(1, 0.0, 5.0, 0.0) + self._walker(2, 6.0, 12.0, 6.0)  # 1 s gap, same line
        seg, links = tsx.stitch_tracks(self._frame(rows))
        self.assertEqual(len(links), 1)
        self.assertEqual(seg["trk_s"].nunique(), 1)

    def test_far_away_object_is_not_joined(self):
        rows = self._walker(1, 0.0, 5.0, 0.0) + self._walker(2, 6.0, 12.0, 30.0)
        seg, links = tsx.stitch_tracks(self._frame(rows))
        self.assertEqual(len(links), 0)
        self.assertEqual(seg["trk_s"].nunique(), 2)

    def test_incompatible_classes_are_not_joined(self):
        rows = self._walker(1, 0.0, 5.0, 0.0, cls="Pedestrian") + self._walker(2, 6.0, 12.0, 6.0, cls="Bus")
        seg, links = tsx.stitch_tracks(self._frame(rows))
        self.assertEqual(len(links), 0)

    def test_reused_id_far_apart_in_time_is_split(self):
        rows = self._walker(7, 0.0, 3.0, 0.0) + self._walker(7, 600.0, 603.0, 0.0)  # same id ten minutes later
        seg, _ = tsx.stitch_tracks(self._frame(rows))
        self.assertEqual(seg["trk"].nunique(), 2)


if __name__ == "__main__":
    unittest.main()
