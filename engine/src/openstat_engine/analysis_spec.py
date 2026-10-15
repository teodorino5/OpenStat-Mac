"""Declarative, versioned analysis specifications with revision hashing and conventions."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .errors import EngineError
from .store import Store

CURRENT_SCHEMA_VERSION = 1
SUPPORTED_ANALYSES = {
    "descriptives",
    "frequencies",
    "ttest_ind",
    "ttest_rel",
    "contingency",
    "outliers",
}
VALID_MISSING_STRATEGIES = {"exclude_listwise", "exclude_pairwise", "treat_as_category"}
VALID_ALTERNATIVES = {"two-sided", "less", "greater"}


@dataclass(frozen=True)
class StatisticalConventions:
    missing_strategy: str = "exclude_listwise"
    confidence_level: float = 0.95
    p_value_threshold: float = 0.05
    degrees_of_freedom_adjustment: int = 1
    rounding_precision: int = 4

    def validate(self) -> None:
        if self.missing_strategy not in VALID_MISSING_STRATEGIES:
            raise EngineError("error.operation_options")
        if not (0.0 < self.confidence_level < 1.0):
            raise EngineError("error.operation_options")
        if not (0.0 < self.p_value_threshold < 1.0):
            raise EngineError("error.operation_options")
        if self.degrees_of_freedom_adjustment not in (0, 1):
            raise EngineError("error.operation_options")
        if not (0 <= self.rounding_precision <= 15):
            raise EngineError("error.operation_options")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisSpecification:
    analysis_id: str
    dataset_id: str
    dataset_revision: str
    variables: dict[str, list[str]]
    options: dict[str, Any] = field(default_factory=dict)
    conventions: StatisticalConventions = field(default_factory=StatisticalConventions)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise EngineError("error.project_version")
        if self.analysis_id not in SUPPORTED_ANALYSES:
            raise EngineError("error.rpc_method")
        if not self.dataset_id or not self.dataset_revision:
            raise EngineError("error.field_name")
        self.conventions.validate()

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_id": self.analysis_id,
            "dataset_id": self.dataset_id,
            "dataset_revision": self.dataset_revision,
            "variables": {k: sorted(v) for k, v in sorted(self.variables.items())},
            "options": {k: self.options[k] for k in sorted(self.options.keys())},
            "conventions": self.conventions.to_dict(),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        payload = self.canonical_json().encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        data = self.canonical_dict()
        data["digest"] = self.digest()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisSpecification":
        conv_raw = data.get("conventions", {})
        conventions = StatisticalConventions(
            missing_strategy=conv_raw.get("missing_strategy", "exclude_listwise"),
            confidence_level=float(conv_raw.get("confidence_level", 0.95)),
            p_value_threshold=float(conv_raw.get("p_value_threshold", 0.05)),
            degrees_of_freedom_adjustment=int(conv_raw.get("degrees_of_freedom_adjustment", 1)),
            rounding_precision=int(conv_raw.get("rounding_precision", 4)),
        )
        return cls(
            schema_version=int(data.get("schema_version", CURRENT_SCHEMA_VERSION)),
            analysis_id=str(data["analysis_id"]),
            dataset_id=str(data["dataset_id"]),
            dataset_revision=str(data["dataset_revision"]),
            variables={k: list(v) for k, v in data.get("variables", {}).items()},
            options=dict(data.get("options", {})),
            conventions=conventions,
        )

    def validate_against_store(self, store: Store) -> dict[str, Any]:
        """Validates that dataset revision exists and all referenced fields exist."""
        revision_info = store.get(self.dataset_revision)
        if revision_info.dataset_id != self.dataset_id:
            raise EngineError("error.operation_options")
        field_ids = {f.id for f in revision_info.fields}

        missing_fields: list[str] = []
        for slot_name, slot_fields in self.variables.items():
            for fid in slot_fields:
                if fid not in field_ids:
                    missing_fields.append(f"{slot_name}:{fid}")

        if missing_fields:
            raise EngineError("error.unknown_field")

        return {
            "valid": True,
            "digest": self.digest(),
            "analysis_id": self.analysis_id,
            "revision": self.dataset_revision,
            "field_count": len(revision_info.fields),
            "row_count": revision_info.row_count,
        }
