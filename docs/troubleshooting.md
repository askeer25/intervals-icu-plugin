# Troubleshooting

- **uv not found**: install uv from its official instructions and restart the desktop host so its PATH refreshes. Run `uv sync --locked` in the extracted project once.
- **Credentials missing / secure store inaccessible**: run `setup` in your own interactive terminal. Sandboxed Windows processes may lack Credential Manager access; this does not prove credentials are absent. Alternatively supply environment variables to the host. No plaintext keyring fallback is used.
- **401**: verify or regenerate the personal API key in Intervals.icu settings. **403**: check access to the requested athlete/resource; do not fall back to another account.
- **429**: reads retry only when Retry-After is at most 10 seconds; otherwise the error returns the delay. Wait and retry later. Writes are not blindly retried.
- **Empty or partial activity**: inspect availability/source metadata. Strava stubs and policy restrictions do not imply no training occurred. Unknown/missing data is not zero.
- **Summary incomplete**: narrow the requested period or filters. Capacity/request budget/saturated-day reasons are explicit. Never label the result a full training history.
- **Calendar changed / preview expired**: obtain a fresh preview. Keep stable plan_id/event_key identifiers. A new preview sees partial successes already present.
- **written_parse_unverified**: the event was written but the API did not return parsed steps. Inspect the native workout description; do not assume it will sync to a device.
- **Export already exists**: choose a new filename. Custom paths are restricted to the application's exports directory. Use doctor to locate the data directory.
- **Legacy direct tool differs from workflow**: see the audit boundaries. Added workflows guarantee only their documented behavior.

