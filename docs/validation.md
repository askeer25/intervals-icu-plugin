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
- At initial local acceptance, macOS/Linux CI had not yet run. Actual-account write and device-sync validation remain unverified; mocked tests and CI do not establish those behaviors.

## GitHub acceptance, 2026-10-10

The public repository is [askeer25/intervals-icu-plugin](https://github.com/askeer25/intervals-icu-plugin). Source revision `54d8e0f6f1e9f773746a115bdecf6d03a42ffa64` passed [CI run 38037633117](https://github.com/askeer25/intervals-icu-plugin/actions/runs/38037633117):

- Windows, macOS and Ubuntu, each on Python 3.11 and 3.13: all six jobs passed locked installation, Ruff, Pyright, 70 tests and distribution builds.
- The package job passed manifest validation and distributable-file scanning and produced the release ZIP artifact.
- GitHub README rendering and relative documentation links were checked. Private data, credentials and local preview files were excluded from the uploaded file set.

A GitHub source/release publication does not imply listing in an external plugin directory or publication to PyPI.

