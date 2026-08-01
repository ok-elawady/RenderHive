from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.api.endpoints import DEFAULT_ENDPOINTS, validate_endpoints
from renderhive_houdini.api.config import normalize_config


def test_submitter_endpoints_match_openapi_paths():
    assert DEFAULT_ENDPOINTS["jobs"] == "/api/jobs/"
    assert DEFAULT_ENDPOINTS["workers"] == "/api/workers/"
    assert DEFAULT_ENDPOINTS["pools"] == "/api/pools/"
    assert validate_endpoints(DEFAULT_ENDPOINTS)


def test_config_uses_token_authentication():
    config = normalize_config({"auth": {"type": "token", "token": "test"}})
    assert config["auth"]["type"] == "token"
    assert config["auth"]["token"] == "test"
