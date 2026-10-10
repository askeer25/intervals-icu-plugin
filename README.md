# Intervals.icu Plugin

[![CI](https://github.com/askeer25/intervals-icu-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/askeer25/intervals-icu-plugin/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Your training log, recovery data, and workout plans—available to your local AI assistant.**

Intervals.icu Plugin connects Codex and other local MCP clients to your personal [Intervals.icu](https://intervals.icu) account. Review training, compare sessions, check recovery trends, preview a training week, and export structured workouts from one conversation.

[中文说明](docs/README.zh-CN.md) · [Quick start](#quick-start) · [Examples](docs/examples.md) · [Documentation](docs/README.md)

This is an **unofficial community integration**, built on [`intervals-icu-mcp`](https://github.com/hhopke/intervals-icu-mcp). It runs locally with your own API key. Version 1.1.0 provides **68 tools, 5 MCP resources, 9 prompt templates, and 4 bundled skills**. Deletion is disabled.

## Highlights

- **Training summaries:** totals and daily, weekly, or monthly groups, filtered by sport and indoor/outdoor environment.
- **Activity comparisons:** compare 2–10 sessions with explicit units, missing metrics, and source information.
- **Recovery trends:** sleep, HRV, resting heart rate, fatigue, and training load, with sample counts and observation dates.
- **Plan review:** compare planned sessions with explicitly paired activities; an unpaired session remains unconfirmed.
- **Previewed planning:** inspect proposed changes and conflicts, then commit with stable identifiers and per-session verification.
- **Workout exports:** save FIT, ZWO, MRC, or ERG files locally without overwriting existing files.

The upstream activity, interval, curve, calendar, library, gear, and sport-setting tools remain available. See the [capability matrix](docs/capabilities.md) for the exact support boundary.

## Quick start

### 1. Get the project

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone the repository:

```bash
git clone https://github.com/askeer25/intervals-icu-plugin.git
cd intervals-icu-plugin
uv sync --locked --no-dev
```

You can also download a source ZIP from [Releases](https://github.com/askeer25/intervals-icu-plugin/releases). Run the following commands from the extracted project root.

### 2. Connect your account

Open [Intervals.icu Settings](https://intervals.icu/settings) and find **Developer Settings** to obtain your personal API key. Enter it in the local terminal, not in chat:

```bash
uv run --locked --no-dev intervals-icu-plugin setup
uv run --locked --no-dev intervals-icu-plugin doctor
```

`setup` verifies the connection and saves credentials in your operating system's secure store. Use athlete ID `0` to select your own account. If a secure store is unavailable, use the [environment configuration](docs/configuration.md#environment-variables).

### 3. Install in Codex

```bash
codex plugin marketplace add .
codex plugin add intervals-icu@intervals-icu-community --json
```

Refresh or restart the host, open a new chat, and ask:

> Summarize my training over the last seven days, and show which metrics are missing.

Hosts with a Plugins UI can install from the registered `intervals-icu-community` marketplace. The `uv` command must be on the host application's PATH.

<details>
<summary>Use with another local MCP client</summary>

After setup, add this server to your client's MCP configuration. Replace the project-root placeholder with your extracted or cloned directory:

```json
{
  "mcpServers": {
    "intervals_icu": {
      "command": "uv",
      "args": [
        "run", "--locked", "--no-dev",
        "--project", "PROJECT_ROOT",
        "intervals-icu-plugin", "serve"
      ]
    }
  }
}
```

This configuration uses local stdio. A hosted ChatGPT connector or shared multi-user server is outside this release.

</details>

## Try it

| Goal | Example prompt |
|---|---|
| Review a training block | “Summarize this month's running by week. Separate indoor and outdoor sessions.” |
| Compare sessions | “Compare these two runs: pace, heart rate, duration, and training load.” |
| Check recovery observations | “Show my last 28 days of sleep and HRV, including sample coverage.” |
| Review execution | “Compare last week's workouts with the activities explicitly paired to them.” |
| Plan a week | “Draft next week's sessions, preview the calendar changes, and show conflicts before writing.” |
| Export a workout | “Export tomorrow's planned workout as a FIT file.” |

See [worked examples](docs/examples.md) for tool inputs and expected behavior.

### How plan writing works

1. **Preview:** validate the proposed events and inspect create/update/unchanged actions and conflicts. This step writes only a local preview file.
2. **Review:** confirm the concrete changes. If the user has already clearly authorized writing that plan, no repeat authorization is needed.
3. **Commit:** check that the calendar still matches the preview, upsert stable UIDs, and read back each result.

Keep the same `plan_id` and `event_key` when retrying or editing a logical session. Changing an event key creates a different session. Previews expire after 24 hours; changed calendars require a fresh preview. Partial results are reported individually and do not trigger deletion rollback.

**Legacy upstream write tools are still direct writes.** Use the bundled planning skill or the new preview/commit tools for this workflow.

## Requirements and support

| Component | Requirement |
|---|---|
| Runtime | Python 3.11+ and uv; dependencies are pinned by `uv.lock` |
| Account | Your own Intervals.icu account and personal API key |
| Client | Codex or a local stdio MCP client |
| Operating system | Windows, macOS, or Linux; see [validation status](docs/validation.md) |

The first install needs Internet access. The service runs locally; activity and wellness queries still contact Intervals.icu. Windows installation and stdio startup have been validated locally. The CI badge reports the current cross-platform check status.

## Data and compatibility

The adapted activity and wellness reads preserve `0` and `false`, make intensity units explicit, and use athlete-local dates. Summaries report partial fetching and missing samples instead of treating absent data as zero.

- **Website visibility is not API availability.** Strava-sourced activities may return restricted stubs. An [official notice dated 2026-10-09](https://forum.intervals.icu/t/api-access-to-intervals-icu/609) warns of possible Garmin API restrictions; the plugin does not assume every Garmin record is blocked.
- **Subscription gates still apply.** The plugin does not bypass paid website features.
- **Recovery outputs describe observations.** They do not invent a composite readiness score or diagnose overtraining.
- **Compatibility is bounded.** Unreplaced upstream tools retain their original formatting, date logic, and HTTP behavior. Activity downloads now return local paths rather than Base64 by default.

Read the [capability matrix](docs/capabilities.md), [audit](docs/audit.md), and [privacy notes](docs/privacy.md) for details.

## Documentation

| Guide | What you'll find |
|---|---|
| [Configuration](docs/configuration.md) | Secure credentials, environment variables, timezones, and local files |
| [Examples](docs/examples.md) | Prompts, structured plan inputs, and export calls |
| [Capabilities](docs/capabilities.md) | Website/API/plugin coverage and compatibility boundaries |
| [Troubleshooting](docs/troubleshooting.md) | Authentication, missing data, conflicts, and export errors |
| [Validation](docs/validation.md) | Tested behavior and checks not yet performed |
| [Release guide](docs/releasing.md) | Build and verify a distributable plugin package |

## Development

```bash
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked pyright
uv run --locked python scripts/build_release.py
```

The release script validates manifests, scans distributable files, and creates a plugin/source ZIP with SHA-256. Local credentials, previews, exports, and virtual environments are excluded.

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), or [open an issue](https://github.com/askeer25/intervals-icu-plugin/issues) with reproducible steps. For sensitive reports, follow [SECURITY.md](SECURITY.md).

## Acknowledgements and license

The MCP foundation is [`hhopke/intervals-icu-mcp`](https://github.com/hhopke/intervals-icu-mcp), installed as a pinned dependency rather than copied into this repository. See [NOTICE](NOTICE) for upstream credits.

Released under the [MIT License](LICENSE). This project is not affiliated with or endorsed by Intervals.icu, Garmin, Strava, or OpenAI.
