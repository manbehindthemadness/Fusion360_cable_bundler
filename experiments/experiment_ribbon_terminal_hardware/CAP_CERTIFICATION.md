# Case 71: certify actual mating frames during joint recovery

2026-11-07. The monitored run `range-fa91816c3bf845c59e6cdc038f79ccb2`
stopped at 70 passes / 71 attempts / zero warnings. The numerical route was
self-clear, but finite terminal clearance remained unresolved. Fusion built a
rejected inspection body; construction alone did not make it an accepted route.

## Cause and solver rule

Joint recovery's normalized closure residual was below its stopping threshold,
but the end center was still 5.969066e-9 mm from its fixed target. The ordered-frame
vector error was 4.274291e-11. The hardware checker requires actual mating frames
within 1e-10 before using its analytic cap-side proof. Without that proof, it
subdivided material at the intended end face until exhausting the shared 1,024-cell
allowance. The later smoothed route had the same kind of mismatch. This is a
solver stopping-contract mismatch, not evidence of a difficult connector collision.

`ClosurePolicy.ORDERED_CAPS` now requires both actual ordered cap frames to meet
the existing mating-proof criterion before self-contact recovery can stop.
It performs a real correction of the same joint coordinates and retains fixed
targets, radii, conductor profile/order and event topology. It neither snaps output
nor relaxes the contact or hardware tests. The original six Newton steps, four
scalar halvings, four recovery updates, 0.35 CPU / two wall seconds and shared
construction pair allowance remain unchanged. Caller cancellation still propagates.

`ClosurePolicy.NORMALIZED` preserves the existing contraction and motion-prediction
steps. Applying the stronger stop to every intermediate contraction changed a
four-step descent trajectory and regressed another route by 3.884507 mm. That
universal proposal was rejected; only certified self-contact recovery explicitly
requests the ordered-cap rule. Both policies share the same implementation and
bounded work, with typed selection rather than a layout-specific exception.

The repaired first pass is 77.75002171114564 mm long, with cap error
1.921424e-14 mm. The optional smoothed proposal remains hardware-unresolved, so the
solver correctly retains this certified first pass. Hardware measurement uses
530 shared cells, with one clear result and one unresolved smoothing measurement;
the unresolved result is retained, not relabelled clear.

## Separate qualification results

Four complete configurations were frozen before selecting the rule: the failure
and its three preceding native/fidelity/boundary passes. All four are numerically
accepted in maintained replay 1104. The three comparison routes retain exact
first-pass and final geometry. The trigger takes 1.044838 CPU / 1.078618 wall seconds
in this cold SDK replay. No native work occurs in that replay.

The original 73-input development corpus is replayed completely in 1105, with no
new cases, retries or work-limit expansion: **63 accepted / 10 unresolved**, versus
60 / 13 in 1089. Every previous acceptance is retained. Of the 60 prior acceptances,
56 preserve exact first-pass and final geometry; the other four have only tiny
numerical changes, with no first/final length increase above the frozen 1e-7 mm
regression limit. This is examined development evidence, not an untouched holdout.
Wall time is 71.951985 seconds within the original 120-second phase ceiling.
The four-input comparison and this corpus overlap at the trigger: their union
contains 76 distinct complete target configurations, not 77.

New numerical recoveries are `prior-case-71` (the current physical trigger),
`range697-case-134`, and `historical-18a674a18788`. The latter two receive no new
native build. All accepted outputs pass strict self-contact and independent finite
hardware checks. The ten unresolved inputs remain in the denominator. The other
72 corpus configurations receive no new native attempt or full physical audit.

One fresh ordinary solve in Fusion, 1106, reproduces the exact reviewed route:
0.949601 CPU seconds. One native attempt builds and passes named fidelity without
warnings: 11,900 points, 660 seams, maximum sampled error 7.617600e-10 mm. These
points, seams and faces are workload, not independent-case coverage. Native
generation takes 1.035786 seconds; the solve meets the matched generation timing
goal. Audit takes 2.016545 seconds separately; the whole native workflow takes
17.552636 seconds. No appearance or bitmap is created; optional UV metadata is
unchanged and disabled in this case. Full physical audits remain unattempted.

Native precise bounds in 1108 pass the unchanged ±55 mm gym allowance with zero
excess: minimum (-24.997598, -18.465211, -13.781605) mm; maximum
(14.319235, 17.049845, -2.035357) mm. The native revision and original tester journal
remain unchanged during view inspection. The capture was reviewed. The rejected
body remains retained and hidden. Maximum sampled native RSS is 2,258,672 KiB;
in-flight peak is unmeasured. Native limits stay one attempt / 120 seconds / 4 GiB,
with 3.8 GiB launch headroom.

## Failed and incomplete stages retained

| Phase | Disposition |
| --- | --- |
| 1096 | Live MCP confirms the owned idle document, stopped tester and current rejected inspection body. No solve or native operation. |
| 1097 | Freeze four inputs, original source 243, stopped journal and campaign statistics. |
| 1098 | Diagnostic harness misses postponed annotations; no route measured. Failure retained. |
| 1099 | Observe unchanged 512-cell traversal on three dependent variants of the trigger. All stop at end material with mating-frame recognition false; 0.082557 aggregate CPU seconds. This is one physical configuration, not three cases. |
| 1100 | Four-case harness fails before writing its plan because `__file__` is absent in its launcher; no solve occurs. Retained, then use the normal path-aware launcher. |
| 1101 | Universal stopping-rule prototype: four accepted, one prior comparison geometry changed. No native attempts. |
| 1102 | Maintained universal policy: four accepted; no native attempts. |
| 1103 | Universal policy stops at input 20/73: case104 grows from 45.414017 to 49.298524 mm. 53 unattempted, zero native attempts. Reject this version. An inherited review sentence about exact collateral equality was corrected in a separate erratum; budgets and executable stop criteria were unchanged. |
| 1104 | Revised typed policy: four evaluated/accepted, all three collateral first/final routes exact. |
| 1105 | Revised maintained policy: 73/73 evaluated, 63 accepted, 10 unresolved, none skipped or unattempted. |
| 1106–1108 | One exact fresh solve/native build/named fidelity audit/bounds check and reviewed view, as above. No retry. |
| 1110 | Restart the ordinary tester with the same settings and a new source-consistent streak. |

Verification: 102 unique affected tests pass, including scale-dependent closure,
ordered-frame half-turn rejection, unchanged exploratory stopping, malformed policy
and caller-stop coverage. Scoped Ruff lint/format checks cover five files. Three
changed Python files receive complete IDE inspection with no new findings. One
pre-existing 18-line duplicate-code hint remains in the unchanged Newton loop.
Initial IDE test-typing findings and formatting were corrected; passing unaffected
checks were not repeated. Complete source/new-test and documentation diff review
and whitespace review apply. IDE call-analysis discovery was unavailable through
the exposed command schema; the three actual consumers were inspected directly.
No full/repository-wide QA or production promotion is claimed.

## Campaign continuation

Restart 1110 retains seed 2633163134, all current ranges, one-degree roll increments,
solver settings, nonadjacent-zone rule, ten-second preview, keep-awake and replayable
screenshots in `~/Pictures/test4`. Its new journal is
`range-0a9d851b83fc481a9d7a955b6cc37e12` under gym697/workspace/range-tests. Launch
and keep-awake are confirmed active. The live journal is authoritative for later
counts. Maximum 1,000 cases and normal first-problem stops remain unchanged.

Through the preceding run: 191 ordinary attempts, 188 passes, three exceptions,
71 distinct target configurations and a longest campaign streak of 70. All three
campaign exceptions now have qualified solver/rule repairs. These manual checks
do not add ordinary tester passes. The 1,000-consecutive-pass goal remains unmet.
The [campaign ledger](../experiment_ribbon_regression/CAMPAIGN.md) records the
user's consolidation interval of 20 exceptions; no layout-specific output edits
are permitted as repairs.
