"""Public tools; retain legacy parameter names on replaced upstream reads."""

import functools
import inspect
import json
from dataclasses import replace
from datetime import timedelta
from typing import Any, Literal, cast

from fastmcp import Context

from . import analysis
from .api import API, parse_date
from .exporting import export_workout, save_export
from .formatting import activity, error, response, wellness
from .planning import PlanEvent, commit, preview


def guarded(func):
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            result = error(exc)
        return json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))

    cast(Any, wrapped).__signature__ = inspect.signature(func).replace(return_annotation=str)
    return wrapped


async def get_api(ctx: Context | None, athlete_id: str | None = None) -> API:
    if ctx is None:
        raise ValueError("MCP context is required.")
    config = await ctx.get_state("plugin_config")
    return API(replace(config, athlete_id=athlete_id) if athlete_id else config)


@guarded
async def get_recent_activities(
    limit: int = 30, days_back: int = 30, athlete_id: str | None = None, ctx: Context | None = None
) -> dict:
    """Recent activities in athlete-local dates, preserving zeros and reporting truncation."""
    if not 1 <= limit <= 100 or not 1 <= days_back <= 366:
        raise ValueError("limit must be 1–100 and days_back 1–366.")
    async with await get_api(ctx, athlete_id) as api:
        today, meta = await api.clock()
        oldest = (today - timedelta(days=days_back - 1)).isoformat()
        rows, coverage = await api.activities(oldest, today.isoformat())
        if len(rows) > limit:
            coverage.update(
                complete=False,
                incomplete_reasons=[*coverage["incomplete_reasons"], "requested_limit"],
            )
        return response(
            {"activities": [activity(r) for r in rows[:limit]], "count": min(len(rows), limit)},
            query_range={"oldest": oldest, "newest": today.isoformat()},
            **meta,
            **coverage,
        )


@guarded
async def get_activities_by_date(
    oldest: str,
    newest: str | None = None,
    limit: int = 500,
    athlete_id: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Date-window activities (up to one year); capped output explicitly reports incompleteness."""
    if not 1 <= limit <= 5000:
        raise ValueError("limit must be 1–5000.")
    async with await get_api(ctx, athlete_id) as api:
        today, meta = await api.clock()
        newest = newest or today.isoformat()
        rows, coverage = await api.activities(oldest, newest)
        if len(rows) > limit:
            coverage.update(
                complete=False,
                incomplete_reasons=[*coverage["incomplete_reasons"], "requested_limit"],
            )
        return response(
            {"activities": [activity(r) for r in rows[:limit]], "count": min(len(rows), limit)},
            query_range={"oldest": oldest, "newest": newest},
            **meta,
            **coverage,
        )


@guarded
async def get_activity_details(activity_id: str, ctx: Context | None = None) -> dict:
    """Activity details from raw API fields, including zero/false, source availability, and units."""
    async with await get_api(ctx) as api:
        _, meta = await api.clock()
        row = await api.json("GET", f"/activity/{activity_id}")
        return response(activity(row, details=True), **meta)


@guarded
async def get_wellness_data(
    days_back: int = 7, athlete_id: str | None = None, ctx: Context | None = None
) -> dict:
    """Athlete-local recent wellness records; missing and zero values remain distinct."""
    if not 1 <= days_back <= 366:
        raise ValueError("days_back must be 1–366.")
    async with await get_api(ctx, athlete_id) as api:
        today, meta = await api.clock()
        oldest = (today - timedelta(days=days_back - 1)).isoformat()
        rows = await api.json(
            "GET",
            f"/athlete/{api.config.athlete_id}/wellness",
            params={"oldest": oldest, "newest": today.isoformat()},
        )
        rows = sorted(rows, key=lambda r: r["id"], reverse=True)
        return response(
            {"wellness_data": [wellness(r) for r in rows], "count": len(rows)},
            query_range={"oldest": oldest, "newest": today.isoformat()},
            requested_days=days_back,
            covered_days=len(rows),
            complete=True,
            **meta,
        )


@guarded
async def get_wellness_for_date(
    date: str, athlete_id: str | None = None, ctx: Context | None = None
) -> dict:
    """Wellness for one local calendar date, including raw/custom fields."""
    parse_date(date)
    async with await get_api(ctx, athlete_id) as api:
        _, meta = await api.clock()
        row = await api.json("GET", f"/athlete/{api.config.athlete_id}/wellness/{date}")
        return response(wellness(row), query_range={"oldest": date, "newest": date}, **meta)


@guarded
async def get_training_summary(
    oldest: str,
    newest: str,
    sport_types: list[str] | None = None,
    environment: Literal["all", "indoor", "outdoor"] = "all",
    group_by: Literal["day", "week", "month"] = "week",
    athlete_id: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Period totals and daily/weekly/monthly groups from available fields, with coverage counts."""
    async with await get_api(ctx, athlete_id) as api:
        _, meta = await api.clock()
        rows, coverage = await api.activities(oldest, newest)
        data = analysis.training_summary(rows, sport_types, environment, group_by)
        data["totals_label"] = (
            "complete_observed_totals" if coverage["complete"] else "partial_observed_totals"
        )
        return response(
            data,
            query_range={"oldest": oldest, "newest": newest},
            filters={"sport_types": sport_types, "environment": environment},
            group_by=group_by,
            **coverage,
            **meta,
        )


@guarded
async def compare_activities(activity_ids: list[str], ctx: Context | None = None) -> dict:
    """Compare 2–10 unique activities; indoor/outdoor/unknown environments and missing metrics are explicit."""
    if not 2 <= len(activity_ids) <= 10 or len(set(activity_ids)) != len(activity_ids):
        raise ValueError("Provide 2–10 unique activity IDs.")
    async with await get_api(ctx) as api:
        _, meta = await api.clock()
        rows = [await api.json("GET", f"/activity/{identity}") for identity in activity_ids]
        entries = [activity(r) for r in rows]
        for entry, row in zip(entries, rows, strict=True):
            entry["environment"] = analysis.environment(row)
            entry["missing_metrics"] = [
                k
                for k in (
                    "distance_meters",
                    "moving_time_seconds",
                    "pace_seconds_per_km",
                    "average_heartrate",
                    "normalized_power",
                    "training_load",
                )
                if k not in entry
            ]
        return response(
            {
                "activities": entries,
                "comparable_environment": len({e["environment"] for e in entries}) == 1
                and entries[0]["environment"] != "unknown",
                "method": "Side-by-side observed metrics; no claim that pace changes alone show fitness changes.",
            },
            **meta,
        )


@guarded
async def get_recovery_summary(
    days: int = 28, athlete_id: str | None = None, ctx: Context | None = None
) -> dict:
    """Recovery observations and sample counts; no invented composite readiness score."""
    if not 1 <= days <= 366:
        raise ValueError("days must be 1–366.")
    async with await get_api(ctx, athlete_id) as api:
        today, meta = await api.clock()
        oldest, newest = (today - timedelta(days=days - 1)).isoformat(), today.isoformat()
        rows = await api.json(
            "GET",
            f"/athlete/{api.config.athlete_id}/wellness",
            params={"oldest": oldest, "newest": newest},
        )
        rows = [r for r in rows if oldest <= r["id"] <= newest]
        for row in rows:
            if row.get("tsb") is None and row.get("ctl") is not None and row.get("atl") is not None:
                row["tsb"] = row["ctl"] - row["atl"]
        return response(
            analysis.recovery(rows, days),
            query_range={"oldest": oldest, "newest": newest},
            attribution="Charts may include data from Garmin devices",
            **meta,
        )


@guarded
async def get_plan_adherence(
    oldest: str, newest: str, athlete_id: str | None = None, ctx: Context | None = None
) -> dict:
    """Plan-versus-actual using explicit event pairing; unpaired workouts remain unconfirmed."""
    async with await get_api(ctx, athlete_id) as api:
        _, meta = await api.clock()
        rows, coverage = await api.activities(oldest, newest)
        events = await api.events(oldest, newest)
        return response(
            analysis.adherence(events, rows),
            query_range={"oldest": oldest, "newest": newest},
            **coverage,
            **meta,
        )


@guarded
async def preview_training_plan(
    plan_id: str, events: list[PlanEvent], allow_conflicts: bool = False, ctx: Context | None = None
) -> dict:
    """Preview structured events with stable event_key per workout. Saves locally for 24 hours; does not write remotely. allow_conflicts must reflect user intent."""
    async with await get_api(ctx) as api:
        _, meta = await api.clock()
        return response(await preview(api, plan_id, events, allow_conflicts), **meta)


@guarded
async def commit_training_plan(preview_id: str, ctx: Context | None = None) -> dict:
    """Commit an authorized preview, check conflicts, upsert stable UIDs, and verify each result. No deletion or automatic rollback."""
    async with await get_api(ctx) as api:
        _, meta = await api.clock()
        return response(await commit(api, preview_id), **meta)


@guarded
async def export_workout_tool(
    format: Literal["fit", "zwo", "mrc", "erg"],
    event_id: int | None = None,
    workout_id: int | None = None,
    filename: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Export one planned or library workout into the local exports directory; never overwrite files."""
    async with await get_api(ctx) as api:
        return response(await export_workout(api, format, event_id, workout_id, filename))


async def _download(
    activity_id: str, output_path: str | None, endpoint: str, extension: str, ctx: Context | None
):
    async with await get_api(ctx) as api:
        file = await api.request("GET", f"/activity/{activity_id}/{endpoint}")
        return response(
            {
                "activity_id": activity_id,
                **save_export(
                    api.config.data_dir,
                    file.content,
                    f"activity-{activity_id}.{extension}",
                    output_path,
                ),
            }
        )


@guarded
async def download_activity_file(
    activity_id: str, output_path: str | None = None, ctx: Context | None = None
) -> dict:
    """Download original activity file locally. Default .bin preserves original bytes; output_path must be in the exports directory and unused."""
    return await _download(activity_id, output_path, "file", "bin", ctx)


@guarded
async def download_fit_file(
    activity_id: str, output_path: str | None = None, ctx: Context | None = None
) -> dict:
    """Download FIT locally without overwriting or embedding Base64. output_path must be inside exports."""
    return await _download(activity_id, output_path, "fit-file", "fit", ctx)


@guarded
async def download_gpx_file(
    activity_id: str, output_path: str | None = None, ctx: Context | None = None
) -> dict:
    """Download GPX locally without overwriting or embedding Base64. output_path must be inside exports."""
    return await _download(activity_id, output_path, "gpx-file", "gpx", ctx)
