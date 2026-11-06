# Frozen gym regression corpus

`gym-v1.json` is the development inventory assembled during the November 5
consolidation. It contains the union of all 21 distinct non-cancelled problem
inputs in the 43 saved range journals and the 43 retained numerical controls:
54 exact target payloads. Original job paths, plan hashes, source digests,
settings and dispositions remain attached to each input. Replays use saved
coordinates and frames directly; seeds never regenerate targets. These are
examined development inputs, not untouched validation families.

All cases remain in the denominator. Eight have adjacent cubicles under the
current placement definition; they remain useful legacy stress inputs. Placement
eligibility is separate from physical feasibility. An older unresolved input must
not be silently removed or relabelled physically impossible.

Run an explicit numerical baseline, then compare an unchanged candidate:

```sh
uv run --python .venv/bin/python -m experiments.experiment_ribbon_regression.runner --output artifacts/verification/NEW-baseline
uv run --python .venv/bin/python -m experiments.experiment_ribbon_regression.runner --output artifacts/verification/NEW-candidate --baseline artifacts/verification/NEW-baseline
```

Read the project experiment safeguards first. Each invocation freezes its corpus
and implementation hashes before launching one isolated worker per input. Limits
are 54 executions, 15 seconds per execution, a 17-second subprocess guard, 120
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
