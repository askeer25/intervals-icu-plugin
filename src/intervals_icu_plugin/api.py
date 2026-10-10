"""Small raw-field client for wrapper-owned workflows, not a copy of the upstream API."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .config import Config


class APIError(Exception):
    def __init__(
        self,
        kind: str,
        message: str,
        status: int | None = None,
        uncertain: bool = False,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.kind, self.status, self.uncertain, self.retry_after = (
            kind,
            status,
            uncertain,
            retry_after,
        )


def parse_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise ValueError("Dates must use YYYY-MM-DD.") from None


def date_range(oldest: str, newest: str) -> tuple[date, date]:
    start, end = parse_date(oldest), parse_date(newest)
    if start > end or (end - start).days >= 366:
        raise ValueError("Date range must be ordered and contain at most 366 days.")
    return start, end


def retry_seconds(value: str | None) -> float:
    try:
        return max(0.0, float(value or "0"))
    except ValueError:
        try:
            return max(
                0.0, (parsedate_to_datetime(value or "") - datetime.now(UTC)).total_seconds()
            )
        except (ValueError, TypeError):
            return 1.0


class API:
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url="https://intervals.icu/api/v1",
            auth=("API_KEY", config.api_key),
            timeout=30,
            follow_redirects=False,
        )
        self.profile: dict[str, Any] | None = None
        self.requests = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if method == "DELETE":
            raise APIError("permission", "Deletion is disabled by this plugin.")
        for attempt in range(3):
            self.requests += 1
            try:
                response = await self.client.request(method, path, **kwargs)
            except httpx.RequestError:
                if method == "GET" and attempt < 2:
                    await asyncio.sleep(0.5 * 2**attempt)
                    continue
                raise APIError(
                    "network",
                    "Request failed; no credentials or response body are included.",
                    uncertain=method != "GET",
                ) from None
            status = response.status_code
            if status < 400 and not response.is_redirect:
                return response
            wait = (
                retry_seconds(response.headers.get("Retry-After"))
                if status == 429
                else 0.5 * 2**attempt
            )
            if method == "GET" and (status == 429 or status >= 500) and attempt < 2 and wait <= 10:
                await asyncio.sleep(wait)
                continue
            kind = {
                401: "authentication",
                403: "permission",
                404: "not_found",
                429: "rate_limit",
            }.get(status, "server" if status >= 500 else "validation")
            raise APIError(
                kind,
                f"Intervals.icu returned HTTP {status}.",
                status,
                method != "GET" and status >= 500,
                wait if status == 429 else None,
            )
        raise AssertionError("Unreachable retry state")

    async def json(self, method: str, path: str, **kwargs):
        response = await self.request(method, path, **kwargs)
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            raise APIError(
                "invalid_response",
                "API returned an invalid JSON response.",
                uncertain=method != "GET",
            ) from None

    async def athlete(self) -> dict:
        if self.profile is None:
            self.profile = await self.json("GET", f"/athlete/{self.config.athlete_id}")
        if not isinstance(self.profile, dict) or "id" not in self.profile:
            raise APIError("invalid_response", "Expected an athlete profile with ID.")
        return self.profile

    async def clock(self):
        profile = await self.athlete()
        name = self.config.timezone or profile.get("timezone")
        source = "configuration" if self.config.timezone else "athlete"
        if name:
            try:
                zone = ZoneInfo(name)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError(
                    "Configured/athlete timezone is not a valid IANA timezone."
                ) from None
            now = datetime.now(zone)
        else:
            now = datetime.now().astimezone()
            name, source = str(now.tzinfo), "system_fallback"
        return now.date(), {
            "timezone": name,
            "timezone_source": source,
            "athlete_id": str(profile["id"]),
        }

    async def activities(self, oldest: str, newest: str, max_items: int = 5000, budget: int = 40):
        """Split saturated windows; never infer completeness from a capped response."""
        start, end = date_range(oldest, newest)
        windows = []
        cursor = start
        while cursor <= end:
            right = min(cursor + timedelta(days=30), end)
            windows.append((cursor, right))
            cursor = right + timedelta(days=1)
        found: dict[str, dict] = {}
        calls = 0
        reasons: list[str] = []
        while windows:
            if calls >= budget or len(found) >= max_items:
                reasons.append("request_budget" if calls >= budget else "capacity")
                break
            left, right = windows.pop(0)
            rows = await self.json(
                "GET",
                f"/athlete/{self.config.athlete_id}/activities",
                params={"oldest": left.isoformat(), "newest": right.isoformat(), "limit": 500},
            )
            calls += 1
            if not isinstance(rows, list):
                raise APIError("invalid_response", "Expected an activity list.")
            for row in rows:
                if not isinstance(row, dict) or "id" not in row:
                    raise APIError("invalid_response", "Activity has no ID.")
                found[str(row["id"])] = row
            if len(rows) >= 500:
                if left == right:
                    reasons.append("saturated_day")
                else:
                    midpoint = left + (right - left) // 2
                    windows[:0] = [(left, midpoint), (midpoint + timedelta(days=1), right)]
        rows = sorted(
            found.values(),
            key=lambda r: (r.get("start_date_local", ""), str(r["id"])),
            reverse=True,
        )
        if len(rows) > max_items:
            reasons.append("capacity")
        return rows[:max_items], {
            "complete": not reasons,
            "incomplete_reasons": sorted(set(reasons)),
            "requests": calls,
        }

    async def events(self, oldest: str, newest: str):
        date_range(oldest, newest)
        return await self.json(
            "GET",
            f"/athlete/{self.config.athlete_id}/events",
            params={"oldest": oldest, "newest": newest},
        )
