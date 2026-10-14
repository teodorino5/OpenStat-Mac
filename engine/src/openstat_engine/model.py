"""Storage and measurement metadata are deliberately independent."""

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from .errors import EngineError

STORAGE_TYPES = {"float64", "int64", "string", "bool", "multiple_response"}
MEASUREMENTS = {"continuous", "discrete", "ordinal", "binary", "nominal", "multiple_response"}
CONTEXTS = {"sample", "population", "unspecified"}
ROLES = {"identifier", "characteristic"}


@dataclass(frozen=True)
class Field:
    id: str
    name: str
    storage: str
    measurement: str
    role: str = "characteristic"
    levels: tuple[str, ...] = ()
    value_labels: dict[str, str] = field(default_factory=dict)
    missing_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.name.strip() or self.name.startswith("_openstat_"):
            raise EngineError("error.field_name")
        if self.storage not in STORAGE_TYPES or self.measurement not in MEASUREMENTS:
            raise EngineError("error.field_type")
        if self.role not in ROLES:
            raise EngineError("error.field_role")
        if self.measurement in {"continuous", "discrete"} and self.storage not in {
            "float64",
            "int64",
        }:
            raise EngineError("error.incompatible_measurement")
        if (self.storage == "multiple_response") != (self.measurement == "multiple_response"):
            raise EngineError("error.incompatible_measurement")
        if len(set(self.levels)) != len(self.levels):
            raise EngineError("error.duplicate_levels")
        if self.measurement == "binary" and self.storage != "bool" and len(self.levels) != 2:
            raise EngineError("error.binary_levels")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Field":
        return cls(
            id=str(value.get("id", uuid4())),
            name=str(value["name"]),
            storage=str(value["storage"]),
            measurement=str(value["measurement"]),
            role=str(value.get("role", "characteristic")),
            levels=tuple(str(v) for v in value.get("levels", [])),
            value_labels={str(k): str(v) for k, v in value.get("value_labels", {}).items()},
            missing_codes=tuple(str(v) for v in value.get("missing_codes", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["levels"] = list(self.levels)
        result["missing_codes"] = list(self.missing_codes)
        return result


def validate_context(context: str) -> None:
    if context not in CONTEXTS:
        raise EngineError("error.context")


def validate_fields(fields: tuple[Field, ...]) -> None:
    if any(f.id.startswith("_openstat_") for f in fields):
        raise EngineError("error.field_name")
    if not fields or len({f.id for f in fields}) != len(fields):
        raise EngineError("error.duplicate_fields")
    if len({f.name for f in fields}) != len(fields):
        raise EngineError("error.duplicate_fields")
