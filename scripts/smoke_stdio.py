"""Exercise exactly the portable MCP launch definition without real account data."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def smoke(root: Path):
    definition = json.loads((root / "mcp.json").read_text())["mcpServers"]["intervals_icu"]
    args = [value.replace("${PLUGIN_ROOT}", str(root)) for value in definition["args"]]
    env = {
        **os.environ,
        "INTERVALS_ICU_API_KEY": "unit-key",
        "INTERVALS_ICU_ATHLETE_ID": "0",
        "INTERVALS_ICU_DELETE_MODE": "full",
    }
    async with Client(StdioTransport(command=definition["command"], args=args, env=env)) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        assert len(tools) == 68 and not any("delete" in t.name for t in tools)
        assert len(resources) == 5 and len(prompts) == 9
        print(
            json.dumps(
                {
                    "portable_stdio": "passed",
                    "tools": len(tools),
                    "resources": len(resources),
                    "prompts": len(prompts),
                    "delete_tools": 0,
                }
            )
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    asyncio.run(smoke(parser.parse_args().root.resolve()))


if __name__ == "__main__":
    main()
