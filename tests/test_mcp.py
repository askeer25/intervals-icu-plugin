import json
import os
import sys

import pytest
import respx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from intervals_icu_plugin.config import Config
from intervals_icu_plugin.server import create_server

BASE = "https://intervals.icu/api/v1"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    return create_server(Config("unit-key", "0", data_dir=tmp_path_factory.mktemp("mcp")))


async def test_tool_resource_prompt_registration(server):
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert len(names) == 68 and not any("delete" in n for n in names)
        assert len(await client.list_resources()) == 5
        assert len(await client.list_prompts()) == 9
        schema = next(t.inputSchema for t in tools if t.name == "icu_preview_training_plan")
        assert schema["properties"]["events"]["type"] == "array"
        prompt = await client.get_prompt("verify_setup")
        assert "Do not create" in str(prompt)


@respx.mock
async def test_real_mcp_call_adapted_activity(server):
    respx.get(f"{BASE}/athlete/0").respond(json={"id": "i1", "timezone": "UTC"})
    respx.get(f"{BASE}/activity/a").respond(
        json={
            "id": "a",
            "moving_time": 0,
            "icu_training_load": 0,
            "indoor": False,
            "icu_intensity": 85,
            "icu_weighted_avg_watts": 210,
        }
    )
    async with Client(server) as client:
        result = await client.call_tool("icu_get_activity_details", {"activity_id": "a"})
    payload = json.loads(result.content[0].text)
    assert payload["data"]["moving_time_seconds"] == 0
    assert payload["data"]["normalized_power"] == 210
    assert payload["data"]["intensity_factor_ratio"] == 0.85
    assert payload["metadata"]["timezone"] == "UTC"


@respx.mock
async def test_preview_call_structured_input_no_write(server):
    respx.get(f"{BASE}/athlete/0").respond(json={"id": "i1", "timezone": "UTC"})
    respx.get(f"{BASE}/athlete/0/events").respond(json=[])
    async with Client(server) as client:
        result = await client.call_tool(
            "icu_preview_training_plan",
            {
                "plan_id": "test-week",
                "events": [
                    {
                        "event_key": "a",
                        "start_date_local": "2026-11-02",
                        "name": "Note",
                        "category": "NOTE",
                    }
                ],
            },
        )
    payload = json.loads(result.content[0].text)
    assert payload["data"]["can_commit"] is True
    assert payload["data"]["items"][0]["action"] == "create"


@respx.mock
async def test_tool_error_no_key_leak(server):
    respx.get(f"{BASE}/athlete/0").respond(403, text="unit-key server body")
    async with Client(server) as client:
        result = await client.call_tool("icu_get_activity_details", {"activity_id": "a"})
    assert "unit-key" not in result.content[0].text
    assert json.loads(result.content[0].text)["error"]["type"] == "permission"


async def test_stdio_entrypoint_handshake():
    env = {
        **os.environ,
        "INTERVALS_ICU_API_KEY": "unit-key",
        "INTERVALS_ICU_ATHLETE_ID": "0",
        "INTERVALS_ICU_DELETE_MODE": "full",
    }
    transport = StdioTransport(
        command=sys.executable, args=["-m", "intervals_icu_plugin.cli", "serve"], env=env
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        assert len(tools) == 68 and not any("delete" in t.name for t in tools)
