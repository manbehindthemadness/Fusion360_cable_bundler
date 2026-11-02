# Reduced constrained-joint construction403/404/406 — 2026-11-02

Five existing gym configurations planned/evaluated numerically: four shorter,
one prior route retained. Two predefined problem layouts natively attempted/built:
one named-fidelity pass, one topology rejection. Three other layouts natively
unattempted by scope. Zero full physical audits or untouched holdouts. This is an
experiment, not a replacement for the live selected solver.

## Procedure and fixed work

The user requests trying the401/402reduced-joint formulation without guessed angle
banks and with close attention to CPU cost. Each case begins with its saved381
coarse, separated construction; neither the selected first-pass optimizer nor
aesthetic smoothing runs. These are incremental experiments, not cold routing.

Keep one algebraic rotation branch and its two fold-group sizes. Move its internal
frame in three covariant angular coordinates; re-factor both groups so terminal
rotation stays closed. The saved/current affine allocation supplies an LP dual.
Six1e-5radian derivative evaluations give the material-length gradient, then use
its unit negative direction. Initial step is the first predicted nonnegative
allocation boundary, capped at the existing pi/4angular trust scale. These are
derived directions and bounded numerical trials, not random frame/angle candidates.

At each trial, run the existing complete nonnegative basic allocation for that one
frame, select minimum length (guide RMS breaks ties) and check full-profile contact.
No different algebraic root is substituted when branch counts/fold-group sizes
change. Strict shortening, complete ordered caps, material metric, declared radius,
conductor/profile identity and separated contact remain mandatory. Guide distance
and bend distribution are diagnostic preferences rather than new physical gates.
External resource/source errors propagate; finite rejection retains the preceding
validated route.

403freezes five inputs plus selected/experimental/rule/script hashes before work:
4s/case,20sphase,4GiBRSS,4updates,4step halvings/update,4contact proposals/case,
1024contact subdivisions/depth36,0native attempts. All five finish; no time/memory
stop, source drift, skipped/unattempted numerical case or acceptance-gate failure.
Across cases:13accepted updates,2penetrating proposals rejected,5contact-unresolved
proposals rejected and4position-unresolved trials. Twenty contact attempts total.
No physical infeasibility or optimum follows from exhaustion.

## Numerical results

| Case | Coarse -> reduced mm | Shorter | Joint work s | Full incremental wall / CPU s | Stop |
| --- | --- | ---: | ---: | --- | --- |
| new-excursion |72.876677 ->50.880252|30.183%|.453382|.459267 /.454196|4updates|
| trigger |41.756299 ->36.877013|11.685%|.716582|.723337 /.721234|4contacts|
| gym-recent |19.123811 ->17.679960|7.550%|.470761|.476832 /.476609|4updates|
| gym-one |11.870847 ->unchanged|0|1.309954|1.315388 /1.314624|4contacts,0accepted|
| gym-six |154.186705 ->153.806894|.246%|.093541|.099999 /.099914|4updates|

Maximum final cap error1.074e-13mm, sampled material metric6.019e-16. Changed routes
have separated optimization contact certificates under the smaller subdivision
budget; the unchanged baseline retains its recorded historical separation status.
Phase3.105572s wall/3.096876s CPU, local peak19,824,640bytes. Setup/source archive,
SDK startup and original coarse solving/contact are excluded; do not call this a
cold end-to-end speed comparison with the selected first-pass optimizer.

Shortening does not establish improved bend distribution. New-excursion's longest
flat run falls31.357->21.040mm, but still occupies41.35%of its route; its mean
direction loss worsens .67677->.69328 despite lower guide RMS/max distance.
Trigger longest flat changes13.912->13.539mm. Recent's longest flat instead grows
2.943->9.352mm and guide RMS1.48406->1.49103mm despite shorter material. Gym-six
longest flat88.434->88.997mm, guide RMS6.17555->6.31302mm and maximum9.52611->9.73573mm.
Those regressions are retained; this is not a uniformly better routing policy.
No centroid/uniform-spacing penalty or extra iteration/search budget is added.

## Native outcomes and current display

404reviews the completed numerical results and preselects exactly the two existing
problem cases, trigger first then new-excursion. Limits2attempts,120s/case,250sphase,
4GiBRSS/3.8GiB launch headroom; stop on first source/resource/API/build/fidelity
failure, no retry, cleanup, tolerance expansion, smoothing or first-pass optimizer.
The smaller explicit straight1.728e-6mm in new-excursion is recorded as a native
topology risk before construction, not deleted or hidden from the scope.

Trigger builds142faces and passes named fidelity:4900surface points,270seam chains,
both ordered caps, maximum surface error5.835e-9mm. Four existing trim-domain
certificates apply; no validation policy change. Generation1.362255s (translation
.083481,definition.685695,kernel.593080), audit13.970386s, native-operation16.907779s.

New-excursion builds a solid but the native topology guard rejects142faces where
the authored patches require152. Surface/guide/seam/cap auditing is therefore
unattempted, not passing. The route contains a1.727618e-6mm explicit straight;
the missing ten-face count is consistent with a collapsed band, but exact native
face-to-patch attribution was not investigated. No repair/tolerance change or
additional build follows. Generation2.252102s, native-operation2.579498s. The failed
body/report stay hidden/retained. Both scheduled attempts occurred before the
second failure stopped404; no case is unattempted inside its two-case scope.
Recent/Gym-one/Gym-six are natively unattempted, not validated by the trigger pass.

404phase19.762245s. Incremental numerical times for the two attempted cases fit
their matched native generation, but original coarse construction/checking is
excluded and the second native result failed: no overall timing/reliability win.
Optional UV is off; no textures/appearances or production changes. Existing sliver
cleanup is not invoked, and its1e-7mm trigger would not remove this1.728e-6mm slot.
No full physical native audits, unseen cases or continuous mechanical guarantee.

Host logs inspected after failure.406is a separately frozen display-only phase:
30s/4GiB,0solves/builds,1.743334s actual. Accepted trigger retains three hidden
original frozen material-guide sketches, both pre-existing hidden cap profiles
and a magenta exact endpoint-tangent reference cubic. No thickness mesh is added.
Native body revision stays unchanged; capture visually inspected. Component
`Selected solver v1 - reduced403-trigger`is framed at display x780cm. Existing live
gym controls, numerical policy, bodies and history remain; no experimental solver
is installed in that interface. Failed new-excursion body remains hidden at830cm.

## Verification and limits

13focused checks pass across5new reduced-joint and8existing joint-route tests.
New checks cover exact cap/material closure after internal motion, derived negative
length slope, conservative penetration/unresolved-contact handling, work limits,
branch changes and resource propagation. Native contact boundaries are mocked in
the acceptance unit tests; actual numerical/native evidence is reported separately.
The initial analytical fixture had a one-fold degenerate second group, so its
small motion correctly changed branch structure and returned unresolved. Tests
were corrected to use a generic four-fold fixture; no solver branch guard was
weakened. An iteration-ledger binding lint issue and tuple annotation warnings
were fixed before403. All5new Python files pass Ruff check/format and IDE inspection.
Complete code/diff reviewed. No full repository suite or standalone type checker.

Active selected-source lock verifies unchanged; only this isolated experiment
package/tests and maintained notes were added. Numerical input/source pins and all
unsuccessful trials remain in `artifacts/verification/ribbon_reduced403` with native
404and display406plans/results. Executed runners are `reduced403.py`, `native404.py`
and `display406.py` under `artifacts/verification`. No deeper refinement or native
retry is scheduled; distribution and native topology remain unresolved questions.

Guide-directed follow-up407/408/409 is documented in
`../experiment_ribbon_guide_joints/NOTES.md`. It preserves this403implementation and
the five coarse inputs/work limits, adding turning-derived feature targets and
coupled placement/length descent. Four improve, one retains; recent's long-flat
regression is reduced, but guide/distribution results remain mixed. Native1/2named
fidelity passes,1/2topology failures; no promotion or repair.
