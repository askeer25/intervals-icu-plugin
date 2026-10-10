import httpx
import pytest
import respx

from intervals_icu_plugin import analysis
from intervals_icu_plugin.api import API, APIError, date_range, parse_date, retry_seconds
from intervals_icu_plugin.formatting import activity, error, wellness

BASE = "https://intervals.icu/api/v1"


def test_zero_false_and_intensity_units():
    row = activity(
        {
            "id": "a",
            "start_date_local": "2026-10-10T00:00:00",
            "moving_time": 0,
            "icu_training_load": 0,
            "indoor": False,
            "commute": False,
            "icu_intensity": 85,
            "icu_weighted_avg_watts": 210,
        },
        True,
    )
    assert row["moving_time_seconds"] == row["training_load"] == 0
    assert row["other"]["indoor"] is False and row["commute"] is False
    assert row["power"]["normalized"] == row["normalized_power"] == 210
    assert row["intensity_percent"] == row["intensity_factor"] == 85
    assert row["intensity_factor_ratio"] == 0.85
    assert "pace_seconds_per_km" not in row


def test_wellness_zero_raw_custom_and_derived_tsb():
    row = wellness(
        {
            "id": "2026-10-10",
            "ctl": 0,
            "atl": 0,
            "steps": 0,
            "sleepScore": 0,
            "locked": False,
            "custom": 0,
        }
    )
    assert row["training"] == {"ctl": 0, "atl": 0, "tsb": 0}
    assert row["activity"]["steps"] == row["sleep"]["score"] == 0
    assert row["state_flags"]["locked"] is False
    assert row["raw_fields"]["custom"] == 0


def test_source_restrictions_not_inferred_from_brand():
    assert activity({"id": "a", "source": "STRAVA"})["availability"]["status"] == "restricted"
    assert (
        activity({"id": "a", "source": "STRAVA", "moving_time": 0})["availability"]["status"]
        != "restricted"
    )
    assert (
        activity({"id": "a", "source": "GARMIN_CONNECT", "device_name": "Garmin"})["availability"][
            "status"
        ]
        != "restricted"
    )


@pytest.mark.parametrize("value", ["2026-13-01", "20261010", "2026-1-1", "2026-10-10T00:00:00"])
def test_invalid_dates(value):
    with pytest.raises(ValueError):
        parse_date(value)


def test_date_range_limit():
    date_range("2026-01-01", "2026-12-31")
    with pytest.raises(ValueError):
        date_range("2026-01-01", "2027-01-02")
    with pytest.raises(ValueError):
        date_range("2026-10-10", "2026-10-09")


@respx.mock
async def test_clock_athlete_timezone_and_override(config):
    respx.get(f"{BASE}/athlete/0").respond(json={"id": "i1", "timezone": "Asia/Shanghai"})
    async with API(config) as api:
        _, meta = await api.clock()
        assert meta["timezone"] == "Asia/Shanghai" and meta["timezone_source"] == "athlete"
    config.timezone = "Pacific/Honolulu"
    async with API(config) as api:
        _, meta = await api.clock()
        assert meta["timezone_source"] == "configuration"


@respx.mock
async def test_system_timezone_fallback(config):
    respx.get(f"{BASE}/athlete/0").respond(json={"id": "i1"})
    async with API(config) as api:
        _, meta = await api.clock()
        assert meta["timezone_source"] == "system_fallback"


@respx.mock
async def test_local_calendar_date_crosses_utc_midnight(config, monkeypatch):
    from datetime import UTC, datetime

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 10, 10, 23, 30, tzinfo=UTC)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr("intervals_icu_plugin.api.datetime", FrozenDateTime)
    respx.get(f"{BASE}/athlete/0").respond(json={"id": "i1", "timezone": "Asia/Shanghai"})
    async with API(config) as api:
        today, _ = await api.clock()
        assert today.isoformat() == "2026-10-11"
    config.timezone = "America/Los_Angeles"
    async with API(config) as api:
        today, _ = await api.clock()
        assert today.isoformat() == "2026-10-10"


@respx.mock
async def test_capacity_marks_partial_and_preserves_limit(config):
    respx.get(f"{BASE}/athlete/0/activities").respond(json=[{"id": str(i)} for i in range(3)])
    async with API(config) as api:
        rows, meta = await api.activities("2026-10-01", "2026-10-01", max_items=2)
    assert len(rows) == 2 and not meta["complete"] and "capacity" in meta["incomplete_reasons"]


@respx.mock
async def test_saturated_windows_split_and_deduplicate(config):
    def handler(request):
        left, right = request.url.params["oldest"], request.url.params["newest"]
        size = 500 if left != right else 250
        return httpx.Response(
            200, json=[{"id": str(i), "start_date_local": left + "T10:00:00"} for i in range(size)]
        )

    route = respx.get(f"{BASE}/athlete/0/activities").mock(side_effect=handler)
    async with API(config) as api:
        rows, meta = await api.activities("2026-10-01", "2026-10-02")
    assert len(rows) == 500 and route.call_count == 3 and meta["complete"]


@respx.mock
async def test_single_saturated_day_incomplete(config):
    respx.get(f"{BASE}/athlete/0/activities").respond(json=[{"id": str(i)} for i in range(500)])
    async with API(config) as api:
        _, meta = await api.activities("2026-10-01", "2026-10-01")
    assert not meta["complete"] and "saturated_day" in meta["incomplete_reasons"]


@respx.mock
async def test_request_budget(config):
    respx.get(f"{BASE}/athlete/0/activities").respond(json=[])
    async with API(config) as api:
        _, meta = await api.activities("2026-01-01", "2026-04-01", budget=1)
    assert meta["incomplete_reasons"] == ["request_budget"]


@pytest.mark.parametrize(
    "status,kind",
    [
        (401, "authentication"),
        (403, "permission"),
        (404, "not_found"),
        (429, "rate_limit"),
        (500, "server"),
    ],
)
@respx.mock
async def test_http_classification_no_body_leak(config, status, kind, monkeypatch):
    async def no_sleep(*_):
        pass

    monkeypatch.setattr("intervals_icu_plugin.api.asyncio.sleep", no_sleep)
    respx.get(f"{BASE}/athlete/0").respond(
        status, text="private-server-body", headers={"Retry-After": "370"}
    )
    async with API(config) as api:
        with pytest.raises(APIError) as caught:
            await api.athlete()
    assert caught.value.kind == kind and "private-server-body" not in str(caught.value)
    if status == 429:
        assert caught.value.retry_after == 370


@respx.mock
async def test_read_retry_respects_delay(config, monkeypatch):
    waits = []

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr("intervals_icu_plugin.api.asyncio.sleep", sleep)
    route = respx.get(f"{BASE}/athlete/0").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json={"id": "i1"}),
        ]
    )
    async with API(config) as api:
        assert (await api.athlete())["id"] == "i1"
    assert waits == [2] and route.call_count == 2


@respx.mock
async def test_write_not_blindly_retried(config):
    route = respx.post(f"{BASE}/athlete/0/events").mock(side_effect=httpx.ReadTimeout("timeout"))
    async with API(config) as api:
        with pytest.raises(APIError) as caught:
            await api.json("POST", "/athlete/0/events", json={})
    assert route.call_count == 1 and caught.value.uncertain


async def test_delete_transport_blocked(config):
    async with API(config) as api:
        with pytest.raises(APIError):
            await api.request("DELETE", "/any")


def test_training_missing_values_and_grouping():
    result = analysis.training_summary(
        [
            {
                "id": "a",
                "start_date_local": "2026-10-05T10:00:00",
                "distance": 0,
                "moving_time": 0,
                "indoor": False,
            },
            {"id": "b", "start_date_local": "2026-10-06T10:00:00", "source": "STRAVA"},
        ],
        None,
        "all",
        "week",
    )
    assert result["totals"]["metrics"]["distance_meters"] == {
        "sum": 0,
        "valid_samples": 1,
        "missing_samples": 1,
    }
    assert result["totals"]["restricted_count"] == 1
    assert result["groups"][0]["period_start"] == "2026-10-05"


def test_recovery_samples():
    result = analysis.recovery(
        [{"id": "2026-10-01", "hrv": 0}, {"id": "2026-10-03", "hrv": 10}], 28
    )
    assert result["metrics"]["hrv"]["mean"] == 5
    assert result["metrics"]["hrv"]["missing_days"] == 26
    assert result["metrics"]["readiness"]["latest"] is None


def test_adherence_no_guessed_pairing():
    events = [
        {"id": 1, "category": "WORKOUT", "moving_time": 100},
        {"id": 2, "category": "WORKOUT"},
    ]
    result = analysis.adherence(
        events,
        [{"id": "a", "paired_event_id": 1, "moving_time": 50}, {"id": "b", "moving_time": 100}],
    )
    assert result["paired_count"] == result["unconfirmed_count"] == 1
    assert result["workouts"][0]["ratios"]["moving_time"] == 0.5
    assert result["workouts"][1]["status"] == "unconfirmed"


def test_internal_error_sanitized():
    assert "sensitive-body" not in str(error(RuntimeError("sensitive-body")))
    assert retry_seconds("10") == 10


def test_custom_raw_intensity_is_not_rewritten():
    from intervals_icu_plugin.server import _normalize_intensities

    payload = {"data": {"intensity_factor": 85, "raw_fields": {"intensity_factor": 0.85}}}
    _normalize_intensities(payload)
    assert payload["data"]["intensity_factor_ratio"] == 0.85
    assert payload["data"]["raw_fields"] == {"intensity_factor": 0.85}
