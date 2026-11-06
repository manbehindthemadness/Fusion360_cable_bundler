# Coupled finite-feature clearance — 2026-11-06

The next stopped run has **7 attempted / 6 passed / 0 warning passes**. The trigger
is N4 seed 251693499, A zone 22/face 11/roll 30°, B zone 23/face 7/roll 58° (stored
zero-based zone/face indices). Original failed job
`selected-0704f8546029437dbdba645d180eae97` and its rejected inspection body remain.
The first-pass route is 23.536051919 mm; the raw construction is 26.121479284 mm.
Neither it, smoothing nor the raw fallback clears both finite terminal boxes.
The old forced reflection closes at 116.194 mm and correctly fails its length guard.

## Rule and unchanged work limits

Only actual **fold** evidence in otherwise unused deferred feasibility recovery
uses the new action. Already accepted output and the existing straight-evidence
reflection policy remain unchanged. Move existing joint angles, banks and runways
while preserving all ordered fold signs, radii, profiles, material order and targets.

Derive a complete material-feature bound from the measured intrusion. A fold
includes its actual terminalward straight, if present; a straight includes the
neighboring fold away from that terminal. An absent runway's synthetic analysis
slab is not additional occupied feature material. Select the closest signed gap
from the 15 algebraic box/material-frame SAT directions once. Follow that same
axis family as the feature moves, including its derivative; do not switch families
or search bend angles/events. Bounds include full material width and thickness.

Solve the six ordered endpoint equations and selected feature-gap equations
**together**. A demonstrated second intrusion may add one more feature constraint;
the first stays active. Complete checks against both finite boxes remain mandatory.
This resolves the previous failure where pose-only closure undid a clearance move,
or clearing one region left its adjacent fold inside the connector.

The quality ceiling is original construction length plus initial complete-feature
projection overlap: 26.121479284 + 0.697443541 = **26.818922825 mm** here. This local
growth allowance is a feasibility preference, not additional physical clearance or
accuracy tolerance. Full self-contact, box clearance and material/cap gates stay hard.

Reuse the same **4 updates / 0.35 CPU s / 2 wall s**, inside the original four-second
construction deadline. At most 24 Newton corrections (six per update), four scalar
halvings and 0.2 radian trust; at most two measured constraints. Remaining original
2,048 contact pairs, at most 1,024 per certificate, and shared hardware
0.1 CPU s / 0.25 wall s / 1,024 cells are unchanged. Per-instance caches hold at most
64 placements/gaps. No alternate candidate search or automatic budget renewal.

Intermediate hardware-blocked proposals are never built and need no redundant
full self-contact certificate. Before acceptance, a sub-native positive runway
slot is fixed to exact zero and every equation is reclosed within the remaining
corrections/time. Hardware is remeasured; final native-length and full self-contact
checks still apply to the exact accepted geometry. No post-build weld or target move.

## Investigation, including unsuccessful work

887–889 retain failed pose-only projection and moving-axis trials. 890 clears the
first connector but hits the other; 891's coupled planes close but exceed the old
quality ceiling. 892 certifies that result but finds an adjacent fold still inside.
893's grouping of an absent synthetic runway stalls. 894 groups only real material
and clears both boxes at 26.386846298 mm, but is a cached prototype, not a native pass.

895 freezes this run's four selected cases and actual baselines before integration.
The N7 passed case is an existing exact alias; two passed controls and this trigger
are genuinely new. Corpus inventory is **63 unique development configurations**;
all prior 60 targets/settings/history prefixes remain. Capacity is reviewed at 63
with unchanged 120 s phase / 103 s launch cutoff / 15 s case limits.

897 evaluates 4/4 but the trigger stops at an intermediate native-sliver guard.
899 evaluates 4/4 and clears hardware, but final numerical runway dust still fails
that guard. Both preserve all three accepted controls and remain recorded failures.
901 adds bounded exact-zero/reclosure: 4/4 accepted, prior three exact.
902 completes **63/63 in 62.757 s: 49 accepted / 14 unresolved**. All **48 previously
accepted final AND first-pass snapshots are exact**; only this trigger is newly
accepted. Each acceptance independently clears both boxes. No configuration is
skipped or unattempted in that numerical comparison. This is examined development
coverage, not holdout validation, universal feasibility or a 1,000-pass streak.

## One current native attempt

904–906 use one ordinary fresh worker, guarded to reproduce the frozen exact route,
and one unchanged native build. Job `selected-fb8b3b7bf57945af8b1fcf5525766fbe`:

| Measurement | Result |
| --- | ---: |
| Length | 26.386845873 mm |
| Fold count / preserved signs and radii | 4 / all |
| Recovery / corrections / final certificate pairs | 0.261909 CPU s / 9 / 298 |
| Total construction pairs | 633 / 2,048 |
| Shared terminal cells / CPU | 434 / 1,024; 0.050288 s |
| Complete numerical CPU / wall | 0.831221 / 0.951711 s |
| Native generation / named audit | 0.819233 / 1.233077 s |
| Whole native operation | 11.163458 s |
| Faces / surface samples / seams | 194 / 6,720 / 372 |
| Maximum native error | 7.603226987e-10 mm |
| Native attempts / builds / named fidelity passes | 1 / 1 / 1 |
| Precision warnings / full physical audits | 0 / 0 |
| Native precise outer bounds, ±32.5 mm | Pass; zero excess |
| Maximum sampled native RSS | 1,924,000 KiB |

The numerical-versus-generation goal narrowly **misses** by 0.011988 s; do not claim
a speedup from the larger whole-native duration. Constructor and audit costs are
separate from retained cap-profile/display overhead. No native retry or timing repair.
The other 48 accepted configurations and all 14 unresolved configurations have no
new native attempt in this comparison. Continuous/full physical compliance remains
unmeasured. Across integration phases there are 76 full numerical executions
(4 + 4 + 4 + 63 + 1), over 63 unique inputs; cached probes/unit fixtures are separate.

The corrected body, exact current gym/prepath and both finite boxes are visible;
viewport reviewed and native revision unchanged by display. Original failed body,
input and **6/7 tester journal** remain preserved. Tester stays stopped; ordinary
callbacks are restored. Sources, inputs, ledgers, failures and captures remain in
ignored `artifacts/verification/ribbon_terminal887` through `906` and adjacent QA files.

Final focused verification: **67 tests pass**; scoped Ruff lint and format pass on
eight affected Python files. Changed implementation/tests are IDE-clean; the two
pre-existing solver duplicate-fragment weak warnings remain. Full diff reviewed,
including an append-only audit of all prior corpus inputs/history. The final two
contract docstring edits have identical executable ASTs to the frozen replay/native
sources (`terminal909-final.json`); no geometry rerun is charged for prose changes.
The source lock verifies **231 files**. No required focused check remains unavailable;
repository-wide QA, broader native coverage and a full physical audit were not run.
