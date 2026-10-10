"""Compose the pinned upstream service with local adapters and workflow tools."""

import json
from typing import Any, cast

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from mcp.types import TextContent

from . import tools
from .config import Config, prepare_upstream
from .formatting import metadata


class PluginMiddleware(Middleware):
    def __init__(self, config: Config):
        self.config = config

    async def on_call_tool(self, context, call_next):
        if "delete" in context.message.name.lower():
            raise ToolError("Deletion is disabled by this plugin.")
        if context.fastmcp_context:
            await context.fastmcp_context.set_state(
                "plugin_config", self.config, serializable=False
            )
        result = await call_next(context)
        for block in result.content:
            if isinstance(block, TextContent):
                try:
                    payload = json.loads(block.text)
                except (ValueError, TypeError):
                    block.text = block.text.replace(self.config.api_key, "[redacted]")
                    continue
                if not isinstance(payload, dict):
                    continue
                if "error" in payload and payload["error"].get("type") in {
                    "api_error",
                    "internal_error",
                }:
                    payload["error"]["message"] = (
                        "Upstream tool failed. Run doctor to check connection; upstream details omitted for privacy."
                    )
                payload.setdefault("metadata", {}).update(
                    {
                        k: v
                        for k, v in metadata(tool=context.message.name).items()
                        if k not in payload.get("metadata", {})
                    }
                )
                _normalize_intensities(payload)
                block.text = json.dumps(payload, ensure_ascii=False, default=str).replace(
                    self.config.api_key, "[redacted]"
                )
                if result.structured_content is not None:
                    # Upstream string-return tools use FastMCP's {result: string} envelope.
                    result.structured_content = {"result": block.text}
        return result


def _normalize_intensities(value):
    if isinstance(value, dict):
        old = value.get("intensity_factor")
        if isinstance(old, (int, float)):
            value.setdefault("intensity_percent", old)
            value.setdefault("intensity_factor_ratio", old / 100)
        for key, child in list(value.items()):
            if key != "raw_fields":
                _normalize_intensities(child)
    elif isinstance(value, list):
        for child in value:
            _normalize_intensities(child)


def create_server(config: Config):
    prepare_upstream(config)
    from intervals_icu_mcp.server import mcp

    replacements = {
        "icu_get_recent_activities": tools.get_recent_activities,
        "icu_get_activities_by_date": tools.get_activities_by_date,
        "icu_get_activity_details": tools.get_activity_details,
        "icu_get_wellness_data": tools.get_wellness_data,
        "icu_get_wellness_for_date": tools.get_wellness_for_date,
        "icu_download_activity_file": tools.download_activity_file,
        "icu_download_fit_file": tools.download_fit_file,
        "icu_download_gpx_file": tools.download_gpx_file,
    }
    additions = {
        "icu_get_training_summary": tools.get_training_summary,
        "icu_compare_activities": tools.compare_activities,
        "icu_get_recovery_summary": tools.get_recovery_summary,
        "icu_get_plan_adherence": tools.get_plan_adherence,
        "icu_preview_training_plan": tools.preview_training_plan,
        "icu_commit_training_plan": tools.commit_training_plan,
        "icu_export_workout": tools.export_workout_tool,
    }
    # The imported upstream service is process-global. Construct only once per process.
    if getattr(mcp, "_portable_plugin_configured", False):
        raise RuntimeError("Plugin server already constructed in this process.")
    cast(Any, mcp)._portable_plugin_configured = True
    mcp.add_middleware(PluginMiddleware(config))
    for name in (
        "icu_delete_activity",
        "icu_delete_event",
        "icu_bulk_delete_events",
        "icu_delete_workout",
        "icu_delete_gear",
        "icu_delete_sport_settings",
        "icu_delete_custom_item",
    ):
        try:
            mcp.local_provider.remove_tool(name)
        except KeyError:
            pass  # DELETE_MODE=none means these tools were never registered.
    for name, function in {**replacements, **additions}.items():
        if name in replacements:
            mcp.local_provider.remove_tool(name)
        local_writes = {
            "icu_preview_training_plan",
            "icu_export_workout",
            "icu_download_activity_file",
            "icu_download_fit_file",
            "icu_download_gpx_file",
        }
        mcp.tool(
            name=name,
            annotations={
                "readOnlyHint": name != "icu_commit_training_plan" and name not in local_writes,
                "destructiveHint": name == "icu_commit_training_plan",
                "idempotentHint": name not in local_writes,
                "openWorldHint": True,
            },
        )(function)

    # FastMCP replaces a local prompt with the same name (no remove_prompt API).
    @mcp.prompt(name="verify_setup")
    def verify_setup() -> str:
        return "Verify with read-only calls: icu_get_athlete_profile, icu_get_recent_activities(limit=1), icu_get_wellness_data(days_back=1), and icu_get_calendar_events. Report permission and source limitations. Do not create, modify, or delete records for verification."

    @mcp.prompt(name="verify_multi_athlete")
    def verify_multi_athlete(athlete_id: str = "") -> str:
        return f"Read-only verification of athlete {athlete_id}: icu_get_athlete_profile and icu_get_wellness_data with the explicit athlete_id. Check permission errors and returned identity. Never create, modify, or delete verification records."

    @mcp.resource("intervals-icu://plugin-capabilities")
    def capabilities() -> str:
        return json.dumps(
            {
                "plugin_version": "1.1.0",
                "upstream_version": "5.4.0",
                "deletion": "disabled",
                "workflow_tools": list(additions),
                "summary_max_days": 366,
                "preview_valid_hours": 24,
                "legacy_limitations": "Unreplaced upstream tools retain upstream date/formatting/HTTP behavior. Use wrapper workflows for complete totals and explicit units.",
                "source_restrictions": "Website visibility does not guarantee API availability. Strava restricted; Garmin subject to policy changes.",
                "auth": "Local personal-account API key; not a shared multi-user service.",
            }
        )

    return mcp
