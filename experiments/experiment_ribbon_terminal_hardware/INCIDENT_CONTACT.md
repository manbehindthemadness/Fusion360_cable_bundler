# Incident-joint recovery and local contact guidance

2026-11-07. Continuation of [case63 contact diagnosis](CONTACT_DIAGNOSIS_63.md).
The maintained experimental v2 solver now repairs this excursion within the
existing work limits. It is not a production promotion or universal success claim.

## Rule and scope

The selected improving, depth-unresolved contact branch may also contain a
verified fold/connector intrusion. For that combination, reflect the evidenced
incident joint and allow its angle, bank and adjoining straight runs to close
the fixed caps. Other fold signs, event order, radii, conductor profile and fixed
end poses remain authoritative. Proven self-penetration retains the previous
contact-first recovery: replacing that path regressed an existing control in1085.
There is no case identifier, seed lookup, saved solution or candidate angle search
in the implementation.

Coupled correction uses cap closure, measured finite-hardware gaps and at most
four retained local contact constraints. For a verified crossing on flat material,
guidance separates the complete incident flat spans and actual profile-arc prisms,
rather than entire folds or just a single point. The deterministic closest signed
separating axis supplies motion guidance. The parent route's strict-shortening
ceiling is an inequality, not a target to grow toward. Guidance never certifies
clearance; unchanged whole-volume contact and both hardware checks must pass.

An optional bounded convex-hull probe can discover actual penetration early.
Each proposed witness must pass both original strict inverse material maps.
A miss or support-query exhaustion never means clear and omits no original cells.
After the first verified crossing, further optional probing is disabled for that
recovery. The final certificate uses the original analytic whole-volume checker.
An optional512entry cache reuses identical immutable cell/axis projections without
changing arithmetic or traversal. Legacy callers keep the original default path.

The same remaining four updates,24Newton steps,.35CPU/2wall seconds and shared
contact pool apply, reduced by preparation already spent. No second strategy gets
a fresh allowance. The first-pass4wall seconds/2048comparisons and1024per-certificate
ceilings remain. The triggering correction uses3updates,16Newton and534comparisons;
the final unchanged proof consumes518of those comparisons. Optional probe support
work is capped at2048queries. Contact tolerances and acceptance rules are unchanged.

## Qualification and separate native result

Source lock:243files. Maintained cold four-input replay1088 evaluates all four:
the trigger is accepted, and three previously accepted comparison configurations
retain exact first-pass and final geometry. The trigger's first pass is
49.269716752934706mm; its smoothed route is49.76158528695945mm, exactly matching
the qualified prototype. Its cold solve takes1.671335CPU/1.676978wall seconds.

Maintained complete-corpus replay1089 evaluates73independent configurations:
60accepted,13unresolved, none skipped or unattempted. All59other previously
accepted routes retain exact first-pass and final geometry. Only the trigger alias
changes, replacing854.374208944mm with49.76158528695945mm. Independent finite
hardware checks pass for every acceptance. This is numerical coverage; the other
72configurations receive no new native attempt. Corpus wall time70.482488seconds.

One fresh ordinary Fusion solve1091 reproduces the exact reviewed49.761585mm route:
1.841288CPU/1.955621wall seconds. One native attempt builds one joined solid and
passes named fidelity with no warnings:9,800points,540seams, maximum sampled error
1.6324063550874774e-9mm. Its282faces/280audited patches are workload, not additional
independent configurations. No full physical audit is claimed.

Native generation1.146770seconds comprises translation.147195, definition.100134
and kernel.899441seconds. Audit1.413201seconds is separate; whole native workflow
16.263433seconds includes other overhead. SolveCPU exceeds matched generation time,
so that performance goal is **missed**, although all hard budgets hold. Optional
UV metadata remains available; this case has material_uv=false and creates no
appearance or bitmap. Material work is not charged as geometry generation.

Native precise component bounds1093 pass the unchanged one-extra-cubicle-layer
plus10mm allowance, with0excess against±55mm. Minimum(-.728364,-12.310416,-21.008983),
maximum(13.638015,21.271701,-.443043)mm. The body revision remains unchanged during
view inspection. The viewport capture was reviewed. Old rejected47mm and original
854mm bodies/journals are retained hidden; the native owner targets the new body.
Maximum sampled native RSS2,247,104KiB; in-flight peak is not measured. One native
attempt/120seconds/4GiB and3.8GiB launch headroom remain unchanged.

Verification:269unique focused/affected tests pass; Ruff lint/format on16changed
Python files pass. All16receive IDE inspection; no new findings, six pre-existing
duplicate-code hints remain in contact.py/solver_v2.py. One inspection timeout was
retried successfully. Complete source/new-file diff review is complete. No full or
repository-wide QA, other72native builds or full physical audits were performed.

## Retained experimental dispositions

All prototypes below concern dependent variants of the same physical trigger,
except explicitly named frozen controls/corpus. Their accumulated expense is not
one solver allowance. Failed scripts and interrupted records remain under ignored
artifacts/verification/ribbon_terminalNNNN. No later audit retroactively accepts an
earlier interrupted run. Preparation/import/orchestration are excluded from CPU
figures unless a complete solve is identified.

| Phase | Disposition |
| --- | --- |
|1060|Broad-phase lower-bound sign wrong; probe misses; no clearance claim.|
|1061|Correct sign; actual strict crossing found in.011255CPU,180part comparisons.|
|1062|Leaf-only probing wastes pool on mating regions;610comparisons unresolved.|
|1063|Probe only nonmating regions; strict crossing578comparisons/.087543CPU.|
|1064–1065|BVH pair ordering exhausts2048support queries; unresolved.|
|1066|Original top-level stack order finds crossing192comparisons/.046753CPU.|
|1067|Point-fiber corrections leave another crossing; CPU stop.337635vs.336097. Six returned Newton omit completed inner work; actual16completed,24upper bound.|
|1068|Flat-span harness declines a1.64e-12mm G1join classification discrepancy; no geometry result.|
|1069|Guidance-only join-roundoff classification; local prism gap.168140mm versus whole-fold4.26mm; no clearance claim.|
|1070|Complete flat constraints close; optional probe support cap still stops final proof.|
|1071|Disable probe after first hit;610total comparisons/.338411CPU, no acceptance.|
|1072|Separate diagnostic original proof clears corrected49.2697mm route in446cells/.267916CPU; does not renew runtime allowance.|
|1073|Alternative support-bound prototype still unresolved in418cells; not adopted.|
|1074|Whole-phase convex-hull negative probe finds strict witness in2comparisons/.006999CPU.|
|1075|Hull plus BVH probing exhausts2048support queries on another pair.|
|1076|Bounded8step hull-only probe finds real crossing16comparisons/.012632CPU.|
|1077|First complete same-budget acceptance:3updates/16Newton/534comparisons/.325002CPU.|
|1078|Fresh full prototype accepts49.7616mm; combined recovery preparation included.345341CPU.|
|1079|Three frozen controls accepted, exact prior first-pass/final routes.|
|1080|Corpus harness import failure before first case;0/73evaluated, all unattempted.|
|1081|Fixed harness stops43/73when trigger CPU fallback returns854mm;30unattempted.|
|1082|Bounded cell/axis cache preserves exact518cell proof, reducing it to.080463CPU.|
|1083–1084|Cold cached prototype accepts exact compact route; three controls remain exact.|
|1085|Corpus stops45/73on historical-208c6aa74e2e regression;28unattempted. New reflection replaced a working proven-contact path; rejected admission policy.|
|1086|Certainty-based admission preserves legacy proven-contact path; trigger accepts, combined recovery.296919CPU.|
|1087|Full prototype corpus73/73:60accepted/13unresolved;59other accepted routes unchanged.|
|1088–1089|Maintained four-input and complete73input results above,0native attempts.|
|1090|Read-only live input/ownership/idle/headroom check passes.|
|1091–1093|One fresh exact ordinary solve/native build/fidelity audit and bounds/view inspection pass as reported above.|

## Autonomous tester continuation

1094starts a new journal/streak using the exact existing ranges, seed2633163134,
solver settings,1degree rolls, screenshots in~/Pictures/test4,10second preview,
nonadjacent-zone rule and keep-awake option. Maximum1,000cases, normal first-problem
stop, existing CPU/RSS limits and all earlier journals are preserved. No in-flight
solver changes. The new directory is range-fa91816c3bf845c59e6cdc038f79ccb2 under
gym697/workspace/range-tests. At launch0attempts/0passes; start and keep-awake both
confirmed active. Future status/cases.jsonl are authoritative for live counts.

Before this restart, runs977+999total120ordinary attempts/118passes/2problems over
63unique inputs, longest campaign streak62. Both encountered problems now have
qualified repairs. Manual qualification and corpus replays do not increment tester
passes. The1,000consecutive-pass goal remains unmet. Subsequent failures must retain
their full inputs, native/numerical dispositions, counters and resource evidence.
