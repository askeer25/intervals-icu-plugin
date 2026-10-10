# Configuration

## Secure credential store

Run `uv run --locked --no-dev intervals-icu-plugin setup` from the project root. The command uses hidden terminal input, verifies your account with a GET request, and stores the API key and resolved athlete ID in a supported OS store:

| System | Supported store |
|---|---|
| Windows | Credential Manager |
| macOS | Keychain |
| Linux | Secret Service or KWallet |

The service name is `codex-intervals-icu-mcp`, compatible with the earlier local installation. The plugin rejects plaintext keyring backends. A headless or sandboxed environment may not have access to a secure store; use environment variables in that case.

```bash
uv run --locked --no-dev intervals-icu-plugin doctor
uv run --locked --no-dev intervals-icu-plugin credentials clear
```

`doctor` reports versions, connection status, account identity, timezone source and data directory without printing the key. `credentials clear` removes local stored entries; it does not revoke the remote key or remove environment variables.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `INTERVALS_ICU_API_KEY` | Personal API key | Read from secure store when absent |
| `INTERVALS_ICU_ATHLETE_ID` | Default athlete | `0`, the authenticated athlete |
| `INTERVALS_ICU_TIMEZONE` | IANA timezone override, such as `Asia/Shanghai` | Athlete timezone, then system timezone |

Set these in the environment **inherited by the host application**. Values set in a separate terminal do not automatically reach an already-running desktop app. Do not put keys in chat, the repository, or a public MCP configuration.

An explicit nonempty API key takes precedence over stored credentials. API-key and athlete-ID selection are independent: an explicit athlete ID can accompany a stored key. The plugin does not automatically load `.env` files. Deletion is forced off regardless of the parent environment's `INTERVALS_ICU_DELETE_MODE` value.

## Local files

Previews and exports use the platformdirs data directory for `intervals-icu-plugin`; `doctor` prints its location. Preview files are valid for 24 hours and remain locally for audit, recovery and locating moved sessions. Keep preview history when managing the same plan on another machine. Exports may include private health or location data.

Exports are created exclusively, never overwritten, and limited to 50 MiB. A custom `output_path` on legacy activity downloads must remain inside the exports directory. Workout exports take a plain filename. Original activity downloads use `.bin` when the original format is unknown.

## Client configuration

Codex discovers the portable `plugin.json`, `mcp.json` and root `skills/` directory through the repository marketplace. Other local MCP clients can invoke `uv run --locked --no-dev --project PROJECT_ROOT intervals-icu-plugin serve` over stdio.

This release has no shared HTTP service or OAuth broker. Each local instance uses the owner's personal API key. See [privacy](privacy.md) and [capabilities](capabilities.md) for the supported boundary.
