"""Inspectable calculations from available observations only."""

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from .formatting import activity


def environment(row: dict) -> str:
    flags = [row.get("trainer"), row.get("indoor")]
    if any(v is True for v in flags) or row.get("type", "").startswith("Virtual"):
        return "indoor"
    if any(v is False for v in flags):
        return "outdoor"
    return "unknown"


def aggregate(rows: list[dict]) -> dict:
    result = {
        "count": len(rows),
        "metrics": {},
        "restricted_count": sum(
            activity(r)["availability"]["status"] == "restricted" for r in rows
        ),
    }
    for field, label in {
        "distance": "distance_meters",
        "moving_time": "moving_time_seconds",
        "icu_training_load": "training_load",
        "total_elevation_gain": "elevation_gain_meters",
    }.items():
        values = [r[field] for r in rows if r.get(field) is not None]
        result["metrics"][label] = {
            "sum": sum(values) if values else None,
            "valid_samples": len(values),
            "missing_samples": len(rows) - len(values),
        }
    zones = {}
    for field in ("icu_hr_zone_times", "icu_power_zone_times", "icu_pace_zone_times"):
        samples = [r[field] for r in rows if isinstance(r.get(field), list)]
        if samples:
            totals: dict[str, float] = defaultdict(float)
            for sample in samples:
                for index, value in enumerate(sample):
                    if isinstance(value, dict):
                        key, seconds = str(value.get("id", index + 1)), value.get("secs")
                    else:
                        key, seconds = str(index + 1), value
                    if isinstance(seconds, (int, float)):
                        totals[key] += seconds
            zones[field] = {"seconds_by_zone": dict(totals), "valid_samples": len(samples)}
    result["zones"] = zones
    result["method"] = (
        "Sums of non-null API values; different zone sources are never combined. Missing values are not zero."
    )
    return result


def training_summary(
    rows: list[dict], sport_types: list[str] | None, env: str, group_by: str
) -> dict:
    rows = [
        r
        for r in rows
        if (not sport_types or r.get("type") in sport_types)
        and (env == "all" or environment(r) == env)
    ]
    groups = defaultdict(list)
    undated = 0
    for row in rows:
        text = row.get("start_date_local")
        if not text:
            undated += 1
            continue
        day = date.fromisoformat(text[:10])
        key = (
            day.isoformat()
            if group_by == "day"
            else (day - timedelta(days=day.weekday())).isoformat()
            if group_by == "week"
            else day.strftime("%Y-%m")
        )
        groups[key].append(row)
    return {
        "totals": aggregate(rows),
        "groups": [{"period_start": k, **aggregate(v)} for k, v in sorted(groups.items())],
        "undated_count": undated,
        "environment_counts": {
            k: sum(environment(r) == k for r in rows) for k in ("indoor", "outdoor", "unknown")
        },
    }


def recovery(rows: list[dict], days: int):
    rows = sorted({r["id"]: r for r in rows}.values(), key=lambda r: r["id"])
    metrics = {}
    for field in (
        "hrv",
        "restingHR",
        "sleepSecs",
        "sleepQuality",
        "fatigue",
        "soreness",
        "stress",
        "readiness",
        "ctl",
        "atl",
        "tsb",
    ):
        values = [
            (r["id"], r[field])
            for r in rows
            if isinstance(r.get(field), (int, float)) and not isinstance(r[field], bool)
        ]
        metrics[field] = {
            "valid_samples": len(values),
            "missing_days": days - len(values),
            "mean": mean(v for _, v in values) if values else None,
            "latest": values[-1][1] if values else None,
            "latest_date": values[-1][0] if values else None,
            "change_first_to_last": values[-1][1] - values[0][1] if len(values) > 1 else None,
        }
    return {
        "covered_days": len(rows),
        "requested_days": days,
        "metrics": metrics,
        "method": "Observed non-null samples, first-to-last change. No composite readiness score or causal inference.",
        "sleep_quality_scale": "1=Great, 5=Poor; inverted scale",
    }


def adherence(events: list[dict], rows: list[dict]):
    pairs = defaultdict(list)
    for row in rows:
        if row.get("paired_event_id") is not None:
            pairs[str(row["paired_event_id"])].append(row)
    items = []
    for event in events:
        if event.get("category") != "WORKOUT":
            continue
        actual = pairs.get(str(event["id"]), [])
        item = {
            "event_id": event["id"],
            "name": event.get("name"),
            "date": event.get("start_date_local"),
            "status": "paired" if actual else "unconfirmed",
            "activity_ids": [r["id"] for r in actual],
            "planned": {},
            "actual": aggregate(actual),
        }
        for field in ("moving_time", "distance", "icu_training_load"):
            planned = event.get(field)
            valid = [r[field] for r in actual if r.get(field) is not None]
            item["planned"][field] = planned
            if actual and len(valid) == len(actual) and planned is not None and planned > 0:
                item.setdefault("ratios", {})[field] = sum(valid) / planned
        items.append(item)
    return {
        "workouts": items,
        "paired_count": sum(i["status"] == "paired" for i in items),
        "unconfirmed_count": sum(i["status"] == "unconfirmed" for i in items),
        "method": "Explicit paired_event_id only. Unpaired does not mean missed; no guessed matching.",
    }
