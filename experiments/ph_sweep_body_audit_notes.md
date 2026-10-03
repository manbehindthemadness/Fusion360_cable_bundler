# PH sweep body audit (2026-10-03)

This experiment revisits the earlier claim that one Fusion solid body does not
by itself establish a usable bend, adequate clearance, or correct trace
surfaces. It audits seven existing, isolated PH-projection ribbon sweeps in the
still-open unsaved Fusion scratch; it does not create or change geometry. The
read-only live probe is `experiment_ph_sweep_body_audit.py`, and its ignored
report is `artifacts/verification/ph_sweep_body_audit.json`.

## Checks

Each body is a 10 × 0.5 mm rectangular sweep of planar PH quintic branch 0.
Five are unrolled 180° hairpins with endpoint separation H = 2, 5, 10, 20,
or 60 mm and derivative magnitude 25 mm. Two additional bodies use 90° roll
at H = 10 mm and 360° roll at H = 20 mm. The audit checks:

1. Fusion's solid flag, face count, and volume.
2. Planar centerline radius from 4097 deterministic curvature samples,
   compared with the **illustrative experiment criterion** of 12 mm. No
   product bend-radius requirement is asserted here.
3. For each unrolled body, predicted midpoints of all four sides at seven
   interior parameters (28 queries/body), requiring four distinct side faces
   and no face switching or missing points at 0.01 mm B-rep tolerance.
4. For every body, whether the four side faces each share exactly two
   vertices with each end cap, and how the labeled start/end cap edges map.

The cap-edge mapping is a topological check for the rolled sweeps. It does not
independently prove that their *interior* surfaces follow an intended roll
distribution. These monolithic rectangular bodies also have no per-trace
grooves, lanes, colors, or individual trace faces to validate.

## Observations

| Body | One solid / faces | Sampled planar minimum radius | Interior side samples | Cap-to-cap faces |
| --- | --- | ---: | --- | --- |
| H = 2 mm, 0° roll | Yes / 6 | 0.472 mm | 28/28 on expected stable faces | 4/4 bridge |
| H = 5 mm, 0° roll | Yes / 6 | 1.487 mm | 28/28 | 4/4 |
| H = 10 mm, 0° roll | Yes / 6 | 4.117 mm | 28/28 | 4/4 |
| H = 20 mm, 0° roll | Yes / 6 | 5.841 mm | 28/28 | 4/4 |
| H = 60 mm, 0° roll | Yes / 6 | 2.715 mm | 28/28 | 4/4 |
| H = 10 mm, 90° roll | Yes / 6 | 4.117 mm | Not sampled against a roll frame | 4/4 |
| H = 20 mm, 360° roll | Yes / 6 | 5.841 mm | Not sampled against a roll frame | 4/4 |

All seven fall below the experiment's 12 mm bend-radius criterion despite
being single solids. This proves that kernel success does not enforce a
specified physical bend limit. It does **not** mean the shapes are inherently
impossible: without an assigned minimum bend radius, these results only
establish their geometric curvature.

The unrolled faces were consistent at every sampled interior station. At
90° roll, an edge starting on the +Z side ended on the +Y side, while the
other three sides mapped correspondingly. At 360° roll, the cap-edge mapping
returned to the unrolled mapping. In these tested sweeps there is no observed
loft-style side-face scrambling or fragmentation.

The earlier sampled nonlocal-distance screen gives approximately 1.533 mm
between separated centerline samples for the H = 2 mm case, with its
quarter-path-length exclusion. Subtracting the 0.5 mm in-plane ribbon
thickness leaves a conservative sampled gap of about 1.033 mm, above the
experiment's illustrative 0.5 mm clearance. This is a heuristic, not a
proof of swept-profile clearance: the exclusion rule, finite sampling, and
roll are not fully analyzed. We did not establish a minimum clearance for
the rolled profiles or a complete global self-intersection certificate.
Likewise, the audit cannot validate per-trace color regions because this
simple sweep does not contain them.

## Conclusion

The broad logical statement remains true—one solid does not certify an
independently specified bend constraint—but the loft face-correspondence
failure did **not** carry over to these rectangular sweeps. For this experiment
the face evidence is favorable. A future sweep-face test would need an
explicit per-trace profile and a defined roll frame before claiming that
colored trace surfaces remain correct throughout a twisted cable.
