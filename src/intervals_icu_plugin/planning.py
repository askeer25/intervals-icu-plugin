"""Previewed, conflict-checked UID upserts; progress survives uncertain writes."""

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api import API, APIError, date_range, parse_date


class PlanEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_key: str = Field(min_length=1, max_length=100)
    start_date_local: str
    name: str = Field(min_length=1, max_length=200)
    category: str = "WORKOUT"
    event_type: str | None = None
    description: str | None = Field(default=None, max_length=20000)
    duration_seconds: int | None = Field(default=None, ge=0)
    distance_meters: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    training_load: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end_date_local: str | None = None
    tags: list[str] | None = None

    @field_validator("start_date_local", "end_date_local")
    @classmethod
    def local_date(cls, value):
        if value is None:
            return None
        if "T" in value:
            if not value.endswith("T00:00:00"):
                raise ValueError("Plan dates must be dates or local midnight without offset.")
            value = value[:10]
        return parse_date(value).isoformat() + "T00:00:00"

    @field_validator("name", "event_key")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank.")
        return value.strip()

    def payload(self, athlete: str, plan_id: str):
        from intervals_icu_mcp.models import ACTIVITY_DISCIPLINES
        from intervals_icu_mcp.tools.event_management import VALID_CATEGORIES

        if self.category not in VALID_CATEGORIES:
            raise ValueError("Unsupported event category; read intervals-icu://event-categories.")
        if self.event_type is not None and self.event_type not in ACTIVITY_DISCIPLINES:
            raise ValueError("Unsupported activity discipline.")
        if self.end_date_local and self.end_date_local <= self.start_date_local:
            raise ValueError("end_date_local must be after start_date_local.")
        if self.category == "WORKOUT":
            if not self.event_type:
                raise ValueError("WORKOUT requires event_type.")
            steps = [
                line.strip()
                for line in (self.description or "").splitlines()
                if line.strip().startswith("-")
            ]
            if not steps or any(
                not re.match(r"^-\s+(?:\d+(?:\.\d+)?(?:km|m|s|h)|\d+:\d{2}(?::\d{2})?)\s+\S", line)
                for line in steps
            ):
                raise ValueError(
                    "Structured WORKOUT requires duration/distance-first '- 10m 70%' steps. Read workout-syntax; full parsing is verified by the server after writing."
                )
        payload = self.model_dump(exclude_none=True, exclude={"event_key"})
        for friendly, raw in {
            "event_type": "type",
            "duration_seconds": "moving_time",
            "distance_meters": "distance",
            "training_load": "icu_training_load",
        }.items():
            if friendly in payload:
                payload[raw] = payload.pop(friendly)
        payload["uid"] = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                json.dumps(
                    ["intervals-icu-plugin", athlete, plan_id, self.event_key],
                    separators=(",", ":"),
                ),
            )
        )
        return payload


def fingerprint(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def event_snapshot(row: dict | None):
    if row is None:
        return None
    keys = (
        "id",
        "uid",
        "name",
        "description",
        "category",
        "type",
        "start_date_local",
        "end_date_local",
        "moving_time",
        "distance",
        "icu_training_load",
        "tags",
        "updated",
    )
    return {k: row.get(k) for k in keys}


def same_payload(row: dict | None, payload: dict) -> bool:
    if row is None:
        return False
    return all(row.get(k) == v for k, v in payload.items())


def snapshots(rows: list[dict], excluded: set[str]):
    return sorted(
        [event_snapshot(r) for r in rows if r.get("uid") not in excluded],
        key=lambda r: str(r.get("id")) if r else "",
    )


class PreviewStore:
    def __init__(self, root: Path):
        self.root = root / "previews"

    def directory(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, preview_id: str):
        if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
            raise ValueError("Invalid preview ID.")
        return self.root / f"{preview_id}.json"

    def save(self, record: dict):
        self.directory()
        target = self.path(record["preview_id"])
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False)
        os.replace(temporary, target)

    def load(self, preview_id: str):
        try:
            return json.loads(self.path(preview_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("Preview not found; generate a new preview.") from None


async def preview(api: API, plan_id: str, events: list[PlanEvent], allow_conflicts: bool = False):
    if not plan_id.strip() or len(plan_id) > 100 or not 1 <= len(events) <= 100:
        raise ValueError("Use a nonblank plan_id of at most 100 characters and 1–100 events.")
    if len({e.event_key for e in events}) != len(events):
        raise ValueError("event_key must be unique within the plan.")
    profile = await api.athlete()
    athlete = str(profile["id"])
    payloads = [e.payload(athlete, plan_id) for e in events]
    oldest = min(p["start_date_local"][:10] for p in payloads)
    newest = max((p.get("end_date_local") or p["start_date_local"])[:10] for p in payloads)
    # An edit can move a session outside the new dates. Retained local previews
    # identify its old date so the existing event is included in the snapshot.
    uids = {p["uid"] for p in payloads}
    store = PreviewStore(api.config.data_dir)
    for path in store.root.glob("*.json"):
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if history.get("athlete_id") != athlete:
            continue
        for item in history.get("items", []):
            if item.get("payload", {}).get("uid") in uids:
                for row in (item["payload"], item.get("original") or {}):
                    if row.get("start_date_local"):
                        oldest = min(oldest, row["start_date_local"][:10])
                        newest = max(
                            newest, (row.get("end_date_local") or row["start_date_local"])[:10]
                        )
    date_range(oldest, newest)
    existing = await api.events(oldest, newest)
    by_uid = {r["uid"]: r for r in existing if r.get("uid")}
    conflicts = []
    items = []
    for event, payload in zip(events, payloads, strict=True):
        current = by_uid.get(payload["uid"])
        action = (
            "unchanged" if same_payload(current, payload) else "update" if current else "create"
        )
        for row in existing:
            left = row.get("start_date_local", "")[:10]
            right = (row.get("end_date_local") or row.get("start_date_local", ""))[:10]
            if (
                row.get("uid") not in uids
                and left <= payload["start_date_local"][:10] <= right
                and (
                    row.get("category") in {"SICK", "INJURED", "HOLIDAY"}
                    or row.get("category") == "WORKOUT"
                    and row.get("type") == payload.get("type")
                )
            ):
                conflicts.append(
                    {
                        "event_key": event.event_key,
                        "existing_event_id": row["id"],
                        "category": row.get("category"),
                    }
                )
        items.append(
            {
                "event_key": event.event_key,
                "action": action,
                "payload": payload,
                "original": event_snapshot(current),
                "status": "pending",
            }
        )
    now = datetime.now(UTC)
    record = {
        "preview_id": uuid.uuid4().hex,
        "athlete_id": athlete,
        "plan_id": plan_id,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
        "oldest": oldest,
        "newest": newest,
        "external_snapshot": fingerprint(snapshots(existing, uids)),
        "conflicts": conflicts,
        "allow_conflicts": allow_conflicts,
        "items": items,
    }
    PreviewStore(api.config.data_dir).save(record)
    return {
        "preview_id": record["preview_id"],
        "expires_at": record["expires_at"],
        "athlete_id": athlete,
        "items": [{k: v for k, v in i.items() if k != "original"} for i in items],
        "conflicts": conflicts,
        "can_commit": not conflicts or allow_conflicts,
        "syntax_validation": "Conservative local step validation; authoritative server parse checked after commit.",
    }


async def commit(api: API, preview_id: str):
    store = PreviewStore(api.config.data_dir)
    record = store.load(preview_id)
    athlete = str((await api.athlete())["id"])
    if record["athlete_id"] != athlete:
        raise ValueError("Preview belongs to a different athlete.")
    store.directory()
    # Nonblocking lock: another request cannot interleave this account's writes.
    with FileLock(str(store.root / (fingerprint(athlete) + ".lock")), timeout=0):
        record = store.load(preview_id)
        if datetime.fromisoformat(record["expires_at"]) <= datetime.now(UTC):
            raise ValueError("Preview expired; generate a new preview.")
        if record["conflicts"] and not record["allow_conflicts"]:
            raise ValueError(
                "Preview has conflicts. Resolve them or explicitly preview with allow_conflicts=true."
            )
        rows = await api.events(record["oldest"], record["newest"])
        uids = {i["payload"]["uid"] for i in record["items"]}
        if fingerprint(snapshots(rows, uids)) != record["external_snapshot"]:
            raise ValueError("Calendar changed since preview; generate a new preview.")
        by_uid = {r["uid"]: r for r in rows if r.get("uid")}
        # Check every item before starting any write.
        for item in record["items"]:
            current = by_uid.get(item["payload"]["uid"])
            if item["status"] in {"verified", "uncertain"} and same_payload(
                current, item["payload"]
            ):
                continue
            if event_snapshot(current) != item["original"]:
                raise ValueError("A planned event changed since preview; generate a new preview.")
        results = []
        for item in record["items"]:
            payload = item["payload"]
            current = by_uid.get(payload["uid"])
            if same_payload(current, payload):
                assert current is not None
                item["status"] = "verified"
                syntax_ok = payload["category"] != "WORKOUT" or bool(
                    (current.get("workout_doc") or {}).get("steps")
                )
                results.append(
                    {
                        "event_key": item["event_key"],
                        "status": "verified" if syntax_ok else "written_parse_unverified",
                        "event_id": current["id"],
                        "action": "unchanged",
                    }
                )
                store.save(record)
                continue
            # Persist uncertain BEFORE sending: crashes must not silently lose write state.
            item["status"] = "uncertain"
            store.save(record)
            failure = None
            try:
                await api.json(
                    "POST",
                    f"/athlete/{api.config.athlete_id}/events",
                    params={"upsertOnUid": "true"},
                    json=payload,
                )
            except APIError as exc:
                failure = exc
            try:
                fresh = await api.events(record["oldest"], record["newest"])
                found = next((r for r in fresh if r.get("uid") == payload["uid"]), None)
                if same_payload(found, payload):
                    assert found is not None
                    item["status"] = "verified"
                    by_uid[payload["uid"]] = found
                    syntax_ok = payload["category"] != "WORKOUT" or bool(
                        (found.get("workout_doc") or {}).get("steps")
                    )
                    result = {
                        "event_key": item["event_key"],
                        "event_id": found["id"],
                        "status": "verified" if syntax_ok else "written_parse_unverified",
                        "action": item["action"],
                    }
                else:
                    item["status"] = "pending" if failure and not failure.uncertain else "uncertain"
                    result = {
                        "event_key": item["event_key"],
                        "status": "failed" if item["status"] == "pending" else "uncertain",
                        "error_type": failure.kind if failure else "verification_mismatch",
                    }
            except APIError:
                result = {
                    "event_key": item["event_key"],
                    "status": "uncertain",
                    "error_type": "verification_unavailable",
                }
            store.save(record)
            results.append(result)
            if result["status"] in {"uncertain", "failed"}:
                results.extend(
                    {"event_key": remaining["event_key"], "status": "not_attempted"}
                    for remaining in record["items"][len(results) :]
                )
                break
        return {
            "preview_id": preview_id,
            "results": results,
            "complete": all(r["status"] == "verified" for r in results),
            "transactional": False,
            "automatic_rollback": False,
        }
