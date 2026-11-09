# NSE vs Ouster BlueCity on 29 October 2026: first results

Four shared 10-minute windows (`docs/ANALYSIS_WINDOWS.md`): W1 07:20, W2 07:40, W3 08:00, W4 08:20 (CET).
Code: `ouster_reader.py`, `nse_ouster.py`, `build_comparison_data.py`. Dashboard page: **NSE vs Ouster**.

```
python build_comparison_data.py          # about 6 minutes -> dashboard/data/compare/ and dashboard/config/ouster_to_nse.json
```

## 1. Putting both systems in one coordinate frame

| | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| rotation Ouster -> NSE | 171.21 deg | 171.17 deg | 171.22 deg | **96.15 deg** |
| shift (m) | (-18.58, 1.67) | (-18.61, 1.75) | (-18.64, 1.78) | **(-7.37, -12.08)** |
| median residual, vehicles | 0.34 m | 0.34 m | 0.38 m | 0.41 m |

- **Method:** every pair of moving vehicles seen by both systems at the same moment votes for the shift that would put one on top of the other; only the correct rotation makes the votes pile up. A least-squares fit on matched vehicles then refines it. A first attempt that matched road shapes found the crossroads rotated by about 180 deg, because the junction is nearly symmetric. The vote method avoids that.
- **Check:** pedestrians and cyclists were not used to find the transform, but they line up at 0.12 to 0.20 m median distance.
- **Clocks:** the number of moving vehicles per second correlates best at 0 s offset (r = 0.77), so the timestamps can be used as they are.
- **The Ouster frame changed before W4.** W1 to W3 agree within 0.05 deg and 6 cm; W4 needs a different transform, which fits just as well. This lines up with the raw Ouster recording that starts at 08:18:19: the Ouster system was probably restarted or reconfigured then. Every window therefore uses its own transform.

## 2. Do they see the same road users?

Area compared: about 1,100 to 1,400 m2 where both systems have detections. Pairs = mutual nearest neighbours within 1.5 m in the same frame (Ouster moved to the NSE frame time), whatever their class.

| Group | NSE per frame | Ouster per frame | NSE detections also seen by Ouster | same class when paired |
|---|---|---|---|---|
| Pedestrian | 1.2 to 5.9 | 1.8 to 7.9 | 77 to 88% | 74 to 87% |
| Cyclist | 0.5 to 2.6 | 0.7 to 2.8 | 76 to 93% | **44 to 63%** |
| Motorcycle | 0.3 to 0.9 | (no class) | 78 to 84% | 0% (mostly called BICYCLE) |
| Vehicle | 5.4 to 8.4 | 5.9 to 9.8 | 89 to 93% | 93 to 99.6% |
| Unknown | - | 0.5 to 1.9 | - | - |

Ranges are over the four windows. All windows together, when both see an object:

| NSE says \ Ouster says | Cyclist | Pedestrian | Unknown | Vehicle | not seen |
|---|---|---|---|---|---|
| Cyclist | 45% | **30%** | 7% | 0% | 18% |
| Motorcycle | 47% | 22% | 10% | 0% | 21% |
| Pedestrian | 14% | 67% | 5% | 0% | 14% |
| Vehicle | 0% | 0% | 2% | 89% | 9% |

**Main findings**
1. **Both systems see nearly the same objects**: 77 to 93% of NSE detections have an Ouster detection within 1.5 m, at 0.1 to 0.4 m distance.
2. **They often disagree on pedestrian vs cyclist.** 30% of NSE cyclists are persons for Ouster, and 14% of NSE pedestrians are bicycles for Ouster. This matters directly for Topic 4 counts.
3. **Ouster reports more objects** (1.1 to 1.6 times as many pedestrians per frame) plus an UNKNOWN class. Some may be real objects NSE misses, some may be false detections; we cannot tell without the video.
4. **Ouster tracks are longer.** Median pedestrian track in the common area: Ouster 10.6 s, NSE 4.8 s (raw ids); after our stitching and `clean` filter: 17.3 s vs 13.7 s. NSE fragments more, even on 29 October.

## Limits

- Four 10-minute morning windows only; no ground truth. The video (06:00 to 13:00) can be used to check samples of disagreements.
- NSE detections with score below 0.25 are left out; Ouster has no score filter, which inflates its counts relative to NSE.
- Pairing by distance can swap people walking close together.
- Ouster has no motorcycle class and many UNKNOWN objects, so class agreement is partly a definition problem.
