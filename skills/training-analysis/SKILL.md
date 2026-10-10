---
name: training-analysis
description: Analyze Intervals.icu training periods or compare activities with explicit source availability, units, and sample coverage.
---

Read `intervals-icu://plugin-capabilities` for current support. Use `icu_get_training_summary` for period totals and `icu_compare_activities` for 2–10 specific sessions. Obtain IDs from adapted activity reads; use streams/intervals only when the question needs them.

Use athlete-local calendar dates. Ask for an unresolved period only when it materially affects the answer; otherwise state the selected range. Separate indoor, outdoor, and unknown environments when comparing running pace. `intensity_percent` is a percentage; `intensity_factor_ratio` is the ratio. The legacy `intensity_factor` is a deprecated percentage field.

Inspect `metadata.complete`, missing sample counts, source restrictions, and pace/distance units before interpreting totals. A complete fetched list can contain restricted metrics. When incomplete, call the sums partial observed totals. Do not infer zero from absent fields or improved fitness from pace alone. Return evidence-backed observations and their concrete limits.

