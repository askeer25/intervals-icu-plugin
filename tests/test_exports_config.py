import os

import pytest
import respx

from intervals_icu_plugin.api import API, APIError
from intervals_icu_plugin.config import Config, load_config, secure_backend
from intervals_icu_plugin.exporting import export_workout, save_export, validate_workout_file

BASE = "https://intervals.icu/api/v1"


@pytest.mark.parametrize(
    "name",
    ["../secret.fit", "a/b.fit", "..fit", "/root.fit", "CON/fit", "CON.fit", "LPT1.fit", "name."],
)
def test_filename_boundaries(tmp_path, name):
    with pytest.raises(ValueError):
        save_export(tmp_path, b"data", name)


def test_exclusive_file_and_outside_path(tmp_path):
    first = save_export(tmp_path, b"original", "a.fit")
    with pytest.raises(ValueError, match="already exists"):
        save_export(tmp_path, b"overwrite", "a.fit")
    assert (tmp_path / "exports/a.fit").read_bytes() == b"original"
    with pytest.raises(ValueError, match="inside"):
        save_export(tmp_path, b"x", "b.fit", str(tmp_path / "outside.fit"))
    assert first["size_bytes"] == 8


def test_export_size_and_empty(tmp_path):
    with pytest.raises(ValueError):
        save_export(tmp_path, b"", "a.fit")


@pytest.mark.parametrize(
    "fmt,content",
    [
        ("zwo", b"<workout_file><workout/></workout_file>"),
        ("fit", b"\x0e\x00\x00\x00\x00\x00\x00\x00.FIT"),
        ("mrc", b"[COURSE HEADER]\n[END COURSE HEADER]"),
        ("erg", b"[COURSE HEADER]\n[END COURSE HEADER]"),
    ],
)
def test_workout_signatures(fmt, content):
    validate_workout_file(content, fmt)
    with pytest.raises(APIError):
        validate_workout_file(b"<html>error</html>", fmt)


@respx.mock
async def test_event_export_get(config):
    route = respx.get(f"{BASE}/athlete/0/events/1/download.zwo").respond(
        content=b"<workout_file><workout/></workout_file>"
    )
    async with API(config) as api:
        result = await export_workout(api, "zwo", 1, None, None)
    assert result["format"] == "zwo" and route.call_count == 1


@respx.mock
async def test_library_export_conversion(config):
    respx.get(f"{BASE}/athlete/0/workouts/2").respond(json={"id": 2, "description": "- 10m 70%"})
    route = respx.post(f"{BASE}/athlete/0/download-workout.mrc").respond(
        content=b"[COURSE HEADER]\n[END COURSE HEADER]"
    )
    async with API(config) as api:
        result = await export_workout(api, "mrc", None, 2, None)
    assert result["format"] == "mrc" and route.call_count == 1


async def test_export_input_exclusive(config):
    async with API(config) as api:
        with pytest.raises(ValueError, match="exactly one"):
            await export_workout(api, "fit", 1, 2, None)


def test_environment_precedence_and_repr(monkeypatch):
    monkeypatch.setenv("INTERVALS_ICU_API_KEY", "unit-key")
    monkeypatch.delenv("INTERVALS_ICU_ATHLETE_ID", raising=False)
    monkeypatch.setattr(
        "intervals_icu_plugin.config.secure_backend", lambda: pytest.fail("store must not be read")
    )
    config = load_config()
    assert config.athlete_id == "0" and config.source == "environment"
    assert "unit-key" not in repr(config)


def test_plaintext_backend_rejected(monkeypatch):
    class Plaintext:
        pass

    Plaintext.__module__ = "keyrings.alt.file"
    monkeypatch.setattr("intervals_icu_plugin.config.keyring.get_keyring", lambda: Plaintext())
    with pytest.raises(RuntimeError, match="plaintext"):
        secure_backend()


def test_no_implicit_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("INTERVALS_ICU_API_KEY=unit-key")
    monkeypatch.delenv("INTERVALS_ICU_API_KEY", raising=False)

    def fail():
        raise RuntimeError("secure store unavailable")

    monkeypatch.setattr("intervals_icu_plugin.config.secure_backend", fail)
    with pytest.raises(ValueError, match="Credentials unavailable"):
        load_config()
    assert "INTERVALS_ICU_API_KEY" not in os.environ


@pytest.mark.parametrize("athlete", ["../1", "i", "abc", ""])
def test_athlete_id_validation(athlete):
    with pytest.raises(ValueError):
        Config("unit-key", athlete)
