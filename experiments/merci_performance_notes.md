# MERCI performance design reference

Recorded 2026-10-06. MERCI is a reference for numerical performance and geometry
representation, not an adopted solver or a demonstrated Fusion construction fix.
The useful direction is to share one geometry contract between prediction and
construction, with local constraints and explicit derivative information, rather
than repeatedly repair independently generated lanes.

## Source and evidence scope

Repository: [Inria MERCI](https://gitlab.inria.fr/elan-public-code/merci).
Inspected checkout: `experiments/experiments/external/merci`, revision
`c49e26d0dda3be9fa2e5c528a7303367c06f1ab7`, clean during inspection.
The clean checkout was moved to macOS Trash on 2026-10-06 at the user's request.
No imports, dependency registration, source modifications or integration into
the add-in were performed. Source links below target the inspected revision;
the remote host previously blocked browser access.

No configurations were evaluated, no native construction was attempted, and no
post-build audits ran. Runtime, memory, convergence and direct speed benefit for
our cases are unmeasured. The suggested gentle and spatial +45-degree tests were
not executed; there is no benchmark result or geometry-success claim.

## Useful design ideas

1. **Solve shape and boundary conditions together.** `MixedSuperRibbon` stores
   segment start positions/frames, lengths and curvature parameters. The fitter
   supplies endpoint position/frame constraints to the same optimization.
   This suggests encoding our exact cap conditions in the construction-compatible
   representation instead of correcting lanes after orientation selection.
   Exact conductor centers and native junction flow still require our own contract.
   Sources: [segment representation](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/MixedSRCore/MixedSuperRibbon.hpp),
   [constraint setup](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/LuaInterface/MRFitterFindEq.cpp).

2. **Keep neighboring elements locally coupled.** The mixed model uses constraints
   to join adjacent segment positions/frames. Its IPOPT interface supplies objective
   gradients, constraint Jacobians and Hessian structure/values. The architectural
   lesson is to exploit local dependency and sparse derivative structure; do not
   replace this with repeated whole-ribbon solid evaluation. This is a design
   opportunity, not evidence that importing their optimizer would be faster here.
   Sources: [element joins](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/MixedSRCore/Constraints/ConstraintLinkPosFrame.cpp),
   [optimizer interface](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/IpoptSolvers/IpoptMixedRibbon.hpp).

3. **Represent the surface explicitly, including slanted rulings.** A ruling is
   a straight line across the surface. Their mesh places its edges at
   `center +/- width/2 * (frameX + eta * frameZ)`, where `frameZ` is the centerline
   tangent. The transverse line can therefore slant along the route rather than
   always remain perpendicular. At clamped ends, separate ruling constraints can
   set `eta` to zero. This is a useful alternative to our assumption that equal-index
   conductor samples must share a perpendicular section plane. It does not prove
   compatibility with our lobed profiles, material conductor paths or Fusion lofts.
   Sources: [surface mesh](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/RibbonObjLib/ObjRibbonMesh.cpp),
   [start ruling constraint](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/MixedSRCore/Constraints/ConstraintEtaStart.cpp).

4. **Separate solve geometry from display/export sampling.** Curvature parameters
   drive numerical geometry evaluation; `RibbonPathGenerator` samples the result
   for output. A JSON descriptor exports distance, position, frame, curvature and
   `eta`, while a separate mesher writes OBJ geometry. An analogous boundary could
   let us measure and inspect candidates before building solids. Neither sampled
   output nor an OBJ mesh certifies continuous clearance or native interpolation.
   Sources: [sampling](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/RibbonObjLib/RibbonPathGenerator.cpp),
   [JSON exporter](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/LuaInterface/MRStdInterface.cpp).

5. **Make optimization cost and continuation explicit.** The fitter exposes
   iteration/evaluation counts, CPU time, constraint residuals and solver status.
   It optionally reuses multipliers and bound data between solves. These are useful
   reporting and interactive-regeneration ideas, but warm starts must be recorded
   separately from cold starts. Do not borrow the example budgets or silently
   add continuation steps. Sources:
   [solve and statistics](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/LuaInterface/MRFitterFindEq.cpp),
   [exposed statistics](https://gitlab.inria.fr/elan-public-code/merci/-/blob/c49e26d0dda3be9fa2e5c528a7303367c06f1ab7/code/src/LuaInterface/IpoptOptions.cpp).

## Limits for our application

The inspected model is a rectangular strip, not our ordered joined conductors and
split endings. Elastic equilibrium differs from shortest feasible routing; it can
change the centerline, unlike our current fixed-route experiment. Fusion still
needs a body whose geometry corresponds to the numerical representation. MERCI
does not establish our macaroni certificate, cap-to-branch compliance, combined
end allowance or native construction success.

The inspected plane-clearance constraints evaluate centerline or edge positions
at element boundaries, not a continuous swept-volume collision certificate.
`ConstraintClampOrBoundingSphere` bounds the first segment's starting position;
it is not our full-ribbon sphere-containment rule. These mechanisms should not
be mistaken for complete collision avoidance or self-contact support.

## Setup and adoption boundary

At inspection, the checkout had no existing build. On this ARM Mac, the PATH-selected CMake and
pkg-config executables are x86_64 and fail with `bad CPU type in executable`.
IPOPT and Lua development installations were not found in the checked Homebrew
locations; Eigen headers are present under `/usr/local/opt/eigen`. No dependencies
were installed and no build was launched. Setup would need a separately approved,
bounded environment before any benchmark.

Licensing documentation conflicts: the root README, license notice and inspected
source headers specify CeCILL 2.1, while the English installation guide retains an
academic-only/no-redistribution statement. Resolve that conflict before adoption
or copying code; these notes do not determine legal compatibility.

Keep these ideas as design references. Do not replace the solver, patch section
construction or run further tests automatically. Any future comparison must freeze
inputs and budgets, disclose different objectives/centerline freedom, and report
numerical performance separately from Fusion construction and diagnostic audits.
