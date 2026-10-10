# Validation record

This file describes required checks. Concrete local results are appended after implementation testing; CI jobs are definitions until they actually run.

- Unit/regression tests: lossless values, date boundaries, source restrictions, fetching completeness, HTTP failures, plan snapshots/upserts/recovery, export format/path behavior, credential isolation.
- MCP integration: registration, resources/prompts, structured preview input, actual tool calls, sanitized errors, no deletion tools.
- Package: locked install, manifest schema validation, portable-path and credential scan, source ZIP integrity.
- Windows: locked executable stdio handshake using the portable configuration; actual account only read/preview.
- macOS/Linux: CI installation and tests. Local Windows results do not stand in for those runs.

## Local acceptance, 2026-10-10

- Windows, Python 3.13.2: locked independent installation, Ruff and Pyright passed.
- Regression and integration suite: **70 passed** (28.39 seconds), covering data, HTTP errors, plan writes via mocked API, exports, configuration and MCP startup.
- Portable `mcp.json` launched via its actual uv command: 68 tools, 5 resources, 9 prompts; zero deletion tools, even when the parent environment requested full deletion.
- Official Agent Plugins schemas validated plugin.json and mcp.json; distributable-file scan passed.
- Python wheel and source distribution built; plugin/source ZIP generated with SHA-256.
- Isolated Codex home: marketplace registration and install returned installed=true, enabled=true, version=1.1.0. The installed cache copy independently installed its locked dependencies and launched via mcp.json, again exposing 68 tools, 5 resources and 9 prompts. No user's live configuration/cache was modified.
- Live secure-store credentials: account/profile, seven-day activity/wellness reads, and local NOTE preview succeeded. Zero remote writes and zero remote deletions. Private records and preview files are excluded from releases.
- Four skill entrypoints passed skill-creator validation (UTF-8 enabled for Windows).
- Three-platform GitHub Actions matrix is supplied. macOS/Linux CI has **not** run in this local session; actual-account write and device-sync validation are **not** claimed. Public repository/marketplace publication is pending publisher and destination selection.

