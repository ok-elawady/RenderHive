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


class ValidationEngine:
    """
    Central RenderHive validation engine.

    Every validation module must contain:
        run_checks(context)

    The function must return a list of result dictionaries.
    """

    def __init__(self, context=None):
        self.context = context or {}
        self.results = []

    def run(self):
        self.results = []

        for module in CHECK_MODULES:
            try:
                module_results = module.run_checks(self.context)

                if module_results:
                    self.results.extend(module_results)

            except Exception as error:
                self.results.append({
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
