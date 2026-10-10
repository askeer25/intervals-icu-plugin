"""Lossless values plus compatibility fields, units, and source availability."""

from datetime import UTC, datetime
from typing import Any

from .api import APIError

SOURCE_NOTE = "Strava activity data is restricted by the public API. Garmin API availability may change (official notice 2026-10-09); do not infer restriction solely from device brand."


def available(row: dict) -> dict:
    restricted = row.get("source") == "STRAVA" and all(
        row.get(k) is None
        for k in ("distance", "moving_time", "average_heartrate", "icu_average_watts")
    )
    return {
        "status": "restricted" if restricted else "available_or_partial",
        "source": row.get("source"),
        "device_name": row.get("device_name"),
        "attribution": "Garmin" if "garmin" in str(row.get("device_name", "")).lower() else None,
    }


def intensity(value):
    return (
        {}
        if value is None
        else {
            "intensity_factor": value,
            "intensity_percent": value,
            "intensity_factor_ratio": value / 100,
        }
    )


def pick(row: dict, mapping: dict) -> dict:
    return {
        target: row[source] for source, target in mapping.items() if row.get(source) is not None
    }


def activity(row: dict, details: bool = False) -> dict:
    result = {
        "id": row["id"],
        "name": row.get("name") or "Untitled",
        "start_date": row.get("start_date_local"),
        "type": row.get("type"),
    }
    result.update(
        pick(
            row,
            {
                "distance": "distance_meters",
                "moving_time": "moving_time_seconds",
                "elapsed_time": "elapsed_time_seconds",
                "total_elevation_gain": "elevation_gain_meters",
                "average_heartrate": "average_heartrate",
                "average_cadence": "average_cadence",
                "icu_average_watts": "average_watts",
                "icu_weighted_avg_watts": "normalized_power",
                "icu_training_load": "training_load",
                "trainer": "trainer",
                "indoor": "indoor",
                "commute": "commute",
                "paired_event_id": "paired_event_id",
            },
        )
    )
    result.update(intensity(row.get("icu_intensity")))
    result["availability"] = available(row)
    distance, seconds = row.get("distance"), row.get("moving_time")
    if distance is not None and distance > 0 and seconds is not None and seconds > 0:
        result["pace_seconds_per_km"] = seconds / (distance / 1000)
    if details:
        result.update(
            pick(
                row,
                {
                    "description": "description",
                    "average_speed": "average_speed_meters_per_sec",
                    "max_speed": "max_speed_meters_per_sec",
                },
            )
        )
        groups = {
            "power": {
                "icu_average_watts": "average",
                "icu_weighted_avg_watts": "normalized",
                "max_watts": "max",
                "icu_variability_index": "variability_index",
                "icu_efficiency_factor": "efficiency_factor",
            },
            "heart_rate": {"average_heartrate": "average", "max_heartrate": "max"},
            "cadence": {"average_cadence": "average", "max_cadence": "max"},
            "nutrition": {
                "calories": "calories_burned",
                "carbs_ingested": "carbs_ingested_g",
                "carbs_used": "carbs_used_g",
            },
            "subjective": {"feel": "feel", "perceived_exertion": "rpe"},
            "other": {
                "device_name": "device",
                "indoor": "indoor",
                "trainer": "trainer",
                "commute": "commute",
            },
        }
        for key, mapping in groups.items():
            values = pick(row, mapping)
            if values:
                result[key] = values
        result["training"] = {
            **pick(
                row,
                {
                    "icu_training_load": "training_load",
                    "tss": "tss",
                    "hrss": "hrss",
                    "trimp": "trimp",
                },
            ),
            **intensity(row.get("icu_intensity")),
        }
        # Preserve custom fields and unfamiliar API fields without exposing them as inferred metrics.
        result["raw_fields"] = row
    return result


WELLNESS_GROUPS = {
    "sleep": {
        "sleepSecs": "duration_seconds",
        "sleepQuality": "quality",
        "sleepScore": "score",
        "avgSleepingHR": "avg_sleeping_hr",
    },
    "heart": {"hrv": "hrv_rmssd", "hrvSDNN": "hrv_sdnn", "restingHR": "resting_hr"},
    "subjective": {
        k: k
        for k in (
            "fatigue",
            "soreness",
            "stress",
            "mood",
            "motivation",
            "injury",
            "hydration",
            "readiness",
        )
    },
    "body": {
        "weight": "weight_kg",
        "bodyFat": "body_fat_percent",
        "abdomen": "abdomen_cm",
        "vo2max": "vo2max",
    },
    "activity": {"steps": "steps"},
    "training": {"ctl": "ctl", "atl": "atl", "tsb": "tsb", "rampRate": "ramp_rate"},
    "state_flags": {
        "locked": "locked",
        "tempWeight": "temp_weight",
        "tempRestingHR": "temp_resting_hr",
    },
}


def wellness(row: dict) -> dict:
    result = {"date": row["id"], "raw_fields": row}
    for key, mapping in WELLNESS_GROUPS.items():
        values = pick(row, mapping)
        if (
            key == "training"
            and values.get("tsb") is None
            and row.get("ctl") is not None
            and row.get("atl") is not None
        ):
            values["tsb"] = row["ctl"] - row["atl"]
        if values:
            result[key] = values
    return result


def metadata(**kwargs):
    return {
        "fetched_at": datetime.now(UTC).isoformat(),
        "units": {
            "intensity_factor": "percent (deprecated)",
            "intensity_percent": "%",
            "intensity_factor_ratio": "ratio",
            "distance_meters": "m",
            "moving_time_seconds": "s",
            "pace_seconds_per_km": "s/km",
        },
        "source_policy_note": SOURCE_NOTE,
        **kwargs,
    }


def response(data: Any, analysis: dict | None = None, **meta):
    result = {"data": data, "metadata": metadata(**meta)}
    if analysis is not None:
        result["analysis"] = analysis
    return result


def error(exc: Exception):
    kind = (
        exc.kind
        if isinstance(exc, APIError)
        else "validation"
        if isinstance(exc, ValueError)
        else "internal"
    )
    message = (
        str(exc)
        if isinstance(exc, (APIError, ValueError))
        else "Unexpected plugin error; private details were omitted."
    )
    result: dict[str, Any] = {"error": {"type": kind, "message": message}}
    if isinstance(exc, APIError):
        result["error"].update(
            status=exc.status, uncertain=exc.uncertain, retry_after=exc.retry_after
        )
    return result
