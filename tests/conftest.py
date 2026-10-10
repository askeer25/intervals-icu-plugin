import os

import pytest

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["INTERVALS_ICU_API_KEY"] = "unit-key"
os.environ["INTERVALS_ICU_ATHLETE_ID"] = "0"
os.environ["INTERVALS_ICU_DELETE_MODE"] = "none"

from intervals_icu_plugin.config import Config  # noqa: E402


@pytest.fixture
def config(tmp_path):
    return Config("unit-key", "0", data_dir=tmp_path)
