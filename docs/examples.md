# Examples

## Training and recovery

Ask in natural language:

```text
Summarize my running this month by week, separating indoor and outdoor sessions.
Compare my two most recent outdoor runs. Identify missing metrics before drawing conclusions.
Show the last 28 days of HRV, resting heart rate and sleep, with valid sample counts.
Compare last week's planned workouts with explicitly paired activities.
```

The corresponding workflow tools are `icu_get_training_summary`, `icu_compare_activities`, `icu_get_recovery_summary` and `icu_get_plan_adherence`. Dates use the athlete's local calendar. A completely fetched list can still contain missing or restricted metrics; inspect completeness metadata and sample counts.

## Preview a structured workout

Read `intervals-icu://workout-syntax` for native course syntax. This is an input to `icu_preview_training_plan`; choose dates and intensities that match the actual request:

```json
{
  "plan_id": "base-week-1",
  "events": [
    {
      "event_key": "easy-run-monday",
      "start_date_local": "2026-11-02",
      "name": "Easy run",
      "category": "WORKOUT",
      "event_type": "Run",
      "description": "Warmup\n- 10m 70% Pace\nMain\n- 30m 80% Pace\nCooldown\n- 5m 60% Pace"
    }
  ]
}
```

The preview returns `preview_id`, expiry time, changes, conflicts and `can_commit`. It does not create a remote event. After reviewing the authorized plan, call `icu_commit_training_plan` with the returned ID:

```json
{"preview_id": "PREVIEW_ID_RETURNED_BY_THE_TOOL"}
```

Keep `plan_id` and each logical session's `event_key` stable across retries and edits. `allow_conflicts=true` belongs in the preview call only when the user intends the shown conflicts. If the calendar changes or the preview expires, preview again.

| Commit status | Meaning |
|---|---|
| `verified` | Written or already present, then verified; parsing checked when relevant |
| `written_parse_unverified` | Event exists but parsed workout steps were not verified |
| `failed` | A write failed; inspect the reported error type |
| `uncertain` | The result cannot yet be established; recover using the same identifiers |
| `not_attempted` | A prior failure or uncertainty stopped remaining writes |

There is no batch transaction or deletion rollback. Retained upstream create/bulk/apply tools remain direct-write interfaces.

## Export a workout

Provide exactly one of `event_id` or `workout_id` to `icu_export_workout`:

```json
{"format": "fit", "event_id": 123, "filename": "planned-session.fit"}
```

Use an actual event ID from the calendar. Formats are `fit`, `zwo`, `mrc` and `erg`. The result contains `saved_to`, format and byte size. An existing filename causes an error; choose a new name. Export does not imply device upload or synchronization.
