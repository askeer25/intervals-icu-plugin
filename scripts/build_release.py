"""Build a reviewable source/plugin ZIP from an explicit allowlist."""

import hashlib
import json
import re
import zipfile
from pathlib import Path

import httpx
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "plugin.json",
    "mcp.json",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "NOTICE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".gitignore",
    ".agents/plugins/marketplace.json",
]
DIRECTORIES = ["src", "skills", "docs", "tests", "scripts", ".github"]


def distributable_files(root=ROOT):
    paths = [root / name for name in FILES]
    paths += [
        p
        for d in DIRECTORIES
        for p in (root / d).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def scan(paths, root=ROOT):
    errors = []
    for path in paths:
        if not path.is_file():
            errors.append(f"Missing required release file: {path.name}")
            continue
        name = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8")
        if re.search(
            r"(?:[A-Za-z]:[\\/](?:Users|博士)[\\/]|/(?:Users|home)/[A-Za-z0-9_.-]+/)", content
        ):
            errors.append(f"Personal absolute path: {name}")
        if re.search(
            r'(?i)(?:INTERVALS_ICU_API_KEY\s*=\s*["\']?[^\s"\']{12,}|"api[_-]?key"\s*:\s*"[^"\s]{12,}")',
            content,
        ):
            errors.append(f"Possible literal credential: {name}")
        if ".env" == path.name or "previews" in path.parts:
            errors.append(f"Private local data: {name}")
    return errors


def validate_manifests():
    # Fetch official schema documents, resolving references via the same public schema host.
    results = {}
    for name in ("plugin.json", "mcp.json"):
        document = json.loads((ROOT / name).read_text())
        schema = httpx.get(document["$schema"], timeout=30, follow_redirects=True)
        schema.raise_for_status()
        jsonschema.validate(document, schema.json())
        results[name] = "schema_valid"
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert marketplace["plugins"][0]["source"]["path"] == "./"
    return results


def main():
    paths = distributable_files()
    errors = scan(paths)
    if errors:
        raise SystemExit("\n".join(errors))
    validations = validate_manifests()
    version = json.loads((ROOT / "plugin.json").read_text())["version"]
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / f"intervals-icu-plugin-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            info = zipfile.ZipInfo(
                f"intervals-icu-plugin/{path.relative_to(ROOT).as_posix()}", (2026, 10, 10, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    report = {
        "version": version,
        "files": len(paths),
        "manifest_validation": validations,
        "scan": "passed",
        "sha256": digest,
        "published": False,
    }
    (output / "release-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
