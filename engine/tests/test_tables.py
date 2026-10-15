from collections.abc import Callable
from typing import Any

import pytest

from openstat_engine import tables, views
from openstat_engine.errors import EngineError
from openstat_engine.store import Store


def rows(store: Store, revision: str) -> list[list[Any]]:
    result: list[list[Any]] = []
    for batch in store.iter_tables(revision):
        data = batch.to_pydict()
        result.extend(
            [
                [data[field.id][i] for field in store.get(revision).fields]
                for i in range(batch.num_rows)
            ]
        )
    return result


def aggregate_rows(store: Store, source_revision: str, result_revision: str) -> list[list[Any]]:
    result = rows(store, result_revision)
    fields = store.get(result_revision).fields
    if len(fields) < 3 or fields[-3].name != "Source dataset":
        return result
    source_dataset_id = store.get(source_revision).dataset_id
    assert all(row[-3] == source_dataset_id for row in result)
    return [row[:-3] + row[-2:] for row in result]


@pytest.mark.feature("DATA-012")
@pytest.mark.feature("DATA-013")
@pytest.mark.feature("DATA-014")
@pytest.mark.feature("DATA-015")
@pytest.mark.feature("DATA-025")
def test_hand_calculated_table_contract(
    store: Store, reference_fixture: Callable[[str], dict[str, Any]]
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/tables.json")
    left = store.create(**fixture["left"])
    right = store.create(**fixture["right"])
    joined = tables.join(
        store,
        left["revision"],
        right["revision"],
        [{"left": "lk", "right": "rk"}],
        "Joined",
        how="full",
    )
    actual_pairs = [[row[-3], row[-1]] for row in rows(store, joined["revision"])]
    assert actual_pairs == fixture["expected"]["full_join_pairs"]
    assert len({row[-4] for row in rows(store, joined["revision"]) if row[-4] is not None}) == 1
    summary = tables.aggregate(
        store,
        left["revision"],
        ["lk"],
        [
            {"field": "amount", "op": "sum", "name": "Total"},
            {"field": "amount", "op": "count", "name": "N"},
        ],
        "Summary",
    )
    assert rows(store, summary["revision"]) == fixture["expected"]["aggregate"]
    grouped_source = store.create(**fixture["aggregate_input"])
    grouped = tables.aggregate(
        store,
        grouped_source["revision"],
        ["group"],
        [
            {"field": "whole", "op": "sum", "name": "Whole total"},
            {"field": "whole", "op": "count", "name": "Whole count"},
            {"field": "decimal", "op": "sum", "name": "Decimal total"},
        ],
        "Grouped summary",
        provenance=True,
    )
    assert (
        aggregate_rows(store, grouped_source["revision"], grouped["revision"])
        == fixture["expected"]["aggregate_input_provenance"]
    )
    assert grouped["fields"][-3]["name"] == "Source dataset"
    assert grouped["fields"][-3]["role"] == "identifier"
    assert grouped["fields"][-2]["name"] == "Source row count"
    assert grouped["fields"][-2]["role"] == "characteristic"
    assert grouped["fields"][-1]["name"] == "Source row IDs"
    assert grouped["fields"][-1]["role"] == "identifier"
    stacked = tables.stack(store, [left["revision"], left["revision"]], "Stacked")
    assert [row[:2] for row in rows(store, stacked["revision"])] == fixture["expected"]["stack"]
    pivot_source = store.create(**fixture["pivot_input"])
    summary_prov = tables.aggregate(
        store,
        pivot_source["revision"],
        ["case"],
        [
            {"field": "score", "op": "sum", "name": "Total"},
            {"field": "score", "op": "count", "name": "N"},
        ],
        "SummaryProv",
        provenance=True,
    )
    prov_rows = rows(store, summary_prov["revision"])
    assert (
        [[r[0], r[1], r[2], r[4], r[5]] for r in prov_rows]
        == fixture["expected"]["aggregate_provenance"]
    )
    assert all(r[3] == pivot_source["id"] for r in prov_rows)
    assert [f["name"] for f in summary_prov["fields"]] == [
        "Case",
        "Total",
        "N",
        "Source dataset",
        "Source row count",
        "Source row IDs",
    ]
    assert [f["role"] for f in summary_prov["fields"][-3:]] == [
        "identifier",
        "characteristic",
        "identifier",
    ]
    pivoted = tables.pivot(store, pivot_source["revision"], ["case"], "variable", "score", "Wide")
    assert rows(store, pivoted["revision"]) == fixture["expected"]["pivot"]
    wide_fields = [f["id"] for f in pivoted["fields"]]
    melted = tables.melt(
        store,
        pivoted["revision"],
        id_vars=[wide_fields[0]],
        value_vars=[wide_fields[1], wide_fields[2]],
        name="Melted",
        var_name="variable",
        value_name="score",
    )
    assert rows(store, melted["revision"]) == fixture["expected"]["melt"]
    matrix = store.create(**fixture["matrix"])
    source_rows = rows(store, matrix["revision"])
    transposed = tables.transpose(store, matrix["revision"], "Transposed")
    result = rows(store, transposed["revision"])
    assert [row[0] for row in result] == ["x", "y", "z"]
    assert [row[2:] for row in result] == fixture["expected"]["transpose"]
    assert rows(store, matrix["revision"]) == source_rows


@pytest.mark.feature("DATA-025")
def test_aggregate_preserves_original_case_ids_after_filter(store: Store) -> None:
    source = store.create(
        "Filtered groups",
        [
            {"id": "group", "name": "Group", "storage": "int64", "measurement": "discrete"},
            {"id": "amount", "name": "Amount", "storage": "int64", "measurement": "continuous"},
        ],
        [[1, 5], [1, 15], [1, 25]],
    )
    filtered = views.filter_cases(
        store,
        source["revision"],
        {"op": "gt", "field": "amount", "value": 10},
    )
    summary = tables.aggregate(
        store,
        filtered["revision"],
        ["group"],
        [{"field": "amount", "op": "sum", "name": "Total"}],
        "Filtered summary",
        provenance=True,
    )
    assert aggregate_rows(store, filtered["revision"], summary["revision"]) == [
        [1, 40, 2, ["1", "2"]]
    ]
    assert summary["fields"][-3]["name"] == "Source dataset"
    assert rows(store, summary["revision"])[0][-3] == store.get(filtered["revision"]).dataset_id
    assert summary["fields"][-1]["name"] == "Source row IDs"


@pytest.mark.feature("DATA-025")
def test_aggregate_validates_provenance_schema(store: Store) -> None:
    source = store.create(
        "Provenance validation",
        [{"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"}],
        [[1]],
    )
    aggregation = [{"field": "x", "op": "count", "name": "Count"}]
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.aggregate(
            store,
            source["revision"],
            [],
            aggregation,
            "Bad provenance option",
            provenance="true",  # type: ignore[arg-type]
        )
    too_many = [
        {"field": "x", "op": "count", "name": f"Count {index}"}
        for index in range(tables.COLUMN_LIMIT - 2)
    ]
    with pytest.raises(EngineError, match="error.global_limit"):
        tables.aggregate(store, source["revision"], [], too_many, "Too wide", provenance=True)


@pytest.mark.feature("DATA-014")
def test_stack_streams_and_preserves_source_identity(store: Store) -> None:
    fields = [{"id": "x", "name": "Score", "storage": "int64", "measurement": "discrete"}]
    first = store.create("First", fields, [[1], [2]])
    second = store.create("Second", fields, [[3]])
    outcome = tables.stack(store, [first["revision"], second["revision"]], "Stacked")
    output = rows(store, outcome["revision"])
    assert [row[0] for row in output] == [1, 2, 3]
    assert [row[-1] for row in output] == [0, 1, 0]
    assert [row[-2] for row in output] == [first["id"], first["id"], second["id"]]
    assert store.page(outcome["revision"])["row_ids"] == [0, 1, 2]


def test_stack_rejects_mismatched_types_and_duplicate_names(store: Store) -> None:
    one = store.create(
        "One", [{"id": "a", "name": "Value", "storage": "int64", "measurement": "discrete"}], [[1]]
    )
    two = store.create(
        "Two",
        [{"id": "b", "name": "Value", "storage": "string", "measurement": "nominal"}],
        [["x"]],
    )
    with pytest.raises(EngineError, match="error.value_type"):
        tables.stack(store, [one["revision"], two["revision"]], "Bad")
    with pytest.raises(EngineError, match="error.duplicate_fields"):
        tables.stack(store, [one["revision"], two["revision"]], "Bad", match="id")


def test_join_null_duplicate_and_cardinality_policies(store: Store) -> None:
    field = [{"id": "key", "name": "Key", "storage": "int64", "measurement": "discrete"}]
    left = store.create("L", field, [[None], [1], [1]])
    right = store.create("R", field, [[None], [1]])
    never = tables.join(
        store,
        left["revision"],
        right["revision"],
        [{"left": "key", "right": "key"}],
        "Never",
        how="full",
    )
    assert len(rows(store, never["revision"])) == 4
    equal = tables.join(
        store,
        left["revision"],
        right["revision"],
        [{"left": "key", "right": "key"}],
        "Equal",
        missing="equal",
    )
    assert len(rows(store, equal["revision"])) == 3
    with pytest.raises(EngineError, match="error.cardinality"):
        tables.join(
            store,
            left["revision"],
            right["revision"],
            [{"left": "key", "right": "key"}],
            "One",
            cardinality="one_to_one",
        )
    with pytest.raises(EngineError, match="error.cardinality"):
        tables.join(
            store,
            left["revision"],
            right["revision"],
            [{"left": "key", "right": "key"}],
            "Unique right required",
            cardinality="one_to_many",
        )
    with pytest.raises(EngineError, match="error.cardinality"):
        tables.join(
            store,
            right["revision"],
            left["revision"],
            [{"left": "key", "right": "key"}],
            "Unique left required",
            cardinality="many_to_one",
        )


def test_join_collisions_empty_data_and_overlay_values(store: Store) -> None:
    fields = [
        {"id": "key", "name": "Key", "storage": "float64", "measurement": "continuous"},
        {"id": "value", "name": "Shared", "storage": "int64", "measurement": "discrete"},
    ]
    left = store.create("Left", fields, [[1.0, 5]])
    right = store.create("Right", fields, [[2.0, 7]])
    edited = store.edit(left["revision"], 0, "value", 9)
    empty_inner = tables.join(
        store,
        edited["revision"],
        right["revision"],
        [{"left": "key", "right": "key"}],
        "Empty inner",
    )
    assert rows(store, empty_inner["revision"]) == []
    full = tables.join(
        store,
        edited["revision"],
        right["revision"],
        [{"left": "key", "right": "key"}],
        "Full",
        how="full",
        suffixes=["_L", "_R"],
    )
    assert [field.name for field in store.get(full["revision"]).fields[:2]] == [
        "Shared_L",
        "Shared_R",
    ]
    assert rows(store, full["revision"])[0][:2] == [9, None]
    assert rows(store, full["revision"])[1][:2] == [None, 7]
    assert rows(store, left["revision"])[0][1] == 5
    with pytest.raises(EngineError, match="error.duplicate_fields"):
        tables.join(
            store,
            edited["revision"],
            right["revision"],
            [{"left": "key", "right": "key"}],
            "Collision",
            suffixes=["_x", "_x"],
        )


def test_join_exact_float_and_multiple_response_keys(store: Store) -> None:
    float_fields = [{"id": "k", "name": "K", "storage": "float64", "measurement": "continuous"}]
    left = store.create("Float L", float_fields, [[0.1], [0.10000000000000002]])
    right = store.create("Float R", float_fields, [[0.1]])
    result = tables.join(
        store, left["revision"], right["revision"], [{"left": "k", "right": "k"}], "Exact"
    )
    assert len(rows(store, result["revision"])) == 1
    choices = [
        {
            "id": "k",
            "name": "Choices",
            "storage": "multiple_response",
            "measurement": "multiple_response",
            "levels": ["A", "B"],
        }
    ]
    left_list = store.create("Lists L", choices, [[["A", "B"]]])
    right_list = store.create("Lists R", choices, [[["A", "B"]]])
    list_join = tables.join(
        store,
        left_list["revision"],
        right_list["revision"],
        [{"left": "k", "right": "k"}],
        "List key",
    )
    assert rows(store, list_join["revision"])[0][0] == ["A", "B"]


@pytest.mark.feature("DATA-015")
def test_pivot_and_duplicate_cells(store: Store) -> None:
    revision = store.create(
        "Long",
        [
            {"id": "id", "name": "ID", "storage": "int64", "measurement": "discrete"},
            {"id": "key", "name": "Variable", "storage": "string", "measurement": "nominal"},
            {"id": "value", "name": "Value", "storage": "float64", "measurement": "continuous"},
        ],
        [[1, "A", 2.0], [1, "B", 3.0], [2, "A", 4.0]],
    )
    result = tables.pivot(store, revision["revision"], ["id"], "key", "value", "Wide")
    assert rows(store, result["revision"]) == [[1, 2.0, 3.0], [2, 4.0, None]]
    duplicate = store.create(
        "Duplicate",
        [
            {"id": "id", "name": "ID", "storage": "int64", "measurement": "discrete"},
            {"id": "key", "name": "Variable", "storage": "string", "measurement": "nominal"},
            {"id": "value", "name": "Value", "storage": "float64", "measurement": "continuous"},
        ],
        [[1, "A", 2.0], [1, "A", 3.0]],
    )
    with pytest.raises(EngineError, match="error.duplicate_fields"):
        tables.pivot(store, duplicate["revision"], ["id"], "key", "value", "Bad")


@pytest.mark.parametrize("operation", ["join", "pivot", "aggregate", "transpose"])
def test_global_limits(store: Store, operation: str) -> None:
    revision = store.create(
        "Tiny", [{"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"}], [[1]]
    )
    store.revisions[revision["revision"]] = store.get(revision["revision"]).__class__(
        **{**store.get(revision["revision"]).__dict__, "row_count": tables.GLOBAL_LIMIT + 1}
    )
    with pytest.raises(EngineError, match="error.global_limit"):
        if operation == "join":
            tables.join(
                store,
                revision["revision"],
                revision["revision"],
                [{"left": "x", "right": "x"}],
                "J",
            )
        elif operation == "pivot":
            tables.pivot(store, revision["revision"], ["x"], "x", "x", "P")
        elif operation == "aggregate":
            tables.aggregate(
                store, revision["revision"], [], [{"field": "x", "op": "count", "name": "N"}], "A"
            )
        else:
            tables.transpose(store, revision["revision"], "T")


def test_invalid_contracts_and_atomic_cleanup(store: Store) -> None:
    left = store.create(
        "L", [{"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"}], [[1]]
    )
    right = store.create(
        "R", [{"id": "y", "name": "Y", "storage": "string", "measurement": "nominal"}], [["1"]]
    )
    existing = set(store.directory.iterdir())
    with pytest.raises(EngineError, match="error.value_type"):
        tables.join(
            store, left["revision"], right["revision"], [{"left": "x", "right": "y"}], "Invalid"
        )
    assert set(store.directory.iterdir()) == existing
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.aggregate(store, left["revision"], [], [], "Bad")


def test_validation_and_uncommon_result_branches(store: Store) -> None:
    numeric = [{"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"}]
    one = store.create("One", numeric, [[1], [2]])
    empty = store.create("Empty", numeric, [])
    for revisions, match, name in [([], "name", "Bad"), ([one["revision"]], "bad", "Bad")]:
        with pytest.raises(EngineError, match="error.operation_options"):
            tables.stack(store, revisions, name, match)
    with pytest.raises(EngineError, match="error.field_id"):
        tables.transpose(store, one["revision"], "Bad", ["missing"])
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.transpose(store, one["revision"], "Bad", [])
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.transpose(store, one["revision"], "Bad", [1])  # type: ignore[list-item]
    wide_input = store.create("Wide input", numeric, [[i] for i in range(1023)])
    with pytest.raises(EngineError, match="error.global_limit"):
        tables.transpose(store, wide_input["revision"], "Too wide")

    invalid_join_options: list[dict[str, Any]] = [
        {"how": "bad"},
        {"missing": "bad"},
        {"cardinality": "bad"},
        {"suffixes": ["x"]},
    ]
    for kwargs in invalid_join_options:
        with pytest.raises(EngineError, match="error.operation_options"):
            tables.join(
                store,
                one["revision"],
                one["revision"],
                [{"left": "x", "right": "x"}],
                "Bad",
                **kwargs,
            )
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.join(
            store,
            one["revision"],
            one["revision"],
            [{"left": "x", "right": "x"}, {"left": "x", "right": "x"}],
            "Bad",
        )
    with pytest.raises(EngineError, match="error.field_id"):
        tables.join(
            store, one["revision"], one["revision"], [{"left": "missing", "right": "x"}], "Bad"
        )

    categorical = store.create(
        "Categories",
        [
            {"id": "key", "name": "Key", "storage": "string", "measurement": "nominal"},
            {"id": "value", "name": "Value", "storage": "int64", "measurement": "discrete"},
        ],
        [["A", 1], ["B", 2]],
    )
    wide = tables.pivot(store, categorical["revision"], ["key"], "key", "value", "Wide")
    assert len(rows(store, wide["revision"])) == 2
    many_categories = store.create(
        "Many categories",
        [
            {"id": "key", "name": "Key", "storage": "string", "measurement": "nominal"},
            {"id": "value", "name": "Value", "storage": "int64", "measurement": "discrete"},
        ],
        [[f"C{i}", i] for i in range(1025)],
    )
    with pytest.raises(EngineError, match="error.global_limit"):
        tables.pivot(store, many_categories["revision"], ["value"], "key", "value", "Too wide")

    aggregate = tables.aggregate(
        store,
        one["revision"],
        [],
        [
            {"field": "x", "op": "sum", "name": "Sum"},
            {"field": "x", "op": "mean", "name": "Mean"},
            {"field": "x", "op": "min", "name": "Min"},
            {"field": "x", "op": "max", "name": "Max"},
        ],
        "Statistics",
        provenance=True,
    )
    assert aggregate_rows(store, one["revision"], aggregate["revision"]) == [
        [3, 1.5, 1, 2, 2, ["0", "1"]]
    ]
    all_null = store.create(
        "Null",
        [
            {
                "id": "x",
                "name": "X",
                "storage": "int64",
                "measurement": "discrete",
                "missing_codes": ["-9"],
            }
        ],
        [[None], [-9]],
    )
    excluded = tables.aggregate(
        store,
        all_null["revision"],
        [],
        [{"field": "x", "op": "sum", "name": "Sum"}],
        "Excluded",
        provenance=True,
    )
    included = tables.aggregate(
        store,
        all_null["revision"],
        [],
        [{"field": "x", "op": "sum", "name": "Sum"}],
        "Included",
        True,
        provenance=True,
    )
    assert aggregate_rows(store, all_null["revision"], excluded["revision"]) == [
        [None, 2, ["0", "1"]]
    ]
    assert aggregate_rows(store, all_null["revision"], included["revision"]) == [
        [-9, 2, ["0", "1"]]
    ]
    assert tables.aggregate(
        store,
        empty["revision"],
        ["x"],
        [{"field": "x", "op": "count", "name": "N"}],
        "Empty summary",
    )


def test_aggregate_uses_stable_float_sums_and_means(store: Store) -> None:
    cancellation = store.create(
        "Cancellation",
        [{"id": "x", "name": "X", "storage": "float64", "measurement": "continuous"}],
        [[1e16], [1.0], [-1e16]],
    )
    reduced = tables.aggregate(
        store,
        cancellation["revision"],
        [],
        [
            {"field": "x", "op": "sum", "name": "Sum"},
            {"field": "x", "op": "mean", "name": "Mean"},
        ],
        "Stable arithmetic",
        provenance=True,
    )
    # Exact binary-float sum is 1; mean is exact sum divided by three, rounded once.
    assert aggregate_rows(store, cancellation["revision"], reduced["revision"]) == [
        [1.0, 1.0 / 3.0, 3, ["0", "1", "2"]]
    ]

    large = store.create(
        "Large finite",
        [{"id": "x", "name": "X", "storage": "float64", "measurement": "continuous"}],
        [[1e308], [1e308]],
    )
    mean = tables.aggregate(
        store,
        large["revision"],
        [],
        [{"field": "x", "op": "mean", "name": "Mean"}],
        "Finite mean",
        provenance=True,
    )
    assert aggregate_rows(store, large["revision"], mean["revision"]) == [[1e308, 2, ["0", "1"]]]
    with pytest.raises(EngineError, match="error.transform_domain"):
        tables.aggregate(
            store,
            large["revision"],
            [],
            [{"field": "x", "op": "sum", "name": "Sum"}],
            "Overflowing sum",
        )


def test_aggregate_preserves_exact_integer_sums_and_checks_int64_range(store: Store) -> None:
    cancellation = store.create(
        "Exact cancellation",
        [{"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"}],
        [[2**53], [1], [-(2**53)]],
    )
    result = tables.aggregate(
        store,
        cancellation["revision"],
        [],
        [{"field": "x", "op": "sum", "name": "Sum"}],
        "Exact integer sum",
    )
    total = aggregate_rows(store, cancellation["revision"], result["revision"])[0][0]
    assert type(total) is int
    assert total == 1

    overflow = store.create(
        "Integer overflow",
        [{"id": "x", "name": "X", "storage": "int64", "measurement": "discrete"}],
        [[2**63 - 1], [1]],
    )
    before_files = set(store.directory.iterdir())
    with pytest.raises(EngineError, match="error.integer_range"):
        tables.aggregate(
            store,
            overflow["revision"],
            [],
            [{"field": "x", "op": "sum", "name": "Sum"}],
            "Out of range",
        )
    assert set(store.directory.iterdir()) == before_files


def test_aggregate_count_uses_classification_coded_missing_policy(store: Store) -> None:
    source = store.create(
        "Multiple response codes",
        [
            {
                "id": "responses",
                "name": "Responses",
                "storage": "multiple_response",
                "measurement": "multiple_response",
                "levels": ["A", "B", "X"],
                "missing_codes": ["X"],
            }
        ],
        [[["A"]], [["X"]], [["A", "X"]], [None], [[]]],
    )
    excluded = tables.aggregate(
        store,
        source["revision"],
        [],
        [{"field": "responses", "op": "count", "name": "N"}],
        "Valid response count",
        provenance=True,
    )
    included = tables.aggregate(
        store,
        source["revision"],
        [],
        [{"field": "responses", "op": "count", "name": "N"}],
        "All response count",
        include_missing_codes=True,
        provenance=True,
    )
    assert aggregate_rows(store, source["revision"], excluded["revision"]) == [
        [2, 5, ["0", "1", "2", "3", "4"]]
    ]
    assert aggregate_rows(store, source["revision"], included["revision"]) == [
        [4, 5, ["0", "1", "2", "3", "4"]]
    ]


def test_aggregate_singleton_and_empty_results(store: Store) -> None:
    fields = [{"id": "x", "name": "X", "storage": "float64", "measurement": "continuous"}]
    single = store.create("Singleton", fields, [[1e308]])
    singleton = tables.aggregate(
        store,
        single["revision"],
        [],
        [
            {"field": "x", "op": "sum", "name": "Sum"},
            {"field": "x", "op": "mean", "name": "Mean"},
        ],
        "Singleton summary",
        provenance=True,
    )
    assert aggregate_rows(store, single["revision"], singleton["revision"]) == [
        [1e308, 1e308, 1, ["0"]]
    ]
    empty = store.create("No cases", fields, [])
    summary = tables.aggregate(
        store,
        empty["revision"],
        [],
        [{"field": "x", "op": "sum", "name": "Sum"}],
        "Empty summary",
    )
    assert rows(store, summary["revision"]) == []


def test_melt_edge_cases_and_validations(store: Store) -> None:
    fields = [
        {"id": "id", "name": "ID", "storage": "int64", "measurement": "discrete"},
        {"id": "a", "name": "A", "storage": "int64", "measurement": "continuous"},
        {"id": "b", "name": "B", "storage": "float64", "measurement": "continuous"},
        {"id": "s", "name": "S", "storage": "string", "measurement": "nominal"},
        {
            "id": "resp",
            "name": "Resp",
            "storage": "multiple_response",
            "measurement": "multiple_response",
            "levels": ["x"],
        },
    ]
    ds = store.create("Sample", fields, [[1, 10, 1.5, "alpha", ["x"]], [2, 20, 2.5, "beta", []]])
    rev = ds["revision"]

    # 1. Empty id_vars (unpivot all value_vars)
    all_melted = tables.melt(store, rev, [], ["a", "b"], "NoIDs")
    assert rows(store, all_melted["revision"]) == [
        ["A", 10.0],
        ["B", 1.5],
        ["A", 20.0],
        ["B", 2.5],
    ]
    assert [f["name"] for f in all_melted["fields"]] == ["variable", "value"]

    # 2. Incompatible types (int64 + string)
    with pytest.raises(EngineError, match="error.value_type"):
        tables.melt(store, rev, ["id"], ["a", "s"], "BadTypes")

    # 3. Multiple response rejected
    with pytest.raises(EngineError, match="error.value_type"):
        tables.melt(store, rev, ["id"], ["resp"], "BadResp")

    # 4. Overlap between id_vars and value_vars
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.melt(store, rev, ["id"], ["id", "a"], "Overlap")

    # 5. Empty value_vars
    with pytest.raises(EngineError, match="error.operation_options"):
        tables.melt(store, rev, ["id"], [], "EmptyVals")

    # 6. Duplicate output name
    with pytest.raises(EngineError, match="error.duplicate_fields"):
        tables.melt(store, rev, ["id"], ["a", "b"], "Dupe", var_name="ID")

    # Value metadata must agree before source columns can share one output field.
    labeled = store.create(
        "Labeled values",
        [
            {"id": "left", "name": "Left", "storage": "int64", "measurement": "ordinal",
             "levels": ["1", "2"], "value_labels": {"1": "Agree", "2": "Disagree"},
             "missing_codes": ["99"]},
            {"id": "right", "name": "Right", "storage": "int64", "measurement": "ordinal",
             "levels": ["1", "2"], "value_labels": {"1": "Agree", "2": "Disagree"},
             "missing_codes": ["99"]},
        ],
        [[1, 2]],
    )
    preserved = tables.melt(
        store, labeled["revision"], [], ["left", "right"], "Labeled melt"
    )
    assert preserved["fields"][-1]["measurement"] == "ordinal"
    assert preserved["fields"][-1]["levels"] == ["1", "2"]
    assert preserved["fields"][-1]["value_labels"] == {"1": "Agree", "2": "Disagree"}
    assert preserved["fields"][-1]["missing_codes"] == ["99"]

    different_labels = store.create(
        "Conflicting labels",
        [
            {"id": "left", "name": "Left", "storage": "int64", "measurement": "ordinal",
             "value_labels": {"1": "Agree"}},
            {"id": "right", "name": "Right", "storage": "int64", "measurement": "ordinal",
             "value_labels": {"1": "Disagree"}},
        ],
        [[1, 1]],
    )
    with pytest.raises(EngineError, match="error.incompatible_melt_fields"):
        tables.melt(
            store, different_labels["revision"], [], ["left", "right"], "Conflicting melt"
        )

    coded_numeric = store.create(
        "Coded numeric",
        [
            {"id": "integer", "name": "Integer", "storage": "int64", "measurement": "continuous"},
            {"id": "float", "name": "Float", "storage": "float64", "measurement": "continuous",
             "missing_codes": ["-99"]},
        ],
        [[1, 1.0]],
    )
    with pytest.raises(EngineError, match="error.incompatible_melt_fields"):
        tables.melt(
            store, coded_numeric["revision"], [], ["integer", "float"], "Coded numeric melt"
        )

    imprecise_numeric = store.create(
        "Imprecise numeric",
        [
            {"id": "integer", "name": "Integer", "storage": "int64", "measurement": "continuous"},
            {"id": "float", "name": "Float", "storage": "float64", "measurement": "continuous"},
        ],
        [[9_007_199_254_740_993, 1.5]],
    )
    with pytest.raises(EngineError, match="error.melt_precision_loss"):
        tables.melt(
            store, imprecise_numeric["revision"], [], ["integer", "float"], "Imprecise melt"
        )


@pytest.mark.feature("DATA-025")
def test_aggregate_row_provenance_and_duplicate_safety(store: Store) -> None:
    fields = [
        {"id": "grp", "name": "Group", "storage": "string", "measurement": "nominal"},
        {"id": "val", "name": "Value", "storage": "int64", "measurement": "discrete"},
    ]
    dataset = store.create("Test", fields, [["B", 10], ["A", 20], ["B", 30], ["A", 40]])
    agg = tables.aggregate(
        store,
        dataset["revision"],
        ["grp"],
        [{"field": "val", "op": "sum", "name": "Sum"}],
        "Agg",
        provenance=True,
    )
    agg_rows = rows(store, agg["revision"])
    assert agg_rows == [
        ["B", 40, dataset["id"], 2, ["0", "2"]],
        ["A", 60, dataset["id"], 2, ["1", "3"]],
    ]

    with pytest.raises(EngineError, match="error.operation_options"):
        tables.aggregate(
            store,
            dataset["revision"],
            ["grp"],
            [{"field": "val", "op": "sum", "name": "Sum"}],
            "Bad",
            provenance="true",  # type: ignore[arg-type]
        )

    with pytest.raises(EngineError, match="error.duplicate_fields"):
        tables.aggregate(
            store,
            dataset["revision"],
            ["grp"],
            [{"field": "val", "op": "sum", "name": "Source row count"}],
            "Collision",
            provenance=True,
        )
