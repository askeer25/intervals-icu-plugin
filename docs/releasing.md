# Release procedure

1. Run locked installation, tests, ruff and pyright. Review three-platform CI before claiming all platforms passed. Perform Windows installation/stdio verification. Live verification is read-only by default; write tests use mocked API or a separately configured disposable test account.
2. Run `uv run --locked python scripts/build_release.py`. Inspect the resulting ZIP, SHA-256 and `dist/release-validation.json`. The same source distribution contains portable plugin manifests, skills, code, lock and docs.
3. Repository and maintainer metadata point to [askeer25/intervals-icu-plugin](https://github.com/askeer25/intervals-icu-plugin). Retain upstream attribution in NOTICE; upstream is not this plugin's repository.
4. After validation, tag the intended commit and create a GitHub release. Attach the ZIP, checksum, wheel and sdist with notes describing compatibility changes and known limits. A GitHub release is separate from submission to a public plugin directory or package registry.
5. Users register the repo marketplace or extracted local directory and install intervals-icu@intervals-icu-community. Validate in a clean host/session. Existing local plugin IDs are not rewritten automatically; disable the old installation manually to avoid duplicate tool names.

Dependencies are locked and the upstream runtime version is fixed. An upstream upgrade must update the lock, audit and compatibility tests together. Source releases remain reproducible from their lock; the Python wheel contains the runtime only, while the ZIP contains marketplace/skills/plugin packaging.

