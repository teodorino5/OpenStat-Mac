import json
import math
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from openstat_engine import columns
from openstat_engine.errors import EngineError
from openstat_engine.store import ROW_ID, Store


def values(store: Store, result: dict[str, Any]) -> list[Any]:
    page = store.page(result["revision"], fields=[result["fields"][-1]["id"]])
    return [row[0] for row in page["rows"]]


def dataset(store: Store, rows: list[list[Any]]) -> str:
    return store.create(
        "Test",
        [
            {
                "id": "x",
                "name": "Value",
                "storage": "float64",
                "measurement": "continuous",
                "missing_codes": ["-999.0"],
            }
        ],
        rows,
    )["revision"]  # type: ignore[no-any-return]


@pytest.mark.feature("DATA-010")
@pytest.mark.feature("DATA-011")
@pytest.mark.feature("DATA-022")
@pytest.mark.feature("DATA-023")
@pytest.mark.feature("DATA-024")
@pytest.mark.feature("DATA-026")
def test_original_columns_contract(
    store: Store,
    reference_fixture: Callable[[str], dict[str, Any]],
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/columns.json")
    item = store.create("Hand calculation", **fixture["input"])
    revision = item["revision"]
    expected = fixture["expected"]
    outcomes = {
        "recode": columns.recode(store, revision, "x", "Recode", [{"from": 4, "to": 40}]),
        "compute": columns.compute(
            store,
            revision,
            "Formula",
            {
                "op": "add",
                "args": [
                    {"op": "multiply", "args": [{"field": "x"}, {"constant": 2}]},
                    {"constant": 1},
                ],
            },
        ),
        "lag": columns.lag(store, revision, "x", "Lag"),
        "lead": columns.lag(store, revision, "x", "Lead", direction="lead"),
        "standardize_sample": columns.standardize(store, revision, "x", "Sample z", ddof=1),
        "standardize_population": columns.standardize(store, revision, "x", "Population z", ddof=0),
    }
    for ties in ("average", "min", "max", "dense", "first"):
        outcomes[f"rank_{ties}"] = columns.rank(store, revision, "x", "Rank", ties=ties)
    for keep in ("first", "last", "none"):
        outcomes[f"duplicates_{keep}"] = columns.duplicates(store, revision, ["x"], "Flag", keep)
    for key, result in outcomes.items():
        assert values(store, result) == pytest.approx(expected[key], abs=1e-12)
        assert result["id"] == item["id"]
        assert result["revision"] != revision
        assert store.page(result["revision"])["row_ids"] == list(range(6))
        assert store.page(result["revision"])["rows"] == [
            row + [derived]
            for row, derived in zip(fixture["input"]["rows"], values(store, result), strict=True)
        ]
    assert store.page(revision)["rows"] == fixture["input"]["rows"]


def test_overlay_materialized_and_roundtrip(store: Store, tmp_path: Path) -> None:
    original = dataset(store, [[1], [2], [3]])
    changed = store.edit(original, 1, "x", 20)["revision"]
    result = columns.compute(store, changed, "Copy", {"field": "x"})
    assert values(store, result) == [1, 20, 3]
    assert store.page(result["revision"])["rows"] == [[1, 1], [20, 20], [3, 3]]
    assert store.get(result["revision"]).edits == ()
    root = tmp_path / "derived.openstat"
    store.save(result["revision"], root)
    reopened = store.open(root)
    assert values(store, reopened) == [1, 20, 3]
    assert values(store, columns.compute(store, original, "Original copy", {"field": "x"})) == [
        1,
        2,
        3,
    ]


def test_stable_noncontiguous_ids_and_batch_boundary(store: Store) -> None:
    revision = dataset(store, [[i] for i in range(8200)])
    item = store.get(revision)
    table = pq.read_table(item.base)
    table = table.set_column(0, ROW_ID, pa.array(range(10, 16410, 2), type=pa.int64()))
    pq.write_table(table, item.base)
    result = columns.lag(store, revision, "x", "Lag", steps=2)
    derived = pq.read_table(store.get(result["revision"]).base)
    assert derived[ROW_ID].to_pylist() == list(range(10, 16410, 2))
    assert derived[result["fields"][-1]["id"]].to_pylist()[8190:8196] == list(range(8188, 8194))


@pytest.mark.parametrize("function", ["rank", "lag", "standardize"])
def test_global_memory_limit(store: Store, function: str) -> None:
    revision = dataset(store, [[1], [2]])
    store.revisions[revision] = replace(store.get(revision), row_count=columns.GLOBAL_LIMIT + 1)
    with pytest.raises(EngineError, match="error.global_limit"):
        getattr(columns, function)(store, revision, "x", "Too large")
    with pytest.raises(EngineError, match="error.global_limit"):
        columns.duplicates(store, revision, ["x"], "Too large")


def test_include_coded_missing_and_nulls(store: Store) -> None:
    revision = dataset(store, [[-999], [None], [2], [2], [None]])
    assert values(
        store, columns.rank(store, revision, "x", "Rank", include_missing_codes=True)
    ) == [1, None, 2.5, 2.5, None]
    assert values(store, columns.compute(store, revision, "Copy", {"field": "x"}, True)) == [
        -999,
        None,
        2,
        2,
        None,
    ]
    assert values(
        store,
        columns.recode(
            store, revision, "x", "Codes", [{"from": -999, "to": 0}], include_missing_codes=True
        ),
    ) == [0, None, 2, 2, None]
    assert values(store, columns.duplicates(store, revision, ["x"], "Repeated")) == [
        False,
        False,
        False,
        True,
        True,
    ]
    assert values(
        store, columns.lag(store, revision, "x", "Codes lag", include_missing_codes=True)
    ) == [None, -999, None, 2, 2]
    assert values(
        store, columns.rank(store, revision, "x", "Descending", ascending=False, ties="first")
    ) == [None, None, 1, 2, None]
    assert values(store, columns.lag(store, revision, "x", "Outside", steps=20)) == [None] * 5


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('touch bad')",
        {"constant": True},
        {"constant": "1"},
        {"constant": float("inf")},
        {"constant": 10**1000},
        {},
        {"op": "eval", "args": []},
        {"op": "add", "args": [{"constant": 1}]},
        {"field": "x", "extra": 1},
        {"op": [], "args": []},
        {"op": "add", "args": "bad"},
    ],
)
def test_reject_unsafe_expressions(store: Store, expression: Any) -> None:
    revision = dataset(store, [[1]])
    with pytest.raises(EngineError, match="error.expression"):
        columns.compute(store, revision, "Unsafe", expression)


def test_expression_depth_and_size(store: Store) -> None:
    revision = dataset(store, [[1]])
    expression: dict[str, Any] = {"constant": 1}
    for _ in range(18):
        expression = {"op": "abs", "args": [expression]}
    with pytest.raises(EngineError, match="error.expression"):
        columns.compute(store, revision, "Deep", expression)
    tree: dict[str, Any] = {"constant": 1}
    for _ in range(8):
        tree = {"op": "add", "args": [tree, tree]}
    with pytest.raises(EngineError, match="error.expression"):
        columns.compute(store, revision, "Wide", tree)


def test_expression_node_budget_and_preflight(store: Store) -> None:
    revision = dataset(store, [[1]])

    def balanced(depth: int) -> dict[str, Any]:
        if depth == 0:
            return {"constant": 1}
        return {"op": "add", "args": [balanced(depth - 1), balanced(depth - 1)]}

    # Full depth-seven binary tree has 255 nodes. One unary node makes 256.
    valid = {"op": "abs", "args": [balanced(7)]}
    assert values(store, columns.compute(store, revision, "Valid", valid)) == [128]

    # A second unary node makes 257 nodes. Reject before creating a Parquet file or revision.
    invalid = {"op": "abs", "args": [valid]}
    files = set(store.directory.iterdir())
    revisions = len(store.revisions)
    with pytest.raises(EngineError, match="error.expression"):
        columns.compute(store, revision, "Too many nodes", invalid)
    assert set(store.directory.iterdir()) == files
    assert len(store.revisions) == revisions


def test_expression_cycle_rejected_before_writing(store: Store) -> None:
    revision = dataset(store, [[1]])
    arguments: list[Any] = []
    expression: dict[str, Any] = {"op": "abs", "args": arguments}
    arguments.append(expression)
    files = set(store.directory.iterdir())
    with pytest.raises(EngineError, match="error.expression"):
        columns.compute(store, revision, "Cycle", expression)
    assert set(store.directory.iterdir()) == files
    assert len(store.revisions) == 1


def test_transform_checkpoint_cleans_partial_output(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = dataset(store, [[i] for i in range(columns.BATCH_SIZE + 1)])
    files = set(store.directory.iterdir())

    def cancel_after_first_batch(processed: int, total: int) -> None:
        assert total == columns.BATCH_SIZE + 1
        if processed == columns.BATCH_SIZE:
            raise EngineError("error.job_cancelled")

    monkeypatch.setattr(columns, "checkpoint", cancel_after_first_batch)
    with pytest.raises(EngineError, match="error.job_cancelled"):
        columns.compute(store, revision, "Cancelled", {"constant": 1})
    assert set(store.directory.iterdir()) == files
    assert len(store.revisions) == 1


@pytest.mark.parametrize(
    "op,value,expected",
    [
        ("sqrt", 4, 2),
        ("log", 1, 0),
        ("exp", 0, 1),
        ("abs", -3, 3),
        ("negate", 3, -3),
    ],
)
def test_unary_functions(store: Store, op: str, value: float, expected: float) -> None:
    revision = dataset(store, [[value]])
    assert values(
        store, columns.compute(store, revision, "Derived", {"op": op, "args": [{"field": "x"}]})
    ) == [expected]


@pytest.mark.parametrize(
    "expression,rows",
    [
        ({"op": "divide", "args": [{"constant": 1}, {"field": "x"}]}, [[0]]),
        ({"op": "sqrt", "args": [{"field": "x"}]}, [[-1]]),
        ({"op": "log", "args": [{"field": "x"}]}, [[0]]),
        ({"op": "exp", "args": [{"field": "x"}]}, [[1000]]),
        ({"op": "multiply", "args": [{"field": "x"}, {"constant": 1e308}]}, [[1e308]]),
    ],
)
def test_formula_domain_failure_atomic(
    store: Store, expression: dict[str, Any], rows: list[list[Any]]
) -> None:
    revision = dataset(store, rows)
    files = set(store.directory.iterdir())
    with pytest.raises(EngineError, match="error.transform_domain"):
        columns.compute(store, revision, "Bad", expression)
    assert set(store.directory.iterdir()) == files
    assert len(store.revisions) == 1


@pytest.mark.parametrize(
    "rows,ddof", [([], 0), ([[None]], 1), ([[1]], 1), ([[1], [1]], 0), ([[0], [0]], 1)]
)
def test_zero_variance_and_insufficient_data(
    store: Store, rows: list[list[Any]], ddof: int
) -> None:
    revision = dataset(store, rows)
    with pytest.raises(EngineError, match="error.zero_variance"):
        columns.standardize(store, revision, "x", "Z", ddof)


def test_standardize_extreme_finite(store: Store) -> None:
    revision = dataset(store, [[-1e308], [0], [1e308]])
    assert values(store, columns.standardize(store, revision, "x", "Z")) == pytest.approx(
        [-1, 0, 1]
    )
    assert values(store, columns.standardize(store, revision, "x", "Z0", 0)) == pytest.approx(
        [-math.sqrt(1.5), 0, math.sqrt(1.5)]
    )


def test_empty_operations(store: Store) -> None:
    revision = dataset(store, [])
    for outcome in [
        columns.rank(store, revision, "x", "Rank"),
        columns.compute(store, revision, "Formula", {"constant": 2}),
        columns.lag(store, revision, "x", "Lag"),
        columns.duplicates(store, revision, ["x"], "Duplicates"),
        columns.recode(store, revision, "x", "Recode", []),
    ]:
        assert values(store, outcome) == []


def test_recode_storage_and_missing_policy(store: Store) -> None:
    revision = dataset(store, [[1], [2], [None]])
    assert values(
        store,
        columns.recode(
            store,
            revision,
            "x",
            "String",
            [{"from": 1, "to": "one"}],
            unmatched="null",
            storage="string",
        ),
    ) == ["one", None, None]
    with pytest.raises(EngineError, match="error.value_type"):
        columns.recode(store, revision, "x", "Invalid keep", [], storage="string")


def test_categorical_lag_and_duplicates(store: Store) -> None:
    definition = {
        "id": "choices",
        "name": "Choices",
        "storage": "multiple_response",
        "measurement": "multiple_response",
        "levels": ["A", "B"],
    }
    revision = store.create(
        "Choices", [definition], [[["A", "B"]], [["A", "B"]], [["B", "A"]], [None]]
    )["revision"]
    assert values(store, columns.lag(store, revision, "choices", "Lag")) == [
        None,
        ["A", "B"],
        ["A", "B"],
        ["B", "A"],
    ]
    assert values(store, columns.duplicates(store, revision, ["choices"], "Flag")) == [
        False,
        True,
        False,
        False,
    ]
    with pytest.raises(EngineError, match="error.value_type"):
        columns.rank(store, revision, "choices", "Rank")
    with pytest.raises(EngineError, match="error.value_type"):
        columns.compute(store, revision, "Formula", {"field": "choices"})
    with pytest.raises(EngineError, match="error.unknown_field"):
        columns.rank(store, revision, "unknown", "Rank")


@pytest.mark.parametrize(
    "function,kwargs",
    [
        ("rank", {"ties": "random"}),
        ("rank", {"ascending": 1}),
        ("lag", {"steps": True}),
        ("lag", {"steps": 0}),
        ("lag", {"direction": "sideways"}),
        ("standardize", {"ddof": True}),
        ("standardize", {"ddof": 2}),
        ("rank", {"include_missing_codes": 1}),
    ],
)
def test_invalid_options(store: Store, function: str, kwargs: dict[str, Any]) -> None:
    revision = dataset(store, [[1], [2]])
    with pytest.raises(EngineError, match="error.operation_options"):
        getattr(columns, function)(store, revision, "x", "Bad", **kwargs)


@pytest.mark.parametrize(
    "mapping,unmatched",
    [
        ([{"from": None, "to": 1}], "keep"),
        ([{"from": 1, "to": 2}, {"from": 1, "to": 3}], "keep"),
        ([{"from": 1, "to": 2, "extra": 3}], "keep"),
        ([None], "keep"),
        ([], "bad"),
        ([], "keep"),
    ],
)
def test_invalid_recode(store: Store, mapping: Any, unmatched: str) -> None:
    revision = dataset(store, [[1]])
    if not mapping and unmatched == "keep":
        mapping = [{"from": 1, "to": 2}] * 1001
    with pytest.raises(EngineError, match="error.operation_options"):
        columns.recode(store, revision, "x", "Bad", mapping, unmatched)


@pytest.mark.parametrize("fields,keep", [([], "first"), (["x", "x"], "first"), (["x"], "random")])
def test_invalid_duplicates(store: Store, fields: list[str], keep: str) -> None:
    revision = dataset(store, [[1]])
    with pytest.raises(EngineError, match="error.operation_options"):
        columns.duplicates(store, revision, fields, "Bad", keep)


def test_duplicate_name_and_persistence_no_expression_execution(
    store: Store, tmp_path: Path
) -> None:
    revision = dataset(store, [[1]])
    with pytest.raises(EngineError, match="error.duplicate_fields"):
        columns.compute(store, revision, "Value", {"constant": 2})
    outcome = columns.compute(store, revision, "Derived", {"constant": 3})
    root = tmp_path / "formula.openstat"
    store.save(outcome["revision"], root)
    manifest = json.loads((root / "manifest.json").read_text())
    assert "expression" not in manifest
    assert values(store, store.open(root)) == [3]


def test_standardize_int64_neighbors_exact_difference(store: Store) -> None:
    revision = store.create(
        "Integers",
        [{"id": "x", "name": "Integer", "storage": "int64", "measurement": "discrete"}],
        [[2**63 - 4], [2**63 - 3], [2**63 - 2]],
    )["revision"]
    assert values(store, columns.standardize(store, revision, "x", "Z")) == pytest.approx(
        [-1, 0, 1]
    )
    assert values(store, columns.rank(store, revision, "x", "Rank")) == [1, 2, 3]


def test_duplicate_multiple_columns_and_missing_literals(store: Store) -> None:
    revision = store.create(
        "Pairs",
        [
            {"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"},
            {"id": "y", "name": "Y", "storage": "string", "measurement": "nominal"},
        ],
        [[1, "A"], [1, "B"], [1, "A"], [None, "A"], [None, "A"]],
    )["revision"]
    assert values(store, columns.duplicates(store, revision, ["x", "y"], "Duplicate")) == [
        False,
        False,
        True,
        False,
        True,
    ]


@pytest.mark.parametrize(
    "function,kwargs",
    [
        ("rank", {"ties": []}),
        ("lag", {"direction": []}),
    ],
)
def test_wrong_option_shapes(store: Store, function: str, kwargs: dict[str, Any]) -> None:
    revision = dataset(store, [[1]])
    with pytest.raises(EngineError, match="error.operation_options"):
        getattr(columns, function)(store, revision, "x", "Bad", **kwargs)
    with pytest.raises(EngineError, match="error.operation_options"):
        columns.duplicates(store, revision, [["x"]], "Bad")  # type: ignore[list-item]
    with pytest.raises(EngineError, match="error.operation_options"):
        columns.duplicates(store, revision, ["x"], "Bad", [])  # type: ignore[arg-type]
    with pytest.raises(EngineError, match="error.operation_options"):
        columns.recode(store, revision, "x", "Bad", [], [])  # type: ignore[arg-type]


def test_multiple_response_coded_missing_policy(store: Store) -> None:
    definition = {
        "id": "responses",
        "name": "Responses",
        "storage": "multiple_response",
        "measurement": "multiple_response",
        "missing_codes": ["?"],
    }
    revision = store.create(
        "Responses", [definition], [[None], [[]], [["a"]], [["?"]], [["a", "?"]]]
    )["revision"]

    recoded = columns.recode(store, revision, "responses", "Recode", [])
    assert values(store, recoded) == [None, [], ["a"], None, None]
    retained = columns.recode(
        store, revision, "responses", "Retained", [], include_missing_codes=True
    )
    assert values(store, retained) == [None, [], ["a"], ["?"], ["a", "?"]]

    lagged = columns.lag(store, revision, "responses", "Lag")
    assert values(store, lagged) == [None, None, [], ["a"], None]
    retained_lag = columns.lag(
        store, revision, "responses", "Retained lag", include_missing_codes=True
    )
    assert values(store, retained_lag) == [None, None, [], ["a"], ["?"]]
    led = columns.lag(store, revision, "responses", "Lead", direction="lead")
    assert values(store, led) == [[], ["a"], None, None, None]
    retained_lead = columns.lag(
        store,
        revision,
        "responses",
        "Retained lead",
        direction="lead",
        include_missing_codes=True,
    )
    assert values(store, retained_lead) == [[], ["a"], ["?"], ["a", "?"], None]
