---
name: plan-training
description: Preview and write an authorized Intervals.icu training plan with stable session identifiers, conflict checks and post-write verification.
---

Read `intervals-icu://plugin-capabilities` and `intervals-icu://workout-syntax`. Read recent training, wellness, sport settings and calendar as needed to build the requested plan. Use native structured workout syntax, with duration/distance first on '- ...' lines.

Use `icu_preview_training_plan` with a stable plan_id and event_key per logical session. Reuse both identifiers for retries and edits. Present dates, courses, create/update/unchanged actions and conflicts before commit. A preview saves locally but does not write to the athlete's calendar.

When the user already explicitly authorized writing the specified plan, do not ask for that authorization again. Otherwise obtain authorization for the concrete preview before calling `icu_commit_training_plan`. Set allow_conflicts=true only when the user intends the shown conflicts. Remote changes or expired previews require a new preview, not a blind retry. Do not use legacy direct batch/create/apply tools to bypass this workflow for plan generation.

Inspect every commit result. Verified items succeeded; written_parse_unverified means the event exists but device-syncable steps were not verified. Failed/uncertain/not_attempted items do not constitute success. Keep identifiers for recovery; no deletion rollback is available. To assess execution use `icu_get_plan_adherence`; unpaired means unconfirmed, not missed.

