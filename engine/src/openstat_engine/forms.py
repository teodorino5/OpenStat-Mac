"""Declarative form model and type-aware variable picker eligibility logic."""

from dataclasses import dataclass, field
from typing import Any

from .errors import EngineError
from .model import Field


@dataclass(frozen=True)
class VariableSlot:
    id: str
    label: str
    required: bool = True
    multiple: bool = False
    min_items: int = 1
    max_items: int | None = 1
    allowed_measurements: tuple[str, ...] = ("continuous", "discrete")
    allowed_storage: tuple[str, ...] | None = None
    allowed_roles: tuple[str, ...] = ("characteristic",)

    def check_eligibility(self, field_def: Field) -> tuple[bool, str | None]:
        if field_def.role not in self.allowed_roles:
            return (
                False,
                f"ineligible_role: {field_def.role} is not in {self.allowed_roles}",
            )
        if field_def.measurement not in self.allowed_measurements:
            return (
                False,
                (
                    f"ineligible_measurement: {field_def.measurement} "
                    f"not in {self.allowed_measurements}"
                ),
            )
        if (
            self.allowed_storage is not None
            and field_def.storage not in self.allowed_storage
        ):
            return (
                False,
                f"ineligible_storage: {field_def.storage} is not in {self.allowed_storage}",
            )
        return True, None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "required": self.required,
            "multiple": self.multiple,
            "min_items": self.min_items,
            "max_items": self.max_items,
            "allowed_measurements": list(self.allowed_measurements),
            "allowed_storage": (
                list(self.allowed_storage) if self.allowed_storage is not None else None
            ),
            "allowed_roles": list(self.allowed_roles),
        }


@dataclass(frozen=True)
class FormModel:
    id: str
    title: str
    slots: tuple[VariableSlot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "slots": [slot.to_dict() for slot in self.slots],
        }

    def slot_map(self) -> dict[str, VariableSlot]:
        return {slot.id: slot for slot in self.slots}

    def evaluate_eligibility(
        self, fields: list[Field]
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Returns {field_id: {slot_id: {"eligible": bool, "reason": str | None}}}."""
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for f in fields:
            result[f.id] = {}
            for slot in self.slots:
                eligible, reason = slot.check_eligibility(f)
                result[f.id][slot.id] = {
                    "eligible": eligible,
                    "reason": reason,
                }
        return result

    def validate_assignments(
        self, fields: list[Field], assignments: dict[str, list[str]]
    ) -> dict[str, Any]:
        fields_by_id = {f.id: f for f in fields}
        errors: list[str] = []
        assigned_all: list[str] = []

        slot_dict = self.slot_map()

        for slot_id in assignments:
            if slot_id not in slot_dict:
                errors.append(f"unknown_slot: {slot_id}")

        for slot in self.slots:
            assigned = assignments.get(slot.id, [])
            if slot.required and len(assigned) < slot.min_items:
                errors.append(
                    f"missing_required_slot: {slot.id} requires min {slot.min_items}"
                )
            if slot.max_items is not None and len(assigned) > slot.max_items:
                errors.append(
                    f"slot_capacity_exceeded: {slot.id} allows at most {slot.max_items} variable(s)"
                )

            for field_id in assigned:
                if field_id not in fields_by_id:
                    errors.append(f"unknown_variable: {field_id}")
                    continue
                f = fields_by_id[field_id]
                eligible, reason = slot.check_eligibility(f)
                if not eligible:
                    errors.append(f"ineligible_variable: {field_id} for slot {slot.id} ({reason})")
                if field_id in assigned_all:
                    errors.append(f"duplicate_assignment: {field_id}")
                else:
                    assigned_all.append(field_id)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "assignments": assignments,
        }


DEFAULT_FORMS: tuple[FormModel, ...] = (
    FormModel(
        id="descriptives",
        title="Descriptive Statistics",
        slots=(
            VariableSlot(
                id="variables",
                label="Variables",
                required=True,
                multiple=True,
                min_items=1,
                max_items=None,
                allowed_measurements=("continuous", "discrete"),
                allowed_roles=("characteristic",),
            ),
            VariableSlot(
                id="split_by",
                label="Split By",
                required=False,
                multiple=False,
                min_items=0,
                max_items=1,
                allowed_measurements=("nominal", "ordinal", "binary"),
                allowed_roles=("characteristic",),
            ),
        ),
    ),
    FormModel(
        id="frequencies",
        title="Frequencies",
        slots=(
            VariableSlot(
                id="variables",
                label="Variables",
                required=True,
                multiple=True,
                min_items=1,
                max_items=None,
                allowed_measurements=("nominal", "ordinal", "binary", "discrete"),
                allowed_roles=("characteristic",),
            ),
        ),
    ),
    FormModel(
        id="ttest_ind",
        title="Independent Samples T-Test",
        slots=(
            VariableSlot(
                id="dependent",
                label="Dependent Variable",
                required=True,
                multiple=False,
                min_items=1,
                max_items=1,
                allowed_measurements=("continuous", "discrete"),
                allowed_roles=("characteristic",),
            ),
            VariableSlot(
                id="grouping",
                label="Grouping Variable",
                required=True,
                multiple=False,
                min_items=1,
                max_items=1,
                allowed_measurements=("nominal", "ordinal", "binary"),
                allowed_roles=("characteristic",),
            ),
        ),
    ),
    FormModel(
        id="ttest_rel",
        title="Paired Samples T-Test",
        slots=(
            VariableSlot(
                id="variable1",
                label="Variable 1",
                required=True,
                multiple=False,
                min_items=1,
                max_items=1,
                allowed_measurements=("continuous", "discrete"),
                allowed_roles=("characteristic",),
            ),
            VariableSlot(
                id="variable2",
                label="Variable 2",
                required=True,
                multiple=False,
                min_items=1,
                max_items=1,
                allowed_measurements=("continuous", "discrete"),
                allowed_roles=("characteristic",),
            ),
        ),
    ),
    FormModel(
        id="contingency",
        title="Contingency Table",
        slots=(
            VariableSlot(
                id="row_variable",
                label="Row Variable",
                required=True,
                multiple=False,
                min_items=1,
                max_items=1,
                allowed_measurements=("nominal", "ordinal", "binary", "discrete"),
                allowed_roles=("characteristic",),
            ),
            VariableSlot(
                id="column_variable",
                label="Column Variable",
                required=True,
                multiple=False,
                min_items=1,
                max_items=1,
                allowed_measurements=("nominal", "ordinal", "binary", "discrete"),
                allowed_roles=("characteristic",),
            ),
        ),
    ),
)


class FormRegistry:
    def __init__(self, forms: tuple[FormModel, ...] = DEFAULT_FORMS) -> None:
        self._forms = {form.id: form for form in forms}

    def list_forms(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self._forms.values()]

    def get_form(self, form_id: str) -> FormModel:
        if form_id not in self._forms:
            raise EngineError("error.rpc_method")
        return self._forms[form_id]


@dataclass
class PickerSession:
    """Keyboard-accessible state machine for variable picker forms."""

    form: FormModel
    fields: list[Field]
    candidates: list[str] = field(default_factory=list)
    selected_candidate_index: int = 0
    assignments: dict[str, list[str]] = field(default_factory=dict)
    focused_slot_id: str | None = None
    auto_populate: bool = True

    def __post_init__(self) -> None:
        if self.auto_populate and not self.candidates and not self.assignments:
            self.candidates = [f.id for f in self.fields]
        for slot in self.form.slots:
            self.assignments.setdefault(slot.id, [])
        if self.form.slots and self.focused_slot_id is None:
            self.focused_slot_id = self.form.slots[0].id

    @property
    def selected_candidate_id(self) -> str | None:
        if 0 <= self.selected_candidate_index < len(self.candidates):
            return self.candidates[self.selected_candidate_index]
        return None

    def keyboard_next_candidate(self) -> str | None:
        if self.candidates:
            self.selected_candidate_index = (
                self.selected_candidate_index + 1
            ) % len(self.candidates)
            return self.selected_candidate_id
        return None

    def keyboard_prev_candidate(self) -> str | None:
        if self.candidates:
            self.selected_candidate_index = (
                self.selected_candidate_index - 1
            ) % len(self.candidates)
            return self.selected_candidate_id
        return None

    def keyboard_select_candidate(self, field_id: str) -> None:
        if field_id in self.candidates:
            self.selected_candidate_index = self.candidates.index(field_id)

    def keyboard_focus_slot(self, slot_id: str) -> None:
        if slot_id in self.form.slot_map():
            self.focused_slot_id = slot_id

    def keyboard_assign(self, slot_id: str | None = None) -> tuple[bool, str | None]:
        target_slot_id = slot_id or self.focused_slot_id
        if not target_slot_id:
            return False, "no_focused_slot"
        slot = self.form.slot_map().get(target_slot_id)
        if not slot:
            return False, f"unknown_slot: {target_slot_id}"

        cand_id = self.selected_candidate_id
        if not cand_id:
            return False, "no_candidate_selected"

        field_map = {f.id: f for f in self.fields}
        field_def = field_map[cand_id]

        eligible, reason = slot.check_eligibility(field_def)
        if not eligible:
            return False, reason

        current_assigned = self.assignments[target_slot_id]
        if slot.max_items is not None and len(current_assigned) >= slot.max_items:
            return False, f"slot_capacity_exceeded: max {slot.max_items}"

        self.candidates.remove(cand_id)
        current_assigned.append(cand_id)
        if self.selected_candidate_index >= len(self.candidates):
            self.selected_candidate_index = max(0, len(self.candidates) - 1)
        return True, None

    def keyboard_remove(
        self, slot_id: str, field_id: str
    ) -> tuple[bool, str | None]:
        if slot_id not in self.assignments:
            return False, f"unknown_slot: {slot_id}"
        assigned = self.assignments[slot_id]
        if field_id not in assigned:
            return False, f"not_in_slot: {field_id}"

        assigned.remove(field_id)
        self.candidates.append(field_id)
        return True, None

    def validate(self) -> dict[str, Any]:
        return self.form.validate_assignments(self.fields, self.assignments)

    def state(self) -> dict[str, Any]:
        return {
            "form_id": self.form.id,
            "candidates": list(self.candidates),
            "selected_candidate_id": self.selected_candidate_id,
            "focused_slot_id": self.focused_slot_id,
            "assignments": {k: list(v) for k, v in self.assignments.items()},
            "valid": self.validate()["valid"],
        }
