---
name: recovery-check
description: Review Intervals.icu sleep, HRV, fatigue and training-load trends using observed sample counts and dates.
---

Use `icu_get_recovery_summary` (28 days unless the user requests another window). Check covered days, each metric's valid_samples/latest_date, source attribution, and missing data before interpreting trends. Fetch specific days with adapted wellness reads when necessary.

Compare observed values over their actual dates. Sleep quality is inverted: 1=Great, 5=Poor. TSB derived from CTL−ATL is a training-load model output, not a clinical measurement. Do not invent a readiness score, diagnose overtraining, or treat missing HRV as low HRV. Explain what the available observations support and where the record is insufficient. This skill authorizes no wellness write unless the user requested one.

