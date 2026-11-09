# Spatial inspection prototype

Reusable project skill: [ribbon-spatial-inspection](../../.agents/skills/ribbon-spatial-inspection/SKILL.md).
Invoke it as `$ribbon-spatial-inspection` for shared spatial inspection and
prediction-before-probe work. The skill uses this package as its implementation.

This experiment measures spatial explanations before solver repairs. It does not
change the selected solver, native builder, joined profile, physical checks or
acceptance rules. Existing solver source pins remain unchanged. All inspection
calculations and probes run in the explicitly supplied project SDK subprocess;
Fusion renders frozen JSON and owns only its new palette/diagnostic component.
Do not reload cached solver modules in a live Fusion session to run this tool.

## One-case workflow

1. In the owned idle Fusion document, call `preparation.author(new_directory,
   document_id)`. It reserves one fresh random N5 gym layout, D0.75 mm, nonadjacent
   cubicles, all endpoint faces and signed one-degree rolls. Run the ordinary
   `experiment_ribbon_locked_solver.worker` once on the returned job using the
   configured SDK. Maximum120seconds/4GiB; zero native body attempts. Preserve any
   failure; do not resample for a more convenient demonstration.
2. In that same SDK, run this package's `worker capture directory`. It selects the
   original accepted route or the explicitly retained rejected candidate without
   solving again. Missing geometry stays unavailable. Freeze the baseline and
   source fingerprints in a new inspection plan. Capture is bounded to10seconds,
   2048self-contact pairs and512hardware cells, with the4GiB resource cap.
3. Create an explicitly owned Fusion component and
   `host.Inspector(component, document_id, directory, python_executable).show()`.
   Its four palette views and Fusion overlays share the exact frozen coordinates.
   Retain the returned inspector. Original route guide sketches and joined cap
   profiles start hidden. No BRep is created. Retain prior user output separately.
4. Review the full material layout and select a section. Sections include actual
   width-dependent fold entry/exit brackets and any measured contact witnesses.
   Material sections can curve through an oblique fold; the displayed center frame
   is not a rigid-profile assumption. Joined contour samples use the unchanged
   rational profile and exact material map. Display chords remain approximations.
5. Choose one coordinate and a nonzero small delta; predict a selected center
   material point's world XYZ displacement and explain cap compensation and risk.
   Commit the prediction. Its content digest is sealed before any probe execution.
   Prediction tolerance judges the explanation, never physical acceptance.
6. Execute the single probe. A cold subprocess uses the existing fixed-radius
   material model, one linear closure projection and at most six Newton/four
   halving retraction steps with actual ordered-cap certification. No retries or
   optimization search. Geometry budget:.35CPU/2wall seconds/4GiB. Requested
   straight motion is at most min(0.1D,0.001length); angles/banks at most0.25degree.
   Cap compensation beyond four times these local per-coordinate limits rejects.
   Ordered folds and intervening straight slots identify the material point across appearing/merged straight primitives. Removed folds or disappearance of the selected slot reject rather than inventing correspondence.
7. A closed proposal is recorded before separately bounded post-probe inspection
   (10seconds, original pair/cell bounds). Overlay the measured result and compare
   its displacement with the committed prediction. A blocked/stopped probe consumes
   the allowance; incomplete proposals and errors remain recorded. An open-cap
   baseline remains inspectable but cannot be repaired by a diagnostic probe.

The landmark follows its ordered fold or straight slot and normalized material fraction at
q=b=0; it is not an arbitrary nearest point or a claim of fixed material distance
when total length changes. Per-conductor labels follow unchanged profile order.
A contact witness identifies actual occupied material coordinates; unresolved
boxes or absent witnesses do not imply separation. Hardware boxes are declared
proxies, not measured physical connectors. Native and full physical audits remain
unmeasured. One diagnostic case and its perturbation are not generalization coverage.

All raw records belong under ignored artifacts. Active future validation still
uses entirely new seeds and layouts, comparing aggregate statistics rather than
replaying diagnostic specimens as holdouts.

## First live demonstration — 2026-11-09

Two independent fresh N5 configurations were reserved, solved once numerically,
and captured with91feature sections each. Zero native bodies were attempted.
These diagnostics are excluded from the fixed100-layout validation denominator.

- Seed968188463 (`artifacts/verification/resume1740`): the single geometry probe
  was blocked by the original primitive-index correspondence guard; no displacement
  score was claimed. That consumed attempt remains retained. This exposed the
  general need to follow ordered folds/straight slots when zero runways appear.
  The current landmark implementation and synthetic regression cover that rule.
- Seed4225515505 (`artifacts/verification/resume1741`): a sealed prediction for
  a+.02mm leading-runway request expected midpoint displacement
  [+.0053,0,+.0085]mm. The sole measured probe returned
  [+.006272391,+.000001441,+.010136817]mm: error.001903869mm,
  inside the precommitted.004mm tolerance. Cap position/frame residuals were
  1.8094e-14mm/3.7576e-16; bounded contact/hardware checks were separated/clear
  (242pairs/16cells). Geometry CPU.005075s; total CPU.112306s.

Setup failures remain recorded: a stale Fusion numerical import before authoring,
an interpreter-bootstrap failure before geometry execution, and a generated
display-script syntax error. The replacement launcher stripped Fusion's inherited
PYTHONHOME/PYTHONPATH; the identical sealed first prediction then reached its one
geometry attempt. Neither diagnostic geometry probe was retried. Closed proposals
are now recorded before correspondence checks; the first blocked implementation
did not retain its closed proposal, so that result cannot be reconstructed here.

The actual Fusion HTML bridge committed and launched the successful probe, and
the native overlay was captured. The exact-source readonly Safari mirror was
visually reviewed and its section slider exercised after prediction commitment.
Native floating-palette physical-pointer interaction was not verified. Focused
verification:11synthetic tests, Ruff check/format and changed-file IDE inspections
passed. This demonstrates the measurement loop and one matched prediction; it
does not establish broad spatial comprehension or improved solver reliability.
