# Fusion 360 Cable Bundler roadmap

The current release is the stable baseline for interactive harness definition, routing preview,
and cable-solid generation. Near-term work should preserve that behavior while concentrating on:

- keeping the focused automated suite and live Fusion checks aligned with current product behavior;
- validating the add-in on Windows when a suitable Fusion host becomes available;
- profiling large harnesses and tightening only demonstrated routing or diagram bottlenecks;
- improving recovery and diagnostics for damaged external Fusion references; and
- packaging and release documentation once distribution requirements are settled.

New routing, persistence, or topology features should be introduced behind focused regression
coverage and verified against representative live Fusion geometry before becoming defaults.
