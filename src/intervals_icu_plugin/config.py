"""Credentials never fall back to plaintext storage or the caller's .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import keyring
from platformdirs import user_data_path

SERVICE = "codex-intervals-icu-mcp"


@dataclass
class Config:
    api_key: str = field(repr=False)
    athlete_id: str = "0"
    timezone: str | None = None
    source: str = "environment"
    data_dir: Path = field(default_factory=lambda: user_data_path("intervals-icu-plugin"))

    def __post_init__(self):
        if not self.api_key.strip():
            raise ValueError(
                "Missing API key. Run intervals-icu-plugin setup or configure environment variables."
            )
        if not self.athlete_id or not self.athlete_id.removeprefix("i").isdigit():
            raise ValueError("Athlete ID must be 0, a numeric ID, or i followed by digits.")


def secure_backend():
    backend = keyring.get_keyring()
    # Chainer backends can include plaintext backends: select a concrete secure provider.
    candidates = getattr(backend, "backends", [backend])
    for candidate in candidates:
        module = type(candidate).__module__
        if module.startswith(
            (
                "keyring.backends.Windows",
                "keyring.backends.macOS",
                "keyring.backends.SecretService",
                "keyring.backends.kwallet",
            )
        ):
            return candidate
    raise RuntimeError(
        "No supported secure credential store. Use environment variables; plaintext fallback is disabled."
    )


def load_config() -> Config:
    api_key = os.environ.get("INTERVALS_ICU_API_KEY", "").strip()
    athlete_id = os.environ.get("INTERVALS_ICU_ATHLETE_ID", "").strip()
    source = "environment"
    if not api_key:
        try:
            backend = secure_backend()
            api_key = backend.get_password(SERVICE, "api-key") or ""
            athlete_id = athlete_id or backend.get_password(SERVICE, "athlete-id") or "0"
            source = "secure credential store"
        except Exception:
            raise ValueError(
                "Credentials unavailable. Run setup or set INTERVALS_ICU_API_KEY (secure store may be inaccessible)."
            ) from None
    return Config(
        api_key, athlete_id or "0", os.environ.get("INTERVALS_ICU_TIMEZONE") or None, source
    )


def prepare_upstream(config: Config):
    os.environ["INTERVALS_ICU_API_KEY"] = config.api_key
    os.environ["INTERVALS_ICU_ATHLETE_ID"] = config.athlete_id
    os.environ["INTERVALS_ICU_DELETE_MODE"] = "none"
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    # The portable package is the cwd; callers' project .env files are never read.
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
