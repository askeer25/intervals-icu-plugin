from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from intervals_icu_plugin.api import API
from intervals_icu_plugin.planning import PlanEvent, PreviewStore, commit, preview

BASE = "https://intervals.icu/api/v1"


@pytest.fixture
def calendar():
    with respx.mock(assert_all_called=False) as router:
        rows = []
        router.get(f"{BASE}/athlete/0").respond(json={"id": "i1", "timezone": "UTC"})
        router.get(f"{BASE}/athlete/0/events").mock(
            side_effect=lambda _: httpx.Response(200, json=deepcopy(rows))
        )

        def write(request):
            import json

            payload = json.loads(request.content)
            assert request.url.params["upsertOnUid"] == "true"
            row = next((r for r in rows if r["uid"] == payload["uid"]), None)
            if row is None:
                row = {"id": len(rows) + 1}
                rows.append(row)
            row.update(payload)
            if payload["category"] == "WORKOUT":
                row["workout_doc"] = {"steps": [{"duration": 600}]}
            return httpx.Response(200, json=row)

        post = router.post(f"{BASE}/athlete/0/events").mock(side_effect=write)
        yield rows, post, write


def note(key="a", name="Session"):
    return PlanEvent(event_key=key, start_date_local="2026-11-02", name=name, category="NOTE")


async def test_preview_no_remote_write_and_duplicate_commit(config, calendar):
    rows, post, _ = calendar
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        assert post.call_count == 0 and p["items"][0]["action"] == "create"
        assert (await commit(api, p["preview_id"]))["complete"]
        assert (await commit(api, p["preview_id"]))["complete"]
        fresh = await preview(api, "week", [note()])
        assert fresh["items"][0]["action"] == "unchanged"
    assert len(rows) == post.call_count == 1


async def test_update_reuses_uid(config, calendar):
    rows, _, _ = calendar
    async with API(config) as api:
        original = await preview(api, "week", [note()])
        await commit(api, original["preview_id"])
        updated = await preview(api, "week", [note(name="Edited")])
        assert updated["items"][0]["action"] == "update"
        await commit(api, updated["preview_id"])
    assert len(rows) == 1 and rows[0]["name"] == "Edited"


async def test_moved_session_keeps_old_date_in_conflict_snapshot(config, calendar):
    rows, _, _ = calendar
    async with API(config) as api:
        original = await preview(api, "week", [note()])
        await commit(api, original["preview_id"])
        moved = note()
        moved.start_date_local = "2026-11-09T00:00:00"
        updated = await preview(api, "week", [moved])
        record = PreviewStore(config.data_dir).load(updated["preview_id"])
        assert record["oldest"] == "2026-11-02"
        rows[0]["name"] = "Manual edit after move preview"
        with pytest.raises(ValueError, match="planned event changed"):
            await commit(api, updated["preview_id"])


async def test_changed_external_calendar_blocks_all_writes(config, calendar):
    rows, post, _ = calendar
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        rows.append({"id": 8, "name": "New external entry", "category": "NOTE"})
        with pytest.raises(ValueError, match="Calendar changed"):
            await commit(api, p["preview_id"])
    assert post.call_count == 0


async def test_changed_own_event_blocks_replay(config, calendar):
    rows, _, _ = calendar
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        await commit(api, p["preview_id"])
        rows[0]["name"] = "Manual edit"
        with pytest.raises(ValueError, match="planned event changed"):
            await commit(api, p["preview_id"])


async def test_expiry_and_account_binding(config, calendar):
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        store = PreviewStore(config.data_dir)
        record = store.load(p["preview_id"])
        record["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        store.save(record)
        with pytest.raises(ValueError, match="expired"):
            await commit(api, p["preview_id"])
        record["athlete_id"] = "i2"
        store.save(record)
        with pytest.raises(ValueError, match="different athlete"):
            await commit(api, p["preview_id"])


async def test_timeout_after_write_is_verified(config, calendar):
    rows, post, writer = calendar

    def timed_out(request):
        writer(request)
        raise httpx.ReadTimeout("lost response")

    post.mock(side_effect=timed_out)
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        assert (await commit(api, p["preview_id"]))["complete"]
    assert len(rows) == post.call_count == 1


async def test_partial_failure_does_not_rollback(config, calendar):
    rows, post, writer = calendar

    def failing(request):
        return writer(request) if len(rows) == 0 else httpx.Response(403)

    post.mock(side_effect=failing)
    async with API(config) as api:
        p = await preview(api, "week", [note("a"), note("b"), note("c")])
        result = await commit(api, p["preview_id"])
    assert [r["status"] for r in result["results"]] == ["verified", "failed", "not_attempted"]
    assert len(rows) == 1 and result["automatic_rollback"] is False


async def test_uncertain_no_write_can_be_recovered(config, calendar):
    _, post, writer = calendar
    post.mock(side_effect=httpx.ReadTimeout("lost"))
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        first = await commit(api, p["preview_id"])
        assert first["results"][0]["status"] == "uncertain"
        post.mock(side_effect=writer)
        assert (await commit(api, p["preview_id"]))["complete"]


async def test_conflicts_require_explicit_preview_option(config, calendar):
    rows, post, _ = calendar
    rows.append(
        {"id": 8, "uid": "other", "category": "SICK", "start_date_local": "2026-11-02T00:00:00"}
    )
    async with API(config) as api:
        p = await preview(api, "week", [note()])
        assert not p["can_commit"]
        with pytest.raises(ValueError, match="conflicts"):
            await commit(api, p["preview_id"])
        assert post.call_count == 0
        allowed = await preview(api, "week", [note()], allow_conflicts=True)
        assert (await commit(api, allowed["preview_id"]))["complete"]


async def test_duplicate_event_keys_rejected(config, calendar):
    async with API(config) as api:
        with pytest.raises(ValueError, match="unique"):
            await preview(api, "week", [note(), note()])


def test_structured_workout_validation():
    with pytest.raises(ValueError, match="Structured WORKOUT"):
        PlanEvent(
            event_key="a",
            start_date_local="2026-11-02",
            name="Run",
            event_type="Run",
            description="bad",
        ).payload("i1", "week")
    p = PlanEvent(
        event_key="a",
        start_date_local="2026-11-02",
        name="Run",
        event_type="Run",
        description="Warmup\n- 10m 70% Pace",
    ).payload("i1", "week")
    assert p["type"] == "Run"
    with pytest.raises(ValueError):
        PlanEvent(event_key="a", start_date_local="2026-11-02T08:00:00", name="x")


async def test_parse_unverified_reported(config, calendar):
    rows, post, writer = calendar

    def unparsed(request):
        response = writer(request)
        rows[-1].pop("workout_doc", None)
        return response

    post.mock(side_effect=unparsed)
    event = PlanEvent(
        event_key="a",
        start_date_local="2026-11-02",
        name="Run",
        event_type="Run",
        description="- 10m 70% Pace",
    )
    async with API(config) as api:
        p = await preview(api, "week", [event])
        result = await commit(api, p["preview_id"])
        repeated = await commit(api, p["preview_id"])
    assert not result["complete"] and result["results"][0]["status"] == "written_parse_unverified"
    assert not repeated["complete"]
