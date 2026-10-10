# Contributing

Bug reports, clearer documentation, focused adapters and regression tests are welcome.

## Development setup

```bash
git clone https://github.com/askeer25/intervals-icu-plugin.git
cd intervals-icu-plugin
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked pyright
```

The runtime is a thin wrapper around a pinned upstream package. Keep changes in `src/intervals_icu_plugin`; avoid vendoring or modifying installed upstream code. Document upstream limitations when the wrapper cannot repair them.

## Before opening a pull request

- Describe the observable problem and resulting behavior.
- Add a meaningful regression test for changed data, request or write semantics. Use mocked API responses rather than personal records.
- Keep tool descriptions, capability documentation and compatibility notes consistent with implementation.
- Run the checks above. For packaging changes, also run `uv run --locked python scripts/build_release.py`.
- Exclude API keys, local previews, activity files, health/location data and machine-specific paths.

Test live writes only with a separately configured disposable test account. Personal accounts are used for read-only verification by default. The test suite does not automatically publish or delete remote records.

## Report an issue

Include the plugin version, OS, client, relevant tool name, reproducible steps and expected versus actual behavior. Redact identifiers and private content. For a credential or privacy issue, follow [SECURITY.md](SECURITY.md).
