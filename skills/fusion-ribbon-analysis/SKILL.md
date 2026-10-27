---
name: fusion-ribbon-analysis
description: Generate reproducible ribbon-routing test cases and inspect solved paths in Fusion with shared numerical evidence, trajectory guides, diagnostic meshes, failure intervals and measurement graphs. Use for solver generalization tests and explaining suspicious ribbon shapes; this is not a native sweep builder or physical simulator.
---

# Fusion Ribbon Analysis

Use this as a shared investigative instrument: the user sees the geometry and
graphs; the agent reads the **same frozen measurements and interval records**.
Use it to challenge assumptions, locate where a failure starts and understand
which solver change may have caused it. Do not merely decorate a pass/fail result.

The maintained implementation is [`devtools/ribbon_analysis`](../../devtools/ribbon_analysis/),
outside the production add-in and experiments. Resolve this skill directory's
symlink to find its repository root. The package requires that repository's
`cable_bundler.routing.geometry`; it is reusable across candidates in this project,
not a standalone third-party Fusion distribution.

Read [references/api.md](references/api.md) when adapting a candidate or creating
a view. Numerical analysis imports no Fusion API. Graphics need Fusion's supplied
`adsk` and an explicitly owned development component in the active idle document.

## Working together

- For new batches,read [case generation](references/case-generation.md). The
  host-only generator freezes25%mandatory normal solos/combinations,25%known stress
  inputs/variations and50%independent randomized boundary challenges. Generate
  before solving,retain the complete JSON/seed/source digest,and never filter or
  resample based on success. Replay saved inputs;promote a useful failure to the
  versioned stress inventory only between runs. Finite randomized runs increase
  confidence,not prove universal generality. Endpoint-only scenario events remain
  intent until independently measured;unknown feasibility is not a known failure
  oracle. Keep all solver failures/exhausted/unattempted cases in the denominator.

- Start from the user's question and an existing candidate when possible. Keep
  its identities, material ordering, fixed target poses and source provenance.
  Accept a stable path through the documented protocol; do not reach into a
  particular experiment's global ledger or infer which scratch belongs to us.
- Read project safeguards before planning/running solver work. Freeze the question,
  candidate IDs, rule version, measured scope and resource bounds within existing
  authorization. Do not expand searches or native batches through this skill.
- Analyze once, then render and inspect the returned `Evidence`. Its target copy,
  sampled series, failure regions and guide cubics are immutable. Later solver
  changes require a newly identified snapshot; never repaint old evidence as new.
- Every displayed result retains hidden native A/center/B route sketches from
  those frozen cubics, including unsuccessful routes. Keep these originals
  available to unhide in Fusion independently of diagnostic graphics. Never
  substitute target-gap witnesses or repaired geometry for the original paths.
- Every result also keeps individually hidden `Constraint - ...` geometry helpers.
  Use these to compare actual versus minimum bend radius, containment, material
  progress and target frames. Read the same frozen overlay measurements yourself.
  Supply solver-bound metadata explicitly; never infer it from a relaxed shape.
  Distinguish local margin and reached coordinate bounds from evidence that a rule
  actually prevents closure. Constraint ablation requires a separately bounded run.
  Solver summaries and individual solver-value panels start visible in every new
  result. Solver details belong in a sketch directly inside their experiment, not
  a separate solver component; preserve the complete source/measurement snapshot.
  Keep coordinate-value/trial panels visible by default when an adapter supplies
  them. Preserve the user's later manual visibility choices when reusing results.
  Physical constraint helpers and original route sketches still start hidden.
  Reserve separate titled description slots for every helper, even while hidden,
  and inspect them visible together. Keep real geometry witnesses in place.
- Show baseline, near-limit and failing variants when they answer the question.
  Track their parentage; variants are not independent solver coverage. Preserve
  failures and missing measurements. Distinguish a sampled rule violation from
  physical impossibility and native construction failure.
- Inspect entry/exit **brackets**, the full affected interval and worst point.
  Ask what changed before the visible symptom: a reversal near the end may be the
  exit from a much longer folded region. Read clean baseline extrema too.
- Keep labels, plotted trace, highlighted region and reported numbers aligned.
  Review a viewport capture for contrast and overlapping failure visibility.
  `CustomGraphicsText.formattedText` is the editable text property. Frozen
  overlapping material sheets are diagnostic illustrations, not valid solids.
- Keep solver, analysis, guide construction and graphics timings distinct.
  Cached analysis excludes search. Use bounded sampling and RSS checks; no mesh
  all-pairs audit, automatic refinement, repair or repeated builds by default.
- Preserve earlier views and ledgers. The viewer changes only its own children;
  hide, save or delete other content only within the user's existing instruction.
  Source drift stops work; do not silently reload modules holding live evidence.
- Explain the observed cause and a specific investigation direction. No graph or
  mesh establishes equilibrium, strain, contact, continuous compliance or Fusion
  kernel success. Native validation remains separate.

## Maintaining the instrument

Mark failed or unresolved candidates with a large red camera-facing outline.
Pass an explicit `failure_reason` to `Viewer.add` or `draw_evidence` for routing,
closure or native failures; sampled red violations are outlined automatically.
Amber warnings alone do not imply failure. For existing frozen views or a later
native failure, use `failure_markers.retain_failure_marker` with the original
component and evidence. Preserve geometry and old provenance; record an additive
display revision when annotating an older gallery. See the API reference.

Improve it from observed collaboration needs. Keep reusable analysis and graphics
in `devtools/ribbon_analysis`, fixtures/batches in `experiments/`, and app-owned
tests in `tests/`. Retain compatibility imports for historical callers while
moving implementations. Update this skill/API reference when the contract changes.
Use focused tests, Ruff and IDE checks for affected code, plus proportionate live
display checks. Preserve historical results and freeze new provenance after a
refactor; old fingerprints are not transferable evidence. Honor the user's choice
of output artifacts—do not create a new report file merely because analysis ran.
