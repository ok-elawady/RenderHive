from types import SimpleNamespace

from apps.workers.capabilities import versions_compatible, worker_supports_layer


def _worker(capabilities, tags=None, gpu_models=None):
    return SimpleNamespace(
        system_info={"capabilities": capabilities},
        tags=tags or [],
        gpu_models=gpu_models or [],
    )


def _layer(
    *,
    dcc,
    version,
    execution_mode="",
    renderer="",
    scene_path="",
):
    scene_info = {
        "dcc": dcc,
        "renderer": renderer,
        "execution": {"mode": execution_mode},
    }
    if dcc == "houdini":
        scene_info["houdini_version"] = version
    else:
        scene_info["maya_version"] = version
    return SimpleNamespace(
        scene_info=scene_info,
        env={},
        tags=[],
        command="",
        scene_path=scene_path,
    )


def test_houdini_builds_are_compatible_within_major_minor():
    assert versions_compatible("houdini", "20.5.278", ["20.5.410"])
    assert not versions_compatible("houdini", "20.5.278", ["21.0.440"])


def test_maya_versions_match_by_release_year():
    assert versions_compatible("maya", "2023.2", ["2023"])
    assert not versions_compatible("maya", "2023", ["2025"])


def test_houdini_husk_task_requires_husk_capability():
    worker = _worker(
        {
            "houdini": {
                "available": True,
                "versions": ["20.5.278"],
                "execution_modes": ["hython"],
            }
        },
        tags=["dcc:houdini", "houdini:20.5.278", "houdini:hython"],
    )
    compatible, reason = worker_supports_layer(
        worker,
        _layer(
            dcc="houdini",
            version="20.5.278",
            execution_mode="husk",
            renderer="Karma XPU",
            scene_path="P:/shot/test.hip",
        ),
    )
    assert compatible is False
    assert "execution mode" in reason


def test_houdini_build_compatible_worker_is_accepted():
    worker = _worker(
        {
            "houdini": {
                "available": True,
                "versions": ["20.5.410"],
                "execution_modes": ["hython", "husk"],
            }
        },
        tags=["dcc:houdini", "houdini:20.5.410", "houdini:hython", "houdini:husk"],
    )
    compatible, _reason = worker_supports_layer(
        worker,
        _layer(
            dcc="houdini",
            version="20.5.278",
            execution_mode="hython",
            renderer="Karma CPU",
            scene_path="P:/shot/test.hip",
        ),
    )
    assert compatible is True


def test_maya_only_worker_cannot_claim_houdini_task():
    worker = _worker(
        {"maya": {"available": True, "versions": ["2023"]}},
        tags=["dcc:maya", "maya:2023"],
    )
    compatible, reason = worker_supports_layer(
        worker,
        _layer(
            dcc="houdini",
            version="20.5.278",
            execution_mode="hython",
            scene_path="P:/shot/test.hip",
        ),
    )
    assert compatible is False
    assert "houdini" in reason.lower()


def test_renderer_filter_is_strict_when_worker_advertises_renderers():
    worker = _worker(
        {
            "houdini": {
                "available": True,
                "versions": ["20.5.278"],
                "execution_modes": ["hython"],
                "renderers": ["karma-cpu"],
            }
        },
        tags=["dcc:houdini", "houdini:20.5.278", "houdini:hython"],
    )
    compatible, reason = worker_supports_layer(
        worker,
        _layer(
            dcc="houdini",
            version="20.5.278",
            execution_mode="hython",
            renderer="Redshift",
            scene_path="P:/shot/test.hip",
        ),
    )
    assert compatible is False
    assert "renderer" in reason
