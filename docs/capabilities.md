# Website / API / plugin capability matrix

Evidence date: 2026-10-10. Website inspection used read-only navigation. API support is checked against the [official OpenAPI](https://intervals.icu/api/v1/docs), not private browser endpoints.

| Website capability | Existing upstream support | Community wrapper 1.1.0 | Boundary |
|---|---|---|---|
| Activity list and details | Recent/date/search/detail tools | Raw-field replacements for recent/date/detail | Search formatting remains upstream |
| Streams, intervals, best efforts | Streams, intervals, search, histogram tools | Retained | Restricted sources may return no metrics |
| Fitness, fatigue, form | Profile/summary/fitness chart | Metadata and recovery workflow | Legacy recommendations/date logic retained |
| Sleep, HRV, wellness | Read/write wellness tools | Zero-preserving reads and sample-aware recovery | No medical diagnosis or invented score |
| Power/pace/HR curves | Curve tools | Retained with intensity metadata | No promise to reproduce website models |
| Totals and period statistics | Primitive activity reads | Training summary with filters and grouping | No combining incompatible zone sources |
| Activity comparison | Primitive activity reads | 2–10 activity side-by-side comparison | Unknown environments remain unknown |
| Calendar and planned workouts | Read/create/update/bulk/duplicate/apply tools | Preview and UID-upsert commit with verification | Legacy write tools remain direct writes |
| Plan adherence | Primitive activity and event reads | Explicit paired_event_id matching | Unpaired is unconfirmed |
| Workout library | Folder/workout read/write tools | Retained, plus file conversion export | No sharing/permission expansion workflow |
| Annual training plan builder | Annual-plan event reading | Retained reading | Observed account shows subscription gate; no builder bypass |
| Activity / workout export | Activity file downloads | Bounded exclusive local files; FIT/ZWO/MRC/ERG workout export | No overwrite / Base64 default |
| Gear and maintenance | Gear/reminder tools | Retained | Deletion disabled |
| Sport thresholds/settings | Sport-setting tools | Retained | User must authorize configuration changes |
| Custom fields/charts | Custom-item tools | Retained | No claim of complete UI chart authoring |
| Athlete coaching | Athlete listing and explicit athlete IDs | Existing scoped reads retained | First release targets personal accounts |
| Routes, route matching, weather | No exposed route/weather tools | Not added in v1 | Route page showed subscription gate |
| Groups / chat | Activity messages only | Retained | No complete social/group/chat API coverage |
| Upload activity files | Manual activity tools only | Not added in v1 | User may use native device sync/site upload |

Baseline: 61 tools (37 read hints, 24 write hints), 4 resources, 9 prompts with deletion off. Wrapper replaces 8 tools and adds 7: expected **68 tools**, 5 resources, 9 prompts. Local exports and previews advertise readOnlyHint=false because they change local state, although they do not modify remote training data. All destructive deletion tools are absent and middleware rejects deletion calls.

## New tool inputs

| Tool | Required inputs | Defaults/options |
|---|---|---|
| icu_get_training_summary | oldest, newest | sport_types=null; environment=all; group_by=week |
| icu_compare_activities | activity_ids | 2–10 unique IDs |
| icu_get_recovery_summary | none | days=28 |
| icu_get_plan_adherence | oldest, newest | explicit paired IDs only |
| icu_preview_training_plan | plan_id, events | allow_conflicts=false; stable event_key per event |
| icu_commit_training_plan | preview_id | 24-hour validity; current account only |
| icu_export_workout | format; event_id XOR workout_id | format=fit/zwo/mrc/erg; optional plain filename |

Date-window operations accept at most 366 inclusive days. Fetching is bounded by 40 logical windows and 5000 returned activities; up to three physical attempts can be made for a read window. Saturated windows split to single days; remaining saturation is reported. A fully fetched activity list can still contain incomplete or restricted metrics.

