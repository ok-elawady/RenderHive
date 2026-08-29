from . import scene_checks
from . import naming_checks
from . import material_checks
from . import lighting_checks
from . import geometry_checks
from . import dependency_checks
from . import render_checks
from . import submission_checks


CHECK_MODULES = [
    scene_checks,
    naming_checks,
    material_checks,
    lighting_checks,
    geometry_checks,
    dependency_checks,
    render_checks,
    submission_checks,
]


RULE_PROFILES = {
    "standard": {
        "name": "Standard (Default)",
        "description": "Standard studio production rules. Critical scene and render issues block submission; advisory issues warn.",
        "overrides": {},
    },
    "studio_strict": {
        "name": "Studio Strict",
        "description": "Strict delivery profile. Unlinked textures, missing AOVs, and questionable camera clipping are treated as errors.",
        "overrides": {
            "TEXTURE_MISSING": "ERROR",
            "REQUIRED_AOV_MISSING": "ERROR",
            "AOV_DRIVER_MISSING": "ERROR",
            "CAMERA_CLIPPING_SUSPICIOUS": "ERROR",
            "NON_MANIFOLD_VERTICES": "ERROR",
            "NON_MANIFOLD_EDGES": "ERROR",
            "REFERENCE_MISSING": "ERROR",
            "CACHE_FILE_MISSING": "ERROR",
        },
    },
    "lookdev": {
        "name": "LookDev / Relaxed",
        "description": "Relaxes non-critical asset, texture, and scene checks to warnings during early look development.",
        "overrides": {
            "TEXTURE_MISSING": "WARNING",
            "REQUIRED_AOV_MISSING": "WARNING",
            "CAMERA_CLIPPING_SUSPICIOUS": "INFO",
            "NON_MANIFOLD_VERTICES": "INFO",
            "NON_MANIFOLD_EDGES": "INFO",
        },
    },
}


class ValidationEngine:
    """
    Central RenderHive validation engine with configurable rule severities.

    Every validation module must contain:
        run_checks(context)

    The function must return a list of result dictionaries.
    """

    def __init__(self, context=None, rule_overrides=None):
        self.context = context or {}
        self.rule_overrides = dict(rule_overrides or self.context.get("rule_overrides") or {})
        self.results = []

    def set_rule_overrides(self, overrides):
        self.rule_overrides = dict(overrides or {})

    def get_rule_severity(self, code, default="ERROR"):
        code = str(code or "").upper()
        return str(self.rule_overrides.get(code, default)).upper()

    def run(self):
        raw_results = []

        for module in CHECK_MODULES:
            try:
                module_results = module.run_checks(self.context)

                if module_results:
                    raw_results.extend(module_results)

            except Exception as error:
                raw_results.append({
                    "severity": "ERROR",
                    "category": "System",
                    "code": "VALIDATION_MODULE_FAILED",
                    "node": "",
                    "message": (
                        "Validation module '{}' failed: {}"
                    ).format(module.__name__, error),
                    "fixable": False,
                    "data": {}
                })

        # Apply user/profile rule severity overrides
        self.results = []
        for result in raw_results:
            code = str(result.get("code") or "").upper()
            override = self.rule_overrides.get(code)
            if override:
                override = str(override).upper()
                if override in ("DISABLED", "IGNORE", "OFF"):
                    continue
                if override in ("ERROR", "WARNING", "INFO", "PASSED"):
                    result = dict(result)
                    result["severity"] = override
                    result["original_severity"] = result.get("severity")

            self.results.append(result)

        return self.results

    def get_results(self, severity=None, category=None):
        results = self.results

        if severity:
            severity = severity.upper()
            results = [
                result for result in results
                if result.get("severity") == severity
            ]

        if category:
            results = [
                result for result in results
                if result.get("category") == category
            ]

        return results

    def has_errors(self):
        return any(
            result.get("severity") == "ERROR"
            for result in self.results
        )

    def summary(self):
        summary = {
            "ERROR": 0,
            "WARNING": 0,
            "INFO": 0,
            "PASSED": 0,
            "total": len(self.results),
            "valid": True,
        }

        for result in self.results:
            severity = result.get("severity", "INFO")

            if severity in summary:
                summary[severity] += 1

        summary["valid"] = summary["ERROR"] == 0

        return summary

    def to_dict(self):
        return {
            "summary": self.summary(),
            "results": self.results,
        }
