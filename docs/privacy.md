# Privacy

The service runs locally. Credentials are sent only to `https://intervals.icu` for authorized API calls. There is no plugin-operated server, telemetry, analytics, credential upload, or `.env` fallback. Dependency installation contacts public package registries through uv.

Credentials use the operating system store or the invoking process environment. Keyring plaintext/fail backends are rejected. API keys are excluded from diagnostics, reprs and responses. `doctor` returns account identity/timezone but no activity records or key. The host LLM can receive queried activity/health data through MCP; only request data appropriate to the user's task.

Local previews contain planned sessions and calendar snapshots, not credentials. They reside in the platformdirs user-data directory with owner-only permissions where the operating system supports them. Preview validity is 24 hours; expired files remain on disk for audit/recovery and locating moved sessions until the user removes them. Keep this history when managing the same plan on another machine. Exports can contain private location/health information. They are never included in releases. On Windows, filesystem ACLs are inherited from the user's profile; chmod-style modes alone do not provide ACL isolation.

`credentials clear` removes the two legacy service entries. It does not revoke the remote API key; revoke/regenerate that in Intervals.icu when necessary. Do not run this personal-account stdio service as a shared/multi-user HTTP service. Public service/OAuth deployment is outside this release.

