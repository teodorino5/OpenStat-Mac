import math
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from openstat_engine import outliers
from openstat_engine.errors import EngineError
from openstat_engine.store import Store, digest


def values(store: Store, revision: str) -> list[list[Any]]:
    result: list[list[Any]] = []
    for table in store.iter_tables(revision):
        columns = table.to_pydict()
        fields = [field.id for field in store.get(revision).fields]
        result.extend(
            [[columns[field][row] for field in fields] for row in range(table.num_rows)]
        )
    return result


@pytest.mark.feature("DATA-021")
def test_hand_calculated_outlier_contract(
    store: Store, reference_fixture: Callable[[str], dict[str, Any]]
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/outliers.json")
    source = store.create(**fixture["input"])
    original_hash = digest(store.get(source["revision"]).base)
    flagged = outliers.flag(store, source["revision"], "x", "Severity")
    expected = fixture["expected"]
    assert [row[-1] for row in values(store, flagged["revision"])] == expected["severity"]
    assert store.page(flagged["revision"])["row_ids"] == list(range(len(expected["severity"])))
    output_field = store.get(flagged["revision"]).fields[-1]
    assert (output_field.storage, output_field.measurement) == ("int64", "nominal")
    assert output_field.value_labels == {
        "0": "Not an outlier",
        "1": "Mild outlier",
        "2": "Extreme outlier",
    }
    assert store.page(source["revision"])["rows"] == fixture["input"]["rows"]
    assert digest(store.get(source["revision"]).base) == original_hash

    included = outliers.flag(
        store,
        source["revision"],
        "x",
        "Including coded missing",
        include_missing_codes=True,
    )
    assert [row[-1] for row in values(store, included["revision"])] == expected[
        "include_coded_missing_severity"
    ]


def test_zero_iqr_uses_strict_open_fences_and_keeps_negative_zero(store: Store) -> None:
    source = store.create(
        "Constant values",
        [{"id": "x", "name": "Value", "storage": "float64", "measurement": "continuous"}],
        [[-0.0], [0.0], [0.0]],
    )
    original_hash = digest(store.get(source["revision"]).base)
    result = outliers.flag(store, source["revision"], "x", "Flag")
    assert [row[0] for row in values(store, result["revision"])] == [-0.0, 0.0, 0.0]
    assert math.copysign(1.0, values(store, result["revision"])[0][0]) == -1.0
    assert [row[-1] for row in values(store, result["revision"])] == [0, 0, 0]
    assert digest(store.get(source["revision"]).base) == original_hash


def test_empty_and_all_missing_sources_emit_null_flags(store: Store) -> None:
    fields = [
        {"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete",
         "missing_codes": ["-999"]}
    ]
    all_missing = store.create("Missing", fields, [[None], [-999]])
    excluded = outliers.flag(store, all_missing["revision"], "x", "Excluded")
    assert [row[-1] for row in values(store, excluded["revision"])] == [None, None]
    included = outliers.flag(
        store, all_missing["revision"], "x", "Included", include_missing_codes=True
    )
    assert [row[-1] for row in values(store, included["revision"])] == [None, 0]

    empty = store.create("Empty", fields, [])
    result = outliers.flag(store, empty["revision"], "x", "Empty flag")
    assert values(store, result["revision"]) == []
    assert store.get(result["revision"]).row_count == 0


def test_int64_fences_preserve_values_near_both_limits(store: Store) -> None:
    minimum, maximum = -(2**63), 2**63 - 1
    for rows, outlier_index in [
        ([[maximum - 10], [maximum - 9], [maximum - 8], [maximum - 7], [maximum]], 4),
        ([[minimum], [minimum + 7], [minimum + 8], [minimum + 9], [minimum + 10]], 0),
    ]:
        source = store.create(
            "Int64 extremes",
            [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
            rows,
        )
        result = outliers.flag(store, source["revision"], "x", "Severity")
        output = values(store, result["revision"])
        expected = [0, 0, 0, 0, 2]
        if outlier_index == 0:
            expected = [2, 0, 0, 0, 0]
        assert [row[-1] for row in output] == expected
        assert output[outlier_index][-1] == 2
        assert [row[0] for row in output] == [row[0] for row in rows]


def test_finite_extreme_floats_do_not_overflow_fence_math(store: Store) -> None:
    source = store.create(
        "Wide finite values",
        [{"id": "x", "name": "Value", "storage": "float64", "measurement": "continuous"}],
        [[-1e308], [-1e308], [1e308], [1e308]],
    )
    result = outliers.flag(store, source["revision"], "x", "Severity")
    output = values(store, result["revision"])
    assert [row[-1] for row in output] == [0, 0, 0, 0]
    assert [row[0] for row in output] == [-1e308, -1e308, 1e308, 1e308]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"inner": -1},
        {"outer": -1},
        {"inner": 2, "outer": 1},
        {"inner": float("nan")},
        {"outer": float("inf")},
        {"inner": True},
        {"outer": "3"},
        {"include_missing_codes": 1},
        {"name": ""},
    ],
)
def test_invalid_outlier_options_reject_without_new_revision(
    store: Store, kwargs: dict[str, Any]
) -> None:
    source = store.create(
        "Options",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[1], [2]],
    )
    before_files = set(store.directory.iterdir())
    before_revisions = set(store.revisions)
    options: dict[str, Any] = {"inner": 1.5, "outer": 3.0, "include_missing_codes": False,
                               "name": "Severity"}
    options.update(kwargs)
    name = options.pop("name")
    with pytest.raises(EngineError, match="error.operation_options"):
        outliers.flag(store, source["revision"], "x", name, **options)
    assert set(store.directory.iterdir()) == before_files
    assert set(store.revisions) == before_revisions


def test_source_validation_and_duplicate_name_are_atomic(store: Store) -> None:
    numeric = store.create(
        "Numeric",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[1], [2]],
    )
    categorical = store.create(
        "Categorical",
        [{"id": "s", "name": "Text", "storage": "string", "measurement": "nominal"}],
        [["A"]],
    )
    before_files = set(store.directory.iterdir())
    with pytest.raises(EngineError, match="error.unknown_field"):
        outliers.flag(store, numeric["revision"], "missing", "Flag")
    with pytest.raises(EngineError, match="error.value_type"):
        outliers.flag(store, categorical["revision"], "s", "Flag")
    with pytest.raises(EngineError, match="error.duplicate_fields"):
        outliers.flag(store, numeric["revision"], "x", "Value")
    assert set(store.directory.iterdir()) == before_files


def test_global_limit_rejects_before_scanning(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = store.create(
        "Bounded scan",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[1]],
    )
    store.revisions[source["revision"]] = replace(
        store.get(source["revision"]), row_count=outliers.GLOBAL_LIMIT + 1
    )

    def no_scan(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Scan started before global row limit check")

    monkeypatch.setattr(store, "iter_tables", no_scan)
    with pytest.raises(EngineError, match="error.global_limit"):
        outliers.flag(store, source["revision"], "x", "Flag")


def test_sparse_edits_are_classified_and_source_ids_preserved(store: Store) -> None:
    source = store.create(
        "Editable values",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[1], [2], [3], [4], [5], [6], [7], [8], [9], [17], [100]],
    )
    edited = store.edit(source["revision"], 9, "x", 2)
    result = outliers.flag(store, edited["revision"], "x", "Severity")
    assert store.page(result["revision"])["row_ids"] == list(range(11))
    assert [row[-1] for row in values(store, result["revision"])] == [0] * 10 + [2]
    assert store.page(source["revision"])["rows"][9] == [17]
