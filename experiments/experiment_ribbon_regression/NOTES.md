# Frozen gym regression corpus

Current failure triage, Nov8 /1598–1602: 65/65 eligible inputs accepted in a fresh
cold numerical replay; zero unattempted and every first/final route pair exactly
matches1506. Current saved tester selection was frozen explicitly: first-pass
optimization on, smoothing1%, UV off, terminal hardware on. Historical omitted
hardware settings are provenance, not current acceptance policy. All65 pass the
current input ranges and spacing policy; conservative exact-material enclosures
also lie inside the current stress box. These enclosures are not native bounding
box measurements. The65-input replay took54.306830s wall, with no native attempts.

The21eligible inputs carrying past problem records have no current numerical
rejection. The sole eligible historical native/fidelity problem, `prior-case-72`,
was also rechecked once through ordinary Fusion solve/build/audit. The old result
built a body but exceeded120s during ordered-seam auditing. Current1600/1601:
one exact accepted body, named fidelity/precise gym boundary/hardware checks pass,
zero warnings;10,920points/600seams, maximum error1.543225e-9mm. Generation0.765614s,
audit1.602133s; solve1.021663CPU exceeds the construction timing goal, recorded
without a budget or acceptance change. Other64inputs were not rebuilt natively;
full physical audits remain unattempted. The timeout did not reproduce with the
current source/settings/session; its original cause has not been isolated.

No further solver fix is indicated by this saved set. The active failure queue
has no reproduced eligible problem; eight input-policy exclusions remain separate
from passes. The tester stays stopped with its existing counters unchanged. The
user's standing eligibility/current-policy triage rule is now explicit in
`experiment_testing_rules.txt`. Plans, per-case dispositions and qualification:
`artifacts/verification/resume1598/`, `resume1599/`, `resume1600/`, `resume1601/`
and `resume1602-triage-closure/`. No solve under historical hardware-off settings
should be described as the current hardware-enabled test.

Current active corpus: `gym-v3.json`, 65 inputs. Its `separated_cubicles` policy
uses the same face/edge/corner adjacency rule as the tester defaults and rejects
inadmissible or unidentified placement before a worker starts. Eight adjacent
legacy cases remain intact in `gym-v2.json`; v3 records their identities and the
parent digest. All 65 retained cases are exact unchanged v2 records. Historical
enrollment and outcome counts below describe their original corpus revisions.

The spacing audit checked all 73 v2 cases, all 77 recent replay inputs and63test
journals containing2,832finished records. The journals identify the same eight
adjacent problem inputs (nine stop records, including a cancellation); none were
unknown. Other seven besides `historical-32e26c5c88b5`: `historical-18a674a18788`,
`historical-28058398a1cd`, `historical-967d15e32a3e`, `historical-a63da6403dab`,
`historical-bab2ad4bcc21`, `historical-e03a89e210af`, `historical-fd38c9581cf6`.
Of the original eight backlog cases, only historical32 and e03 violate this
spacing policy; the other six were separated and qualified. e03's solver repair
and native qualification remain valid historical evidence. A spacing exclusion
does not establish the cause of a native/fidelity/runtime error or remove its bug
record. No solver changes or new solves/native builds accompanied this audit.
25 focused tests, scoped Ruff/format and IDE inspections pass. Evidence:
`artifacts/verification/resume1594-spacing-audit/`, `resume1595-journal-spacing/`,
and `resume1596-corpus-spacing/` under the same verification directory.

Nov8 user review: after viewing the original native inspection body in1589/1590,
the user classified `historical-32e26c5c88b5` as an invalid spacing scenario.
Its zero-based zones14/23 are cubicles `(0,1,-1)` / `(1,1,-1)`, which share a face.
This legacy input is outside the intended separated-cubicle test policy. Both the
current code default and saved tester specification already enable
`avoid_adjacent_zones`; no default or solver code was changed for this decision.
Keep the original input, failed numerical receipts and inspection-only body.
Seven of the original eight failures have qualified solver repairs; the eighth
is excluded by the user's input-policy decision, not repaired or counted as a
successful geometry configuration. Existing corpus outcomes stay immutable.
Future work must distinguish an empty cubicle between endpoints from a physical
gap between every cubicle; the latter has not been implemented by this decision.
Evidence: `artifacts/verification/resume1592-spacing-decision/`.

Run999 encounters existing alias`rangec59-case-63` again: numerical/native-fidelity
pass, actual native boundary failure on854mmfallback. Its history already contains
both retained-control and boundary dispositions. Numerical replay acceptance and
exact geometry preservation do not establish overall success or native bounds.
Future improvement comparisons must allow this known failed output to change
while preserving its real history. Corpus remains73inputs; frozen trigger plus
actual preceding controls are in1000/plan.json. See
[excursion63 review](../experiment_ribbon_terminal_hardware/EXCURSION_63.md).

Current inventory: **73 exact development inputs**. New N1 case57 joins the prior
72; preceding54–56 are existing aliases with appended histories. All prior input
fields/history prefixes remain. Capacity73 retains120sphase/103scutoff/15scase.
Final994 evaluates73/73: **60 accepted / 13 unresolved**, all60 accepted final and
first-pass routes exact against987. Current57 is the sole new acceptance relative
to the pre-repair corpus. Only current has one new native/fidelity/boundary pass;
other72 new native builds and all full physical audits are unperformed. See
[completed recovery and reuse](../experiment_ribbon_terminal_hardware/COMPLETED_RECOVERY.md).

Earlier inventory: **72 exact development inputs**. Monitored cases 53–55 and N10
failure 56 are all new signatures; prior 68 inputs/settings/history prefixes remain.
Capacity 72 retains 120 s phase / 103 s cutoff / 15 s case limits. 971 evaluates
72/72: **59 accepted / 13 unresolved**, all **58 previous final AND first-pass
routes exact**. Only current case newly accepts and receives one new native/
fidelity/boundary pass; all other new native coverage/full physical audits remain
unattempted. [Fold-feature quality evidence](../experiment_ribbon_terminal_hardware/FOLD_QUALITY.md).

Earlier inventory: **68 exact development inputs**. Monitored cases 14/15 and N3
failure 16 are new; case 13 is existing `historical-208c6aa74e2e`, with appended
history. All prior 65 inputs/history prefixes remain. Capacity 68 retains the
120 s phase / 103 s cutoff / 15 s case limits. 944 evaluates 68/68: **55 accepted /
13 unresolved**, all **53 previous final AND first-pass routes exact**. Current and
older case138 improve; only current has a new native/fidelity/boundary pass.
[Constrained straight-feature evidence](../experiment_ribbon_terminal_hardware/STRAIGHT_QUALITY.md).

Earlier inventory: **65 exact development inputs**. N8 passed case 9 and N6 failure
case 12 are new; cases 10/11 are existing aliases with appended provenance. All prior
63 inputs/history prefixes remain. Capacity 65 uses the same 120 s phase / 103 s cutoff /
15 s case limits. 924 evaluates 65/65: **51 accepted / 14 unresolved**, all **50 prior
accepted final AND first-pass routes exact**. One current native/fidelity/boundary
pass; no other new native coverage or full physical audit. See
[exact measurement reuse](../experiment_ribbon_terminal_hardware/MEASUREMENT_REUSE.md).

Earlier inventory: **63 exact development inputs**. That run adds two genuinely
new passed controls and the N4 seed 251693499 failure; its preceding N7 pass is an
existing alias with appended provenance. Prior 60 inputs/history prefixes remain.
Reviewed capacity is 63 with the same 120 s phase, 103 s cutoff and 15 s case limits.
902 evaluates all 63: **49 accepted / 14 unresolved**, all **48 previous accepted
final and first-pass snapshots exact**. One current native/fidelity/boundary pass;
no other native attempt or full physical audit. See
[coupled feature clearance](../experiment_ribbon_terminal_hardware/FEATURE_CLEARANCE.md).

Earlier inventory grew to60exact development inputs after the range run: N8alias
prior-case01plus newN2/N10preceding passed controls and N7trigger with newrolls.
Prior57inputs/settings/historyprefixes retained. Replay capacity60uses original120s
phase/103scutoff/15scasebudget. Final880:60/60evaluated,46numerically accepted/
14unresolved, all45prior accepted final+firstpass snapshots exact. OnlynewN7trigger
is natively rebuilt/fidelity/boundary checked;0fullphysicalaudits. See
[deferred terminal evidence](../experiment_ribbon_terminal_hardware/DEFERRED_RECOVERY.md).

Latest866comparison(2026-11-06):57/57evaluated,43numerically accepted/14unresolved;
all35previous accepted final/first-pass routes exactly unchanged. Eight former
rejections retain an existing fully self-separated/hardware-clear construction
when later optimization fails; seven changed cases lack new native/stress validation.
Current N8run is an exact prior-case01alias, with appended provenance and no new
configuration count. Only that trigger is built/named-fidelity/boundary checked.
See [construction fallback evidence](../experiment_ribbon_terminal_hardware/CONSTRUCTION_FALLBACK.md).

Latest terminal-correction comparison857(2026-11-06):57/57exact inputs evaluated,
35accepted/22unresolved under the enabled hardware trial. All34previous accepted
final routes are byte-for-byte unchanged; current164is newly repaired. Six of seven
witness-directed reversal actions are declined by unchanged acceptance rules.
855stopped17/57on a caught measurement-budget regression, with40unattempted; its
sources/failure are retained. The revised32cell early probe preserves the original
final-check budget. One changed configuration is natively built/named-fidelity/
boundary checked, with0fullphysicalaudits; no other native replays or1000case streak.
See [coupled correction evidence](../experiment_ribbon_terminal_hardware/COUPLED_REVERSAL.md).

`gym-v2.json` began as a 57-input development corpus and later grew to73. It retains the entire
54-input v1 inventory and adds this run's cases 162/N9, 163/N3 and intersection
164/N4. Preceding passed case 161/N5 is an exact alias of `range5fe-case-161`;
its new provenance is attached without counting another input. Version 1 remains
unchanged. The three preceding passed controls and failure were frozen before
changing recovery selection. This is development coverage, not a fresh holdout.

`gym-v1.json` is the original inventory assembled during the November 5
consolidation. It contains the union of all 21 distinct non-cancelled problem
inputs in the 43 saved range journals and the 43 retained numerical controls:
54 exact target payloads. Original job paths, plan hashes, source digests,
settings and dispositions remain attached to each input. Replays use saved
coordinates and frames directly; seeds never regenerate targets. These are
examined development inputs, not untouched validation families.

All cases remain in their original historical denominators. The eight adjacent
inputs remain available as legacy stress cases in explicit v1/v2 replay. The
user-requested v3 active scope excludes them by the existing placement policy,
with exclusion identities and parent digest recorded. Placement eligibility is
separate from physical feasibility; these inputs are not relabelled solver passes
or proven physically impossible.

Run an explicit numerical baseline, then compare an unchanged candidate:

```sh
uv run --python .venv/bin/python -m experiments.experiment_ribbon_regression.runner --output artifacts/verification/NEW-baseline
uv run --python .venv/bin/python -m experiments.experiment_ribbon_regression.runner --output artifacts/verification/NEW-candidate --baseline artifacts/verification/NEW-baseline
```

Read the project experiment safeguards first. Each invocation freezes its corpus
and implementation hashes before launching one isolated worker per input. Limits
are 57 executions, 15 seconds per execution, a 17-second subprocess guard, 120
seconds per phase, no launch after 103 seconds, and 4 GiB sampled peak RSS. The
solver's existing four-second first-pass, contact, contraction and recovery limits
remain independent. No native construction or range tester starts here.

Source/resource/harness errors stop immediately. A candidate acceptance loss or
length increase above 1e-7 mm stops comparison, retaining the rejected row and all
unattempted inputs. Baseline numerical rejection is recorded while later cases
are measured. Each worker flushes proposals to its own trials journal. Output
directories are new and result files are not overwritten. A `cancel` file stops
the phase cooperatively. There are no automatic retries or budget increases.

Promote future failures with fixed targets and original provenance into a newly
versioned corpus between runs, after reviewing its resource scope. Preserve prior
corpora and outcomes. A numerical pass never substitutes for native construction,
named fidelity or full physical compliance.

## Consolidation evidence, 785–792

- 786 baseline: 54/54 evaluated, 53 accepted, one unresolved; 53.279653 s wall,
  46.348474 s aggregate solver CPU. No native attempts.
- 787 rejected a raw length-first allocation/selection proposal before its planned
  batch: 66 focused tests passed, one existing excursion regression failed
  (about 49.63 mm became 109.02 mm). Source patch and outcome remain archived.
- 788 rejected earlier length-only branch replacement: 13/54 evaluated and
  numerically accepted; case `new-case-21` grew 15.845070 to 16.129798 mm after
  contraction. The other 41 inputs were unattempted. A shorter coarse construction
  does not guarantee a shorter completed first pass. This proposal was reverted.
- 789 retained construction initialization and changed only terminal contraction
  recovery eligibility: compare a strict shorter replacement with the already
  contracted baseline, without a guide-fit veto. Every replacement still needs
  its strict contact certificate. Original default historical behavior remains
  available through the explicit improvement policy.
- 789: 54/54 evaluated, 53 accepted, the same one unresolved, zero measured
  acceptance/length regressions. Of 53 accepted routes, 52 are exactly unchanged;
  `historical-208c6aa74e2e` shortens 84.210531 to 82.807388 mm. Wall 52.647320 s,
  aggregate solver CPU 45.531925 s; this is one paired development replay, not a
  statistical performance claim. Quality reporting is timed separately from UV
  metadata and remains included in overall numerical time.
- 790: all 46 inputs eligible under the current non-adjacent-cubicle setting are
  numerically accepted. Seven of eight adjacent-cell legacy inputs also pass;
  `historical-32e26c5c88b5`, seed 3079315550/N7, remains unresolved with no fixed-radius
  closure after its original finite corrections. Its cells `(0,1,-1)` and
  `(1,1,-1)` are adjacent. This is not evidence of physical impossibility.
- 791: the one changed accepted configuration is natively attempted/built/named-
  fidelity-audited, 1/1, zero warnings. Generation 6.285068 s, audit 5.283457 s,
  354 faces, 12,320 points, 682 seams, maximum error 1.7730553e-9 mm. Precise
  bounds pass the unchanged ±60.625 mm stress box. Numerical CPU 1.409755 s and
  wall 1.413080 s meet this matched construction timing goal. The other 52 accepted
  routes have no new native builds; the unresolved input is unbuilt. Full physical
  audits: zero.
- 792 captures the verified body alone and leaves it hidden, preserving the
  current gym draft, tester state and overlay visibility. The earlier native
  screenshot includes the unrelated current draft and is not a target comparison.

Evidence is under `artifacts/verification/ribbon_consolidation785` through `792`,
including the separately named `787-rejected` directory. The 1,000-case goal is
not established. The range tester remains stopped; no production promotion occurs.

## Intersection 164, evidence 794–813

Run `range-fe65c9e2dd4e445da05fb87bd1fd27bc` stopped after 163 passes. N4,
seed 321914440, A zone24/face6/roll75°, B zone2/face11/roll34° (one-based UI).
The visible intersecting body was already a **rejected native inspection**, not a
false accepted route. All three closed branches had strict penetration witnesses.
The legacy selector predicted one step on roots `(0,1)`, but the first
endpoint-retracted motion cleared only about half the measured gap. Three updates
then exposed the attached straight's crossing, exhausting the four-update allowance.

795–799 are bounded partial diagnostics, not independent complete-case coverage.
Clearing only the first gap on another branch (796) and correcting the original
branch's attached straight (797) both failed whole-route recovery. 799 found the
existing `(1,0)` branch separates in one update using its confirmed straight sheet
as a moving material plane, rather than its old fixed-world prediction axis.

Unconditionally changing initial evidence preparation regressed an older repaired
control, so that proposal was rejected (804 patch/JUnit retained). The retained
rule preserves legacy selection whenever its full predicted first motion opens
the actual gap, and leaves clipped predictions alone. Only an inconsistent full
prediction authorizes bounded preparation of confirmed straight-sheet evidence on
existing branches. A replacement must itself open its measured gap in one full
endpoint-retracted motion. This predicts motion only; actual recovery still needs
strict complete contact certification. All preparation remains charged to the
original 0.35 CPU/2 wall seconds, four updates and shared contact pool. No roots,
headings, radii, physical limits or contact acceptance rules were expanded.

803 freezes 57 pre-fix baselines: 55 accepted, current164 and legacy adjacent-cell
N7 unresolved. 807 stops after 44 evaluated/accepted because an unchanged N6 raw
route hits its contraction CPU cap, retaining 67.72 rather than 39.74 mm. Thirteen
cases remain unattempted. IDE inspections were running concurrently; the timing
is confounded. Preserve that failed outcome. 808 renews only that control and the
13 unattempted cases, with inspections idle and unchanged caps: 14/14 evaluated,
no regression; the control exactly matches baseline again. Avoid concurrent IDE,
lint or test work during timing comparisons.

Final combined evidence covers all 57 inputs, with 56 accepted, the same legacy
adjacent-cell input unresolved, 54 accepted controls exactly unchanged, and one
older control shorter (52.785090 → 50.999106 mm). Current164 is now accepted at
39.475530 mm. This is two bounded candidate phases with one retained timing
failure/re-evaluation, not an uninterrupted 57-case run. Including the 57 baselines,
44 first-phase, 14 renewal, one fresh live solve and one post-lint replay gives
117 numerical executions across 57 exact inputs; partial diagnostics and unit
tests are separate. It establishes no global optimum or 1,000-case streak.

809–810 natively attempt/build/named-fidelity-audit both changed configurations,
2/2 with zero warnings and unchanged gym stress bounds passed. Other 54 accepted
routes have no new native builds; the legacy unresolved input is unbuilt. Full
physical audits: zero. Fresh current164 recovery is 1 update/344 pairs/0.226105 CPU
seconds including preparation; construction uses 645/2048 pairs. Total numerical
CPU 1.317405/wall 1.353458 seconds; generation 2.853187, audit 3.703505 seconds.
170 faces, 5,880 points, 324 seams, maximum error 1.7287507e-9 mm; ±32.5 mm box
passes with zero excess. Both matched timing goals pass. The corrected body is
visible; original rejected inspection and 163/164 ledger remain preserved.

Final import-order cleanup is separately source-pinned in812: identical import
sets/non-import syntax and exact final/first-pass route equality after one cold
replay. Runtime policy is unchanged; old numerical/native source pins are retained.
Final focused QA is recorded in813. Tester stays stopped; no automatic range
restart or production promotion follows.
