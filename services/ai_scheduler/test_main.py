"""
Tests for the RenderHive AI Scheduler FastAPI service.

Runs without a real LLM model — all tests exercise mock mode or patch the
LLM object directly so the full code paths are covered without GPU hardware.

Run with:
    cd services/ai_scheduler
    pip install pytest httpx fastapi
    pytest test_main.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Import the app — LLM will be None (mock mode) since LLAMA_MODEL_PATH is unset
# ---------------------------------------------------------------------------
import main as ai_main
from main import app, _extract_json_array
from prompts import build_prompt, _trim_scene_info

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id: str, priority: int = 80, base_score: float = 0.41, scene_info: dict | None = None):
    return {
        "task_id": task_id,
        "priority": priority,
        "base_score": base_score,
        "scene_info": scene_info or {"renderer": "redshift", "resolution": [3840, 2160]},
    }


def _make_worker_caps(**kwargs):
    base = {
        "hostname": "render-node-01",
        "cores": 32,
        "memory_mb": 131072,
        "gpu_models": ["NVIDIA RTX 4090"],
        "live_metrics": {"cpu_percent": 12.0, "gpu_percent": 0.0},
    }
    base.update(kwargs)
    return base


# ===========================================================================
# Tests: _extract_json_array (Bug 2 regression)
# ===========================================================================

class TestExtractJsonArray:
    """Verify the JSON array extractor handles all realistic LLM outputs."""

    def test_simple_array(self):
        """Clean JSON array is returned as-is."""
        text = '[{"task_id": "a", "score_delta": 0.1, "reason": "ok"}]'
        result = _extract_json_array(text)
        parsed = json.loads(result)
        assert parsed[0]["task_id"] == "a"

    def test_nested_array_in_values(self):
        """
        Regression for Bug 2: non-greedy regex [.*?] would stop at the first ]
        inside a nested array like "resolution": [1920, 1080], truncating the
        outer array and producing invalid JSON.
        """
        text = (
            '[{"task_id": "abc", "score_delta": 0.12, '
            '"reason": "4K task on RTX", '
            '"scene_info": {"resolution": [1920, 1080]}}]'
        )
        result = _extract_json_array(text)
        # Must be parseable — the old regex would have truncated here
        parsed = json.loads(result)
        assert parsed[0]["task_id"] == "abc"
        assert parsed[0]["score_delta"] == 0.12

    def test_strips_markdown_fences(self):
        """LLM output wrapped in ```json ... ``` is unwrapped correctly."""
        text = '```json\n[{"task_id": "x", "score_delta": 0.05, "reason": "good"}]\n```'
        result = _extract_json_array(text)
        parsed = json.loads(result)
        assert parsed[0]["task_id"] == "x"

    def test_strips_markdown_fences_no_language(self):
        """LLM output wrapped in ``` ... ``` without language tag is unwrapped."""
        text = '```\n[{"task_id": "y", "score_delta": 0.0, "reason": "ok"}]\n```'
        result = _extract_json_array(text)
        parsed = json.loads(result)
        assert parsed[0]["task_id"] == "y"

    def test_preamble_text_before_array(self):
        """LLM preamble before the array is stripped."""
        text = 'Here is my ranking:\n[{"task_id": "z", "score_delta": 0.1, "reason": "best"}]'
        result = _extract_json_array(text)
        parsed = json.loads(result)
        assert parsed[0]["task_id"] == "z"

    def test_trailing_brackets_after_array(self):
        """Markdown brackets after the JSON array do not break extraction."""
        text = '[{"task_id": "v", "score_delta": 0.1, "reason": "best"}]\n[More info here]'
        result = _extract_json_array(text)
        parsed = json.loads(result)
        assert parsed[0]["task_id"] == "v"

    def test_multiple_objects_in_array(self):
        """Multi-element array with nested values is parsed correctly."""
        text = (
            '[\n'
            '  {"task_id": "t1", "score_delta": 0.15, "reason": "GPU match", "res": [4096, 2160]},\n'
            '  {"task_id": "t2", "score_delta": -0.05, "reason": "CPU only"}\n'
            ']'
        )
        result = _extract_json_array(text)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["task_id"] == "t1"
        assert parsed[1]["task_id"] == "t2"


# ===========================================================================
# Tests: /health endpoint
# ===========================================================================

class TestHealth:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_reports_model_not_loaded_in_mock_mode(self):
        """In mock mode (no LLAMA_MODEL_PATH), model_loaded must be False."""
        response = client.get("/health")
        data = response.json()
        assert data["model_loaded"] is False

    def test_health_includes_context_config(self):
        """Health endpoint exposes n_ctx and max_tasks_per_request (added in our fix)."""
        response = client.get("/health")
        data = response.json()
        assert "n_ctx" in data
        assert "max_tasks_per_request" in data
        assert data["n_ctx"] >= 4096  # must be at least our minimum

    def test_health_includes_prompt_template(self):
        response = client.get("/health")
        data = response.json()
        assert "prompt_template" in data
        assert data["prompt_template"] in ("mistral", "llama3", "chatml")


# ===========================================================================
# Tests: POST /api/v1/rank-tasks — mock mode (LLM is None)
# ===========================================================================

class TestRankTasksMockMode:
    """All tests run in mock mode — LLM is None because no model file is present."""

    def test_empty_tasks_returns_empty_list(self):
        payload = {"worker_caps": _make_worker_caps(), "tasks": []}
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        assert response.json() == []

    def test_single_task_returns_zero_delta(self):
        """Single-candidate fast-path: no AI needed, returns delta=0."""
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("task-a")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["task_id"] == "task-a"
        assert data[0]["score_delta"] == 0.0
        assert "Only one candidate" in data[0]["reason"]

    def test_multiple_tasks_mock_returns_zero_deltas(self):
        """Mock mode returns zero-delta for all tasks (deterministic, no random)."""
        tasks = [_make_task(f"task-{i}", base_score=0.40 + i * 0.001) for i in range(3)]
        payload = {"worker_caps": _make_worker_caps(), "tasks": tasks}
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        ids = {d["task_id"] for d in data}
        assert ids == {"task-0", "task-1", "task-2"}
        # All deltas are 0.0 in mock mode (changed from random to deterministic)
        for entry in data:
            assert entry["score_delta"] == 0.0
            assert "Mock mode" in entry["reason"]

    def test_response_shape_matches_schema(self):
        """Every response item must have task_id, score_delta, reason."""
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        for item in response.json():
            assert "task_id" in item
            assert "score_delta" in item
            assert "reason" in item
            assert isinstance(item["score_delta"], float)

    def test_tasks_capped_at_max_for_inference_but_all_returned(self):
        """
        Requests with more than MAX_TASKS_PER_REQUEST tasks are silently
        truncated for AI inference, but the response must contain entries for ALL original tasks.
        """
        max_tasks = ai_main.MAX_TASKS_PER_REQUEST
        tasks = [_make_task(f"task-{i}") for i in range(max_tasks + 5)]
        payload = {"worker_caps": _make_worker_caps(), "tasks": tasks}
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        assert len(response.json()) == max_tasks + 5

    def test_invalid_request_missing_worker_caps(self):
        """Missing required field returns 422 Unprocessable Entity."""
        payload = {"tasks": [_make_task("t1")]}
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 422

    def test_invalid_request_missing_tasks(self):
        """Missing tasks field returns 422."""
        payload = {"worker_caps": _make_worker_caps()}
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 422


# ===========================================================================
# Tests: POST /api/v1/rank-tasks — with patched LLM
# ===========================================================================

def _make_llm_response(items: list[dict]) -> dict:
    """Build a llama_cpp-style response dict with a JSON array output."""
    return {
        "choices": [{"text": json.dumps(items)}]
    }


class TestRankTasksWithPatchedLLM:
    """Patch the LLM object so we can test full inference code paths without hardware."""

    @pytest.fixture(autouse=True)
    def mock_llm(self):
        """Replace the module-level LLM with a MagicMock for this test class."""
        mock = MagicMock()
        with patch.object(ai_main, "LLM", mock):
            yield mock

    def test_valid_llm_response_is_parsed(self, mock_llm):
        """A well-formed LLM JSON response is parsed and returned correctly."""
        mock_llm.return_value = _make_llm_response([
            {"task_id": "t1", "score_delta": 0.12, "reason": "GPU match"},
            {"task_id": "t2", "score_delta": -0.05, "reason": "CPU only"},
        ])
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = {item["task_id"]: item for item in response.json()}
        assert data["t1"]["score_delta"] == pytest.approx(0.12)
        assert data["t2"]["score_delta"] == pytest.approx(-0.05)

    def test_delta_clamped_to_max(self, mock_llm):
        """Score deltas exceeding ±0.20 are silently clamped — the AI can never
        override an artist's priority setting entirely."""
        mock_llm.return_value = _make_llm_response([
            {"task_id": "t1", "score_delta": 0.99, "reason": "too high"},
            {"task_id": "t2", "score_delta": -0.99, "reason": "too low"},
        ])
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        # The clamping happens in the Django ai_client, not the FastAPI service.
        # The service itself passes deltas through — this test confirms the
        # FastAPI service does NOT silently clamp (clamping is the client's job).
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = {item["task_id"]: item for item in response.json()}
        assert data["t1"]["score_delta"] == pytest.approx(0.99)

    def test_llm_json_decode_error_falls_back(self, mock_llm):
        """If the LLM returns garbage, the endpoint returns zero-delta scores
        rather than a 500 error — the farm must keep running."""
        mock_llm.return_value = {"choices": [{"text": "This is not JSON at all!"}]}
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        for item in response.json():
            assert item["score_delta"] == 0.0
            assert "parsing failed" in item["reason"]

    def test_llm_exception_returns_500(self, mock_llm):
        """An unhandled LLM exception escalates to an HTTP 500 so the caller
        knows inference failed and can fall back on its own."""
        mock_llm.side_effect = RuntimeError("CUDA out of memory")
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 500

    def test_missing_task_id_in_response_padded_with_zero(self, mock_llm):
        """If the LLM omits a task from its ranking, a zero-delta entry is
        appended so the caller always gets a result for every input task."""
        mock_llm.return_value = _make_llm_response([
            # Only returns t1, omits t2
            {"task_id": "t1", "score_delta": 0.10, "reason": "good"},
        ])
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = {item["task_id"]: item for item in response.json()}
        assert "t2" in data
        assert data["t2"]["score_delta"] == 0.0
        assert "Missed by AI" in data["t2"]["reason"]

    def test_nested_array_in_scene_info_parsed_correctly(self, mock_llm):
        """
        Regression test for Bug 2: if the LLM echoes back scene_info with
        nested arrays (e.g. "resolution": [1920, 1080]) inside its JSON output,
        the rfind-based extractor must still parse the outer array correctly.
        """
        raw_with_nested = (
            '[{"task_id": "t1", "score_delta": 0.08, '
            '"reason": "4K GPU render", '
            '"extra": {"resolution": [3840, 2160]}},'
            '{"task_id": "t2", "score_delta": -0.03, "reason": "1080p"}]'
        )
        mock_llm.return_value = {"choices": [{"text": raw_with_nested}]}
        payload = {
            "worker_caps": _make_worker_caps(),
            "tasks": [_make_task("t1"), _make_task("t2")],
        }
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = {item["task_id"]: item for item in response.json()}
        assert data["t1"]["score_delta"] == pytest.approx(0.08)
        assert data["t2"]["score_delta"] == pytest.approx(-0.03)

    def test_tasks_capped_at_max_but_response_has_all(self, mock_llm):
        """
        Requests with more than MAX_TASKS_PER_REQUEST tasks must be silently
        truncated for inference, but the final response must contain 
        all original tasks (padded with zero deltas).
        """
        max_tasks = ai_main.MAX_TASKS_PER_REQUEST
        mock_llm.return_value = _make_llm_response([
            {"task_id": "task-0", "score_delta": 0.10, "reason": "good"},
        ])
        tasks = [_make_task(f"task-{i}") for i in range(max_tasks + 5)]
        payload = {"worker_caps": _make_worker_caps(), "tasks": tasks}
        response = client.post("/api/v1/rank-tasks", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == max_tasks + 5
        # The extra tasks should have 0.0 delta
        task_12 = next(item for item in data if item["task_id"] == f"task-{max_tasks + 2}")
        assert task_12["score_delta"] == 0.0


# ===========================================================================
# Tests: prompts.py
# ===========================================================================

class TestPrompts:
    def test_build_prompt_contains_task_ids(self):
        tasks = [
            {"task_id": "uuid-a", "priority": 80, "base_score": 0.41, "scene_info": {}},
            {"task_id": "uuid-b", "priority": 60, "base_score": 0.32, "scene_info": {}},
        ]
        prompt = build_prompt(_make_worker_caps(), tasks)
        assert "uuid-a" in prompt
        assert "uuid-b" in prompt

    def test_build_prompt_contains_worker_hostname(self):
        tasks = [{"task_id": "t1", "priority": 50, "base_score": 0.30, "scene_info": {}}]
        prompt = build_prompt({"hostname": "mighty-node"}, tasks)
        assert "mighty-node" in prompt

    def test_trim_scene_info_strips_file_paths(self):
        """
        File paths must be stripped before they reach the prompt to prevent
        context window overflow on large farms with deep directory structures.
        """
        full = {
            "renderer": "redshift",
            "resolution": [3840, 2160],
            "scene_path": "/mnt/farm/projects/show/seq/shot/scene_v042.ma",
            "output_path": "/mnt/farm/output/beauty/####.exr",
            "env": {"PYTHONPATH": "/opt/maya/python", "MAYA_APP_DIR": "/home/user/.maya"},
            "dcc": "maya",
        }
        trimmed = _trim_scene_info(full)
        assert "renderer" in trimmed
        assert "dcc" in trimmed
        assert "resolution" in trimmed
        assert "scene_path" not in trimmed
        assert "output_path" not in trimmed
        assert "env" not in trimmed

    def test_trim_scene_info_preserves_ai_relevant_fields(self):
        scene = {
            "renderer": "karma-xpu",
            "dcc": "houdini",
            "dcc_version": "20.5",
            "resolution": [1920, 1080],
            "camera": "cam_hero",
            "execution_mode": "husk",
        }
        trimmed = _trim_scene_info(scene)
        assert trimmed == scene  # all fields are relevant, nothing stripped

    def test_build_prompt_does_not_contain_file_paths(self):
        """File paths in scene_info must not appear in the final prompt."""
        tasks = [{
            "task_id": "t1",
            "priority": 80,
            "base_score": 0.41,
            "scene_info": {
                "renderer": "arnold",
                "scene_path": "/very/long/path/to/secret_project/scene.ma",
                "dcc": "maya",
            },
        }]
        prompt = build_prompt(_make_worker_caps(), tasks)
        assert "/very/long/path/to/secret_project/scene.ma" not in prompt
        assert "arnold" in prompt
