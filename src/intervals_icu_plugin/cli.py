"""Public local CLI; stdout belongs exclusively to MCP when serving."""

import argparse
import asyncio
import importlib.metadata
import json
import sys
from getpass import getpass

from .api import API
from .config import SERVICE, Config, load_config, secure_backend
from .formatting import error


async def doctor(config: Config):
    result = {
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("intervals-icu-plugin", "intervals-icu-mcp", "fastmcp", "httpx", "keyring")
        },
        "credential_source": config.source,
        "deletion": "disabled",
        "data_directory": str(config.data_dir),
    }
    async with API(config) as api:
        _, meta = await api.clock()
        result.update(connection="ok", **meta)
    return result


async def setup():
    print("Get your personal API key from https://intervals.icu/settings (Developer Settings).")
    config = Config(
        getpass("API key (hidden): ").strip(), input("Athlete ID [0=self]: ").strip() or "0"
    )
    async with API(config) as api:
        athlete = str((await api.athlete())["id"])
    backend = secure_backend()
    original = {k: backend.get_password(SERVICE, k) for k in ("api-key", "athlete-id")}
    try:
        backend.set_password(SERVICE, "api-key", config.api_key)
        backend.set_password(SERVICE, "athlete-id", athlete)
    except Exception:
        for key, value in original.items():
            try:
                if value is None:
                    backend.delete_password(SERVICE, key)
                else:
                    backend.set_password(SERVICE, key, value)
            except Exception:
                pass
        raise RuntimeError(
            "Secure credential write failed; previous values restored where possible. Use environment variables."
        ) from None
    print("Verified and saved to the OS secure store. No plaintext file was created.")


def main():
    parser = argparse.ArgumentParser(prog="intervals-icu-plugin")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run stdio MCP service")
    sub.add_parser("setup", help="Verify and save credentials interactively")
    sub.add_parser("doctor", help="Read-only diagnostics, without secrets")
    credentials = sub.add_parser("credentials").add_subparsers(
        dest="credentials_command", required=True
    )
    credentials.add_parser("clear", help="Remove only this plugin's locally saved credentials")
    args = parser.parse_args()
    try:
        if args.command == "setup":
            asyncio.run(setup())
        elif args.command == "credentials":
            backend = secure_backend()
            for key in ("api-key", "athlete-id"):
                if backend.get_password(SERVICE, key) is not None:
                    backend.delete_password(SERVICE, key)
            print(
                "Local credentials cleared. Environment values and the remote API key are unchanged."
            )
        elif args.command == "doctor":
            print(json.dumps(asyncio.run(doctor(load_config())), indent=2))
        else:
            from .server import create_server

            server = create_server(load_config())
            server.run(transport="stdio", show_banner=False)
    except Exception as exc:
        print(json.dumps(error(exc)), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
