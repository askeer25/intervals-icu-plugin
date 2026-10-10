"""Validate host installation in an isolated Codex home, never the user's live config."""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path

from smoke_stdio import smoke


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    test_root = root / ".cache" / f"host-install-{uuid.uuid4().hex}"
    source = test_root / "source"
    source.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            if not (source / name).resolve().is_relative_to(source.resolve()):
                raise ValueError("Archive path traversal")
        archive.extractall(source)
    project = source / "intervals-icu-plugin"
    # Scoped only to the child processes: no change to the user's app configuration.
    env = {**os.environ, "CODEX_HOME": str(test_root / "codex-home")}
    Path(env["CODEX_HOME"]).mkdir()
    binary = shutil.which("codex")
    if binary is None:
        raise SystemExit("Codex CLI is not installed; host installation check unavailable.")
    outputs = []
    for command in (
        [binary, "plugin", "marketplace", "add", str(project)],
        [binary, "plugin", "add", "intervals-icu@intervals-icu-community", "--json"],
        [binary, "plugin", "list", "--marketplace", "intervals-icu-community", "--json"],
    ):
        completed = subprocess.run(
            command,
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            check=True,
            shell=os.name == "nt",
        )
        outputs.append(completed.stdout)
    listing = json.loads(outputs[-1])
    installed = listing["installed"]
    assert len(installed) == 1 and installed[0]["installed"] and installed[0]["enabled"]
    assert installed[0]["version"] == "1.1.0"
    cached_plugin = (
        Path(env["CODEX_HOME"])
        / "plugins"
        / "cache"
        / "intervals-icu-community"
        / "intervals-icu"
        / installed[0]["version"]
    )
    asyncio.run(smoke(cached_plugin))
    (test_root / "listing.json").write_text(json.dumps(listing, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "host_install": "passed",
                "version": installed[0]["version"],
                "enabled": True,
                "isolated_home": True,
                "live_config_changed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
