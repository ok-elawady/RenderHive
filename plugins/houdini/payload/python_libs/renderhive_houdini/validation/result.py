"""Validation result data model shared by UI, reports and Auto Fix."""

from __future__ import absolute_import

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    severity: str
    category: str
    message: str
    node_path: str = ""
    code: str = ""
    fixable: bool = False
    batch_safe: bool = False
    requires_confirmation: bool = False
    data: dict = field(default_factory=dict)

    @property
    def blocks_submission(self):
        return str(self.severity or "").upper() == "ERROR"

    @property
    def node(self):
        return self.node_path

    def as_dict(self):
        return {
            "severity": str(self.severity or "INFO").upper(),
            "category": str(self.category or "General"),
            "message": str(self.message or ""),
            "node": str(self.node_path or ""),
            "code": str(self.code or ""),
            "fixable": bool(self.fixable),
            "batch_safe": bool(self.batch_safe),
            "requires_confirmation": bool(self.requires_confirmation),
            "data": dict(self.data or {}),
        }
