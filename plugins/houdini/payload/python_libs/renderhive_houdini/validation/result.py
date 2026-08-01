"""Validation result data model."""

from __future__ import absolute_import

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    severity: str
    category: str
    message: str
    node_path: str = ""

    @property
    def blocks_submission(self):
        return self.severity.upper() == "ERROR"
