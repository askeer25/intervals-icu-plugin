"""Local export files: bounded names, exclusive creation, no Base64 payloads."""

import re
from pathlib import Path

from .api import API, APIError

MAX_EXPORT_BYTES = 50 * 1024 * 1024


def save_export(data_dir: Path, content: bytes, filename: str, output_path: str | None = None):
    directory = (data_dir / "exports").resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output_path:
        path = Path(output_path).expanduser().resolve()
        if not path.is_relative_to(directory):
            raise ValueError("output_path must be inside the plugin exports directory.")
    else:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", filename) or ".." in filename:
            raise ValueError("Use a plain filename without directories or '..'.")
        if filename.split(".", 1)[0].upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *[f"COM{i}" for i in range(1, 10)],
            *[f"LPT{i}" for i in range(1, 10)],
        } or filename.endswith("."):
            raise ValueError("Filename is reserved or invalid on Windows.")
        path = directory / filename
    if len(content) > MAX_EXPORT_BYTES or not content:
        raise ValueError("Export is empty or exceeds 50 MiB.")
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        raise ValueError("Export file already exists; choose another filename.") from None
    return {"saved_to": str(path), "size_bytes": len(content)}


def validate_workout_file(content: bytes, fmt: str):
    if fmt == "fit":
        valid = len(content) >= 12 and content[8:12] == b".FIT"
    else:
        text = content.decode("utf-8-sig", errors="replace")
        valid = "<workout_file" in text if fmt == "zwo" else "[COURSE HEADER]" in text.upper()
    if not valid:
        raise APIError(
            "invalid_response", f"Response is not a recognizable {fmt.upper()} workout file."
        )


async def export_workout(
    api: API, fmt: str, event_id: int | None, workout_id: int | None, filename: str | None
):
    if (event_id is None) == (workout_id is None):
        raise ValueError("Specify exactly one of event_id or workout_id.")
    if (event_id or workout_id or 0) <= 0:
        raise ValueError("IDs must be positive.")
    athlete = api.config.athlete_id
    if event_id is not None:
        result = await api.request("GET", f"/athlete/{athlete}/events/{event_id}/download.{fmt}")
        identity = f"event-{event_id}"
    else:
        workout = await api.json("GET", f"/athlete/{athlete}/workouts/{workout_id}")
        result = await api.request(
            "POST", f"/athlete/{athlete}/download-workout.{fmt}", json=workout
        )
        identity = f"workout-{workout_id}"
    validate_workout_file(result.content, fmt)
    selected = filename or f"{identity}.{fmt}"
    if not selected.lower().endswith(f".{fmt}"):
        raise ValueError("Filename extension must match the requested format.")
    return {**save_export(api.config.data_dir, result.content, selected), "format": fmt}
