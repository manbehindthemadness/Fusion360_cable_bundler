> Fixed-sample exception (Nov9): the explicit 100-layout failure-rate goal
> continues past preserved geometry failures, without retries or solver changes.
> Source/resource/cancellation/logging/host errors still stop for review. The
> first-failure protocol below remains the default for other validation runs.

# Generalized recovery and validation rules

The user's fresh-input directive supersedes historical fixture-replay requirements
for future validation. Earlier specimens supplied mechanism evidence; their routes
are no longer reference outputs or a qualification matrix. Existing raw records
remain archived for provenance. Active comparisons retain aggregate statistics and
non-replayable novelty fingerprints. No deletion or revised historical pass credit
is implied.

## Geometry and recovery

- Preserve fixed target poses, conductor identity, explicit material order and the
  entire joined profile. Contact guidance follows actual material phases at mating
  folds, rather than assuming separate piece labels imply separate material.
- Keep independently measured self-contact and terminal-hardware witnesses in the
  same recovery problem. Each occupied hardware member retains its own separating
  box halfspace; different members can clear different faces.
- Distinguish quality preferences inherited from an invalid starting route from
  physical acceptance rules. A typed, measured blocked-mating continuation may
  release an inherited length ceiling only after its existing bounded projection
  stalls. A clear baseline retains strict quality acceptance. Generic or malformed
  stalls cannot enable this continuation.
- Recovery consumes genuinely unused work from the original allocation. Keep
  update, Newton, CPU, wall, contact-pair and hardware limits unchanged. A finite
  projection failure does not establish physical impossibility.
- Reuse placement prefixes only for exact immutable inputs through the same
  placement/validation kernel. Bound caches per model; do not change geometric
  arithmetic, inputs, witness traversal, tolerances or optimization steps.
- Measure native construction and named fidelity separately. Preserve raw errors,
  warning counts and failed or incomplete attempts. Native fidelity does not prove
  the unmeasured full physical audit.
- Apply the gym stress envelope after native construction. It cannot guide solver
  geometry or become an outcome-based input filter. No case identifiers, saved
  route matching, seed-specific branches or fixture-specific settings belong in a
  generalized solver rule.

## Fresh validation protocol

1. Freeze scope, input ranges, source hashes, physical checks, resource bounds and
   first-failure stop before solving. Use analytical/synthetic mechanism tests for
   code QA; retire historical geometry replay from qualification.
2. Use `FreshRegistry.prepare` in `fresh.py` with a finite random specification.
   It draws a fresh 32-bit run seed and checks actual endpoint/profile geometry
   against registered fingerprints and the whole proposed schedule. Reserve all
   layouts before starting the ordinary tester, including the unattempted tail.
   Reject duplicate seed proposals before outcomes; never resample a failed solve.
   Preparation stops after sixteen proposals or thirty seconds without solving.
3. Persist the returned specification, fingerprints, source/helper hashes and
   comparison metadata in the current run's ignored plan, then pass that exact
   specification to the ordinary tester's `start` action. The manual range tester
   alone does not enforce novelty; fresh validation must use this preparation.
4. Keep one solver source throughout a run. Stop at the first numerical, native,
   fidelity, boundary, harness or resource problem. A solver change starts a new
   run with a new seed and novel layout schedule; it does not repair the old run's
   first-attempt statistics. Keep the 4 GiB RSS cap and twenty-minute reviews.
5. After collection, use `summarize_journal` and `FreshRegistry.record` once.
   Report planned, attempted, finished, unattempted and uncollected counts; separate
   numerical acceptance, native attempts/builds/fidelity, warnings, timing goals
   and full-physical-audit gaps. Repairs receive no first-attempt pass credit.
6. Compare aggregate first-attempt rates, failure stage, first-failure ordinal and
   timing distributions under matching sampling/check contracts. Label source
   changes, mixed-source runs and replay populations explicitly. First-failure
   stopping produces variable sample sizes; do not pool selected successful
   prefixes or claim universal reliability from a finite streak.

Novelty covers registered runs and known retired inputs imported as hashes. It
cannot establish uniqueness against unrecorded historical layouts. Hash rounding
only merges numerical aliases in the novelty index; actual solver coordinates
remain unchanged. Current-run evidence remains frozen until outcomes are collected;
completed layouts and screenshots are never used as future reference fixtures.

The comparison registry lives under ignored
`artifacts/verification/ribbon-fresh-runs/novelty.sqlite3`. Back it up with the
aggregate statistics; losing it loses the cross-run novelty guarantee. No native
solver, builder, physical rule or resource allowance changes in this policy update.
