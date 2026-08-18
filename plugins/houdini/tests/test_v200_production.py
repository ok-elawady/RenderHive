from pathlib import Path
import hashlib
import re
import sys
import uuid

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "payload" / "python_libs"
sys.path.insert(0, str(LIB))

from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.api.config import DEFAULT_CONFIG, normalize_config
from renderhive_houdini.api.contract import SUBMITTER_ENDPOINTS, WORKER_OWNED_ENDPOINTS
from renderhive_houdini.api.endpoints import DEFAULT_ENDPOINTS
from renderhive_houdini.api.models import normalize_worker, worker_meets_requirements
from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.core.task_builder import build_api_request, build_task
from renderhive_houdini.version import __version__

CONTRACT = ROOT / "contracts" / "renderhive_api_0_2_0.yaml"
EXPECTED_CONTRACT_SHA256 = "b77bdeb330bb15cf73fe37f659b67187989d6134f5757cf678acd6f22723172d"


def _context():
    return SceneContext(
        hip_path="P:/show/shot/lighting_v012.hip",
        hip_name="lighting_v012.hip",
        houdini_version="20.5.278",
        frame_start=1,
        frame_end=10,
        current_frame=1,
        fps=24,
        hip_directory="P:/show/shot",
        job_directory="P:/show",
        is_new_file=False,
        has_unsaved_changes=False,
        scene_name="lighting_v012",
        project_name="show",
        project_path="P:/show",
        output_root="P:/show/render",
    )


def _node(path, name, renderer="Karma CPU", mode="husk", output=""):
    return RenderNodeInfo(
        path=path,
        name=name,
        type_name="usdrender_rop" if mode == "husk" else "ifd",
        type_label="USD Render ROP" if mode == "husk" else "ROP",
        category="Driver",
        renderer=renderer,
        execution_mode=mode,
        frame_start=1,
        frame_end=10,
        frame_step=1,
        frame_source="Render Node",
        camera="/stage/cam1" if mode == "husk" else "/obj/cam1",
        output_path=output or "P:/show/render/{}/beauty.$F4.exr".format(name),
        resolution_width=1920,
        resolution_height=1080,
        is_bypassed=False,
        is_locked=False,
        is_renderable=True,
        usd_output_path="P:/show/usd/{}.usd".format(name) if mode == "husk" else "",
    )


def _canonical(path):
    path = str(path or "").split("?", 1)[0]
    return re.sub(r"\{[^}]+\}", "{}", path)


def _spec():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def test_release_version_is_production_v200():
    assert __version__ == "2.0.5"
    assert '"version": "2.0.5"' in (ROOT / "payload" / "config" / "defaults.json").read_text(encoding="utf-8")
    assert '"RENDERHIVE_HOUDINI_VERSION": "2.0.5"' in (ROOT / "package" / "renderhive.json.template").read_text(encoding="utf-8")


def test_embedded_openapi_is_exact_api_020_contract():
    digest = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    assert digest == EXPECTED_CONTRACT_SHA256
    spec = _spec()
    assert str((spec.get("info") or {}).get("version")) == "0.2.0"


def test_all_submitter_endpoints_exist_in_openapi_with_methods():
    paths = _spec().get("paths") or {}
    for name, definition in SUBMITTER_ENDPOINTS.items():
        configured = DEFAULT_ENDPOINTS[name]
        assert _canonical(configured) == _canonical(definition["path"])
        spec_path = next((p for p in paths if _canonical(p) == _canonical(definition["path"])), None)
        assert spec_path, name
        required = set(definition.get("methods") or (definition.get("method", "GET"),))
        available = {method.upper() for method in paths[spec_path] if method.lower() in {"get", "post", "put", "patch", "delete"}}
        assert {m.upper() for m in required}.issubset(available), name


def test_worker_owned_endpoints_exist_in_openapi():
    paths = _spec().get("paths") or {}
    for expected, method in WORKER_OWNED_ENDPOINTS.items():
        spec_path = next((p for p in paths if _canonical(p) == _canonical(expected)), None)
        assert spec_path, expected
        assert method.lower() in paths[spec_path], expected


def test_multi_render_sources_become_exactly_multiple_backend_layers():
    nodes = [
        _node("/stage/usdrender_char", "Characters"),
        _node("/stage/usdrender_env", "Environment"),
    ]
    task = build_task(
        _context(), nodes[0], "shot010", "show", chunk_size=3,
        concurrent_tasks=2, render_nodes=nodes,
        min_cores=8, min_memory_mb=16384, min_gpus=0,
    )
    payload = build_api_request(task, normalize_config({}))
    assert len(payload["layers"]) == 2
    assert [layer["name"] for layer in payload["layers"]] == ["Characters", "Environment"]
    assert [layer["scene_info"]["render_node"] for layer in payload["layers"]] == [
        "/stage/usdrender_char", "/stage/usdrender_env"
    ]
    assert all("renderhive_houdini.worker.render_rop" in layer["command"] for layer in payload["layers"])
    assert all("--node" in layer["command"] for layer in payload["layers"])
    assert all(layer["chunk_size"] == 3 for layer in payload["layers"])
    assert payload["max_tasks_per_worker"] == 2


def test_api_job_payload_validates_against_exact_openapi_jobcreate_schema():
    pool_id = str(uuid.UUID("11111111-1111-4111-8111-111111111111"))
    dep_id = str(uuid.UUID("22222222-2222-4222-8222-222222222222"))
    node = _node("/stage/usdrender1", "beauty", renderer="Karma XPU")
    task = build_task(
        _context(), node, "shot010", "show", chunk_size=2, concurrent_tasks=1,
        pool_targeting={
            "strategy": "selected_only",
            "selected_pool_ids": [pool_id],
            "effective_pool_ids": [pool_id],
            "effective_pool_names": ["GPU"],
        },
        dependencies=[dep_id], render_nodes=[node], min_gpus=0,
    )
    payload = build_api_request(task, normalize_config({}))
    validation_schema = {"$ref": "#/components/schemas/JobCreate", "components": _spec()["components"]}
    jsonschema.validate(payload, validation_schema, format_checker=jsonschema.FormatChecker())
    assert payload["included_pools"] == [pool_id]
    assert payload["excluded_pools"] == []
    assert payload["dependencies"] == [{"type": "JOB_ON_JOB", "parent_job": dep_id}]
    assert payload["layers"][0]["min_gpus"] >= 1
    assert "start_suspended" not in payload
    assert "machine_limit" not in payload
    assert "max_frames_per_worker" not in payload


def test_all_except_selected_maps_to_backend_excluded_pools():
    pool_id = "33333333-3333-4333-8333-333333333333"
    node = _node("/out/arnold1", "arnold1", renderer="Arnold", mode="hython")
    task = build_task(
        _context(), node, "arnold", "show", render_nodes=[node],
        pool_targeting={"strategy": "all_except_selected", "excluded_pool_ids": [pool_id]},
    )
    payload = build_api_request(task, normalize_config({}))
    assert payload["included_pools"] == []
    assert payload["excluded_pools"] == [pool_id]


def test_worker_hardware_eligibility_matches_cpu_ram_gpu_requirements():
    worker = normalize_worker({
        "id": "w1", "hostname": "node01", "status": "ONLINE",
        "cores": 24, "memory_mb": 65536, "gpu_models": ["RTX A5000"],
    })
    assert worker_meets_requirements(worker, 16, 32768, 1)
    assert not worker_meets_requirements(worker, 32, 32768, 1)
    assert not worker_meets_requirements(worker, 16, 131072, 1)
    assert not worker_meets_requirements(worker, 16, 32768, 2)


def test_progress_markers_exist_for_hython_and_husk_paths():
    rop = (LIB / "renderhive_houdini" / "worker" / "render_rop.py").read_text(encoding="utf-8")
    husk = (LIB / "renderhive_houdini" / "worker" / "render_husk.py").read_text(encoding="utf-8")
    for text in (rop, husk):
        assert "RENDERHIVE_FRAME_START" in text
        assert "RENDERHIVE_FRAME_DONE" in text


def test_artist_ui_uses_clean_surfaces_for_sources_dependencies_and_pools():
    theme = (LIB / "renderhive_houdini" / "ui" / "theme.py").read_text(encoding="utf-8")
    render_page = (LIB / "renderhive_houdini" / "ui" / "pages" / "render_page.py").read_text(encoding="utf-8")
    job_page = (LIB / "renderhive_houdini" / "ui" / "pages" / "job_page.py").read_text(encoding="utf-8")
    deps = (LIB / "renderhive_houdini" / "ui" / "job_dependency_widgets.py").read_text(encoding="utf-8")
    assert "QTreeWidget#RenderLayerTree" in theme
    assert "QTreeWidget#JobDependencyTree" in theme
    assert "background-color: %(surface2)s" in theme
    assert "check_mark.png" in theme
    assert 'setObjectName("RenderLayerTree")' in render_page
    assert 'setObjectName("RenderLayerTree")' in job_page
    assert 'setObjectName("JobDependencyTree")' in deps
    assert 'setObjectName("SecondaryText")' in job_page
    assert 'setObjectName("InlineFieldContainer")' in job_page


def test_production_ui_has_maya_parity_features_without_removed_fake_controls():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            LIB / "renderhive_houdini" / "ui" / "pages" / "job_page.py",
            LIB / "renderhive_houdini" / "ui" / "pages" / "render_page.py",
            LIB / "renderhive_houdini" / "ui" / "pages" / "validation_page.py",
            LIB / "renderhive_houdini" / "ui" / "main_window.py",
        ]
    )
    for required in (
        "Chunk Size", "Tasks per Worker", "Minimum CPU Cores", "Minimum RAM", "Minimum GPUs",
        "All Pools", "Selected Pools Only", "All Except Selected", "Retry Attempts", "Task Timeout",
        "Job Dependencies", "Browse Jobs", "Render Sources", "Validation", "Submit Job",
    ):
        assert required in text
    for removed in ("Start Suspended", "Machine Limit", "Allowed Workers", "Denied Workers"):
        assert removed not in text


def test_multi_source_selection_survives_single_validation_autofix_path():
    main = (LIB / "renderhive_houdini" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'render_state.get("selected_render_node_paths")' in main
    assert "self._restore_render_nodes(selected_paths, primary_path, render_state)" in main


def test_karma_xpu_farm_validation_requires_real_gpu_even_when_ui_minimum_is_any():
    from renderhive_houdini.validation.farm_checks import run as run_farm_checks
    gpu_worker = normalize_worker({
        "id": "gpu", "hostname": "gpu01", "status": "ONLINE", "cores": 16,
        "memory_mb": 32768, "gpu_models": ["RTX 4090"],
        "system_info": {"capabilities": {"houdini": {"versions": ["20.5.278"], "execution_modes": ["husk"]}}},
    })
    cpu_worker = normalize_worker({
        "id": "cpu", "hostname": "cpu01", "status": "ONLINE", "cores": 16,
        "memory_mb": 32768, "gpu_models": [],
        "system_info": {"capabilities": {"houdini": {"versions": ["20.5.278"], "execution_modes": ["husk"]}}},
    })
    node = _node("/stage/xpu", "xpu", renderer="Karma XPU")
    common = {
        "backend_online": True, "pools": [], "pool_strategy": "all", "effective_pool_ids": [],
        "min_cores": 0, "min_memory_mb": 0, "min_gpus": 0, "render_nodes": [node],
    }
    failed = run_farm_checks(_context(), node, dict(common, workers=[cpu_worker]))
    assert any(item.code == "FARM_SOURCE_NO_ELIGIBLE_WORKER" for item in failed)
    passed = run_farm_checks(_context(), node, dict(common, workers=[gpu_worker]))
    assert any(item.code == "FARM_WORKERS_ELIGIBLE" for item in passed)
