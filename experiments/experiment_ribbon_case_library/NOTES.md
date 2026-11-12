# Selected case catalogue

This optional SQLite catalogue stores selected gym inputs for diagnostic regression:
layout and run seeds, conductor dimensions, ordered endpoint selections and exact
poses, solver settings, contact/native-point policy and resource limits, original
source digest, outcome and evidence location. Each immutable record is limited to
32 KiB. It contains no solved route, drawing, mesh, solid or Fusion object.

Fresh generation, novelty reservations and aggregate statistics remain separate.
The solver never reads this catalogue. Replaying a known failure can establish a
regression result; fresh unseen layouts remain the independent generalization
check. Replays receive no new-layout, fresh-pass or streak credit. Original failed
outcomes remain unchanged. Numerical/native replay requires its own bounded plan
under `experiment_testing_rules.txt`; catalogue commands never run the solver.

Default database: `artifacts/verification/ribbon-case-library/cases.sqlite3`.
It has its own SQLite application/schema identity. Opening a foreign database,
including the novelty index, fails read-only before any write. Do not connect it
to campaign generation or solver lookup. No IDE database connection is required;
only that inapplicable SQL data-source inspection is suppressed locally.

Run through the configured project SDK/uv after the required environment check:

```sh
uv run python -m experiments.experiment_ribbon_case_library save CASE_ID artifacts/verification/resume2145 4
uv run python -m experiments.experiment_ribbon_case_library list
uv run python -m experiments.experiment_ribbon_case_library export CASE_ID artifacts/verification/selected-case.json
```

`save` explicitly selects a finished run ordinal and copies values/provenance only.
Identifiers cannot be overwritten. `export` reconstructs an endpoint-only inspection
document labelled `diagnostic_replay` / `fresh_validation: false` / `not_run`; it
creates no Fusion geometry. Exact saved targets remain authoritative. Generator
drift beyond the existing handoff tolerance stops export instead of moving targets.
Existing export files are preserved. Keep only the current diagnostic/immediate
comparison in Fusion, with historical evidence and recipes on disk.

Initial smoke evidence:2147catalogue20KiB/3selected original failures;24catalogue/
fresh-index tests pass, scoped Ruff/format/IDE clear. Actual novelty database and
317source lock byte-identical through imports/export and separately planned
2148/2149/2150numerical rechecks. Three rechecks use1.943556solverCPU seconds total,
all remain unresolved,0native builds/Fusion objects/fresh credit.2149does demonstrate
an actual internal connector intrusion detected and constrained during motion.
These results establish inexpensive regression workflow and observed tool use;
fresh unseen cases still determine generalization. Original failure receipts and
known-case outcomes were preserved, not relabelled as new passes.

Checkpoint2193 rechecks all six selected recipes once under unchanged2190source:
six numerical attempts, all unresolved, zero native attempts or Fusion objects.
Solver CPU totals3.512211seconds; worker wall totals4.230382seconds, excluding
launcher/SDK-import overhead. Five cases exercise combined motion/retained
discovery; four obtain strict crossing witnesses through it. Discovering a crossing
does not establish a completed correction. Catalogue, novelty database and solver
lock hashes remain unchanged. Separate fresh2191/2192cohorts pass40/40named
native/fidelity/boundary checks; their statistics contain no selected replay credit.
Full physical audits remain unmeasured. This demonstrates low-cost regression
evidence and remaining failures, not generalization over those failures.

Checkpoint2203 uses seven input-only recipes after adding the selected2200case4
proof failure. Two pass numerically and five remain unresolved, with zero native
attempts in the replay. The material-return recipe passed2199but stopped on CPU
in2203after the same recorded updates and identical992comparison separation
certificate; retain both outcomes as timing-sensitive. Separate2204qualification
of mating-proof-2200-04builds once and passes named native fidelity and boundary
checks without warnings. It receives no fresh credit; full physical audit remains
unmeasured. Original failed receipts and catalogue outcomes remain unchanged.

Checkpoint2221 adds input-only flat-phase-2215-02 from the collected fresh2215case2
failure;8recipes occupy28KiB, novelty and source-lock bytes unchanged by saving.
2223current-source replay collects8attempts:3numericalpasses/5unresolved,0native/
freshcredit. One separate2224native qualification of flat-phase passes named fidelity
and boundary checks without accuracy warnings. Original failed outcomes remain.
Closed-motion previously passed2214but is now phase-clock unresolved; this known
preservation failure stays active and precludes a generalization claim. No replay
or native result is added to fresh campaign statistics. FullphysicalUNMEASURED.

Checkpoint2236adds input-only terminal-closure-2232-19 from the collected fresh
failure;9recipes occupy32KiB. Saving performs0solves/native/Fusion operations,
keeps original unresolved provenance and leaves novelty/source-lock bytes unchanged.
2237current-source nine-case replay collects3numericalpasses/6unresolved,0native/
freshcredit. Case19finishes local reclosure and reaches final proof; material-return
loses a prior pass at the original CPU limit despite identical correction vectors.
Both failures remain active. Subsequent2238static measurement of case19's exact
candidate separates contact712pairs/clears hardware100cells but does not change
the failed original allocation, qualify native geometry or add fresh credit.
