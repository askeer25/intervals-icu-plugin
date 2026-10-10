---
name: export-workout
description: Export a planned or library Intervals.icu workout to a local FIT, ZWO, MRC or ERG file without overwriting existing files.
---

Find the event or library workout with the calendar/library tools. Use `icu_export_workout` with exactly one of event_id or workout_id, the requested format, and optionally a plain filename. Use FIT for compatible device workflows when the user has not specified a format, and state the choice.

Check the returned saved_to path and format. Deliver the real absolute file link. Existing files are never overwritten; choose a new name if needed. An export does not imply device upload or synchronization. Do not publish or upload the file unless requested. For recorded activity files use the adapted activity download tools; their output_path is restricted to the application's exports directory.

