import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from openstat_engine.errors import EngineError
from openstat_engine.store import Store, digest
from openstat_engine.views import (
    filter_cases,
    predicate,
    select,
    set_weights,
    sort_cases,
    weights,
)


@pytest.mark.feature("DATA-006")
@pytest.mark.feature("DATA-008")
@pytest.mark.feature("DATA-009")
@pytest.mark.feature("DATA-007")
def test_original_case_contract(
    store: Store, reference_fixture: Callable[[str], dict[str, Any]]
) -> None:
    original = reference_fixture("engine/fixtures/foundations/cases.json")
    source = store.create(
        "Original case contract", original["input"]["fields"], original["input"]["rows"]
    )
    revision = source["revision"]
    expected = original["expected"]
    counts = select(store, revision, original["input"]["condition"])
    assert {key: counts[key] for key in ["selected", "false", "unknown"]} == expected["counts"]
    filtered = filter_cases(store, revision, original["input"]["condition"])
    assert store.page(filtered["revision"])["row_ids"] == expected["filtered_ids"]
    ordered = sort_cases(store, revision, original["input"]["sort"])
    assert store.page(ordered["revision"])["row_ids"] == expected["sorted_ids"]
    weight = weights(store, revision, "w")
    assert {
        key: weight[key] for key in ["eligible", "missing", "zero", "total_weight"]
    } == expected["weights"]
    weighted = set_weights(store, revision, "w", "frequency")
    assert weighted["weights"] == {"field": "w", "kind": "frequency"}
    assert {
        key: weighted["audit"][key] for key in ["eligible", "missing", "zero", "total_weight"]
    } == expected["weights"]


@pytest.mark.parametrize(
    "op,wanted,expected",
    [
        ("eq", 2, 2),
        ("ne", 2, 1),
        ("lt", 2, 1),
        ("le", 2, 3),
        ("gt", 2, 0),
        ("ge", 2, 2),
        ("in", [1, 2], 3),
    ],
)
def test_typed_numeric_predicates(
    store: Store, numeric: list[dict[str, str]], op: str, wanted: Any, expected: int
) -> None:
    result = store.create("T", numeric, [[1], [2], [2], [None]])
    counts = select(store, result["revision"], {"op": op, "field": "amount", "value": wanted})
    assert counts["selected"] == expected and counts["unknown"] == 1


@pytest.mark.parametrize(
    "op,expected", [("is_null", 1), ("is_coded_missing", 1), ("is_missing", 2)]
)
def test_null_and_coded_missing_remain_distinct(store: Store, op: str, expected: int) -> None:
    fields = [
        {
            "id": "x",
            "name": "X",
            "storage": "string",
            "measurement": "binary",
            "levels": ["a", "b"],
            "missing_codes": ["?"],
        }
    ]
    result = store.create("T", fields, [["a"], ["?"], [None]])
    assert select(store, result["revision"], {"op": op, "field": "x"})["selected"] == expected
    assert (
        select(store, result["revision"], {"op": "eq", "field": "x", "value": "a"})["selected"] == 1
    )


def test_three_valued_boolean_algebra() -> None:
    from openstat_engine.model import Field

    fields = (Field("x", "X", "float64", "continuous"),)
    compare = {"op": "gt", "field": "x", "value": 0}
    missing = {"op": "is_missing", "field": "x"}
    assert (
        predicate(fields, {"op": "and", "args": [compare, {"op": "not", "args": [missing]}]})(
            dict(x=None)
        )
        is False
    )
    assert predicate(fields, {"op": "or", "args": [compare, missing]})(dict(x=None)) is True
    assert predicate(fields, {"op": "not", "args": [compare]})(dict(x=None)) is None
    assert predicate(fields, {"op": "or", "args": [compare, missing]})(dict(x=-1)) is False
    assert predicate(fields, {"op": "and", "args": [compare]})(dict(x=1)) is True


@pytest.mark.parametrize(
    "spec",
    [
        {},
        {"op": "eval", "field": "x", "value": "bad"},
        {"op": "and", "args": []},
        {"op": "not", "args": [{"op": "is_null", "field": "x"}] * 2},
        {"op": "and", "args": "bad"},
        {"op": "is_null", "field": "x", "extra": True},
        {"op": "eq", "field": "x", "value": None},
        {"op": "in", "field": "x", "value": "bad"},
        {"op": "contains", "field": "x", "value": "x"},
        {"op": "eq", "field": "absent", "value": 1},
    ],
)
def test_invalid_conditions_reject_without_revision(
    store: Store, numeric: list[dict[str, str]], spec: dict[str, Any]
) -> None:
    result = store.create("T", [numeric[0] | {"id": "x"}], [[1]])
    with pytest.raises(EngineError):
        filter_cases(store, result["revision"], spec)
    assert len(store.revisions) == 1


def test_predicate_depth_and_response_membership(store: Store) -> None:
    fields = [
        {
            "id": "x",
            "name": "X",
            "storage": "multiple_response",
            "measurement": "multiple_response",
            "missing_codes": ["?"],
        }
    ]
    result = store.create("T", fields, [[["a", "b"]], [[]], [["?"]], [None]])
    assert (
        select(store, result["revision"], {"op": "contains", "field": "x", "value": "a"})[
            "selected"
        ]
        == 1
    )
    with pytest.raises(EngineError):
        select(store, result["revision"], {"op": "eq", "field": "x", "value": ["a"]})
    condition: dict[str, Any] = {"op": "is_null", "field": "x"}
    for _ in range(18):
        condition = {"op": "not", "args": [condition]}
    with pytest.raises(EngineError):
        select(store, result["revision"], condition)


def test_filter_edits_append_and_project_roundtrip_use_stable_ids(
    store: Store, numeric: list[dict[str, str]], tmp_path: Path
) -> None:
    initial = store.create("T", numeric, [[9], [1], [5], [3]])
    base_hash = digest(store.get(initial["revision"]).base)
    edited = store.edit(initial["revision"], 2, "amount", 6)
    filtered = filter_cases(store, edited["revision"], {"op": "ge", "field": "amount", "value": 5})
    assert store.page(filtered["revision"])["row_ids"] == [0, 2]
    changed = store.edit(filtered["revision"], 2, "amount", 7)
    assert store.page(changed["revision"])["rows"] == [[9.0], [7.0]]
    with pytest.raises(EngineError, match="error.row_id"):
        store.edit(filtered["revision"], 1, "amount", 8)
    appended = store.extend(changed["revision"], rows=1)
    assert store.page(appended["revision"])["row_ids"] == [0, 2, 3]
    path = tmp_path / "Filtered.openstat"
    store.save(appended["revision"], str(path))
    other = Store(tmp_path / "other")
    opened = other.open(str(path))
    assert other.page(opened["revision"])["rows"] == [[9.0], [7.0], [None]]
    assert digest(store.get(initial["revision"]).base) == base_hash


def test_sort_descending_ordinal_nulls_and_stable_ties(store: Store) -> None:
    fields = [
        {
            "id": "x",
            "name": "X",
            "storage": "string",
            "measurement": "ordinal",
            "levels": ["low", "mid", "high"],
        }
    ]
    source = store.create("T", fields, [["high"], ["low"], ["mid"], ["mid"], [None]])
    result = sort_cases(
        store, source["revision"], [{"field": "x", "ascending": False}], nulls="first"
    )
    assert store.page(result["revision"])["row_ids"] == [4, 0, 2, 3, 1]
    assert store.page(source["revision"])["row_ids"] == [0, 1, 2, 3, 4]


def test_external_sort_multiple_merge_passes(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "Original-generated.csv"
    with path.open("w") as stream:
        stream.write("X\n")
        for value in range(140000 - 1, -1, -1):
            stream.write(f"{value}\n")
    initial = store.import_csv(str(path))
    result = sort_cases(store, initial["revision"], [{"field": initial["fields"][0]["id"]}])
    first = store.page(result["revision"], 0, 2)
    last = store.page(result["revision"], 139998, 2)
    assert first["rows"] == [[0], [1]] and first["row_ids"] == [139999, 139998]
    assert last["rows"] == [[139998], [139999]]
    assert not list(store.directory.glob("openstat-sort-*"))


@pytest.mark.parametrize(
    "keys,nulls",
    [
        ([], "last"),
        ([{"field": "absent"}], "last"),
        ([{"field": "amount", "ascending": 1}], "last"),
        ([{"field": "amount", "extra": "bad"}], "last"),
        ([{"field": "amount"}] * 2, "last"),
        ([{"field": "amount"}], "bad"),
    ],
)
def test_invalid_sort_options(
    store: Store, numeric: list[dict[str, str]], keys: Any, nulls: str
) -> None:
    source = store.create("T", numeric, [])
    with pytest.raises(EngineError):
        sort_cases(store, source["revision"], keys, nulls)


def test_filter_and_sort_cleanup_after_write_error(
    store: Store, numeric: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = store.create("T", numeric, [[1]])
    before = set(store.directory.glob("*.parquet"))

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("Original test fault")

    monkeypatch.setattr(pq.ParquetWriter, "write_table", fail)
    with pytest.raises(OSError):
        filter_cases(store, source["revision"], {"op": "gt", "field": "amount", "value": 0})
    with pytest.raises(OSError):
        sort_cases(store, source["revision"], [{"field": "amount"}])
    assert set(store.directory.glob("*.parquet")) == before


def test_weights_reject_negative_fractional_wrong_role_and_kind(
    store: Store, numeric: list[dict[str, str]]
) -> None:
    for rows, kind in [([[-1]], "frequency"), ([[1.5]], "frequency")]:
        result = store.create("T", numeric, rows)
        with pytest.raises(EngineError, match="error.weight_value"):
            weights(store, result["revision"], "amount", kind)
    result = store.create("T", numeric, [[1.5], [0.5], [None]])
    assert weights(store, result["revision"], "amount", "analytic")["total_weight"] == 2
    for field, kind in [("absent", "frequency"), ("amount", "invalid")]:
        with pytest.raises(EngineError):
            weights(store, result["revision"], field, kind)
    definition = numeric[0] | {"role": "identifier"}
    result = store.create("T", [definition], [[1]])
    with pytest.raises(EngineError):
        weights(store, result["revision"], "amount")


def test_scan_projection_edit_bit_patterns_and_metadata_without_reads(
    store: Store, numeric: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    result = store.create("T", numeric, [[-0.0], [None]])
    edited = store.edit(result["revision"], 1, "amount", 2.5)
    values = list(store.iter_tables(edited["revision"], ["amount"], batch_size=1))
    assert math.copysign(1, values[0]["amount"][0].as_py()) == -1
    assert values[1]["amount"][0].as_py() == 2.5
    for columns, size in [([], 1), (["missing"], 1), (["amount"] * 2, 1), (["amount"], 0)]:
        with pytest.raises(EngineError):
            list(store.iter_tables(edited["revision"], columns, size))

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Metadata rename scanned data")

    monkeypatch.setattr(store, "iter_tables", fail)
    renamed = store.metadata(
        result["revision"], [numeric[0] | {"name": "Renamed"}], "sample", "case"
    )
    assert renamed["context"] == "sample"


def test_weights_persistence_and_project_roundtrip(store: Store, tmp_path: Path) -> None:
    fields = [
        {"id": "w_freq", "name": "FreqWeight", "storage": "int64", "measurement": "discrete"},
        {"id": "w_ana", "name": "AnaWeight", "storage": "float64", "measurement": "continuous"},
        {"id": "score", "name": "Score", "storage": "float64", "measurement": "continuous"},
    ]
    data = [[2, 1.5, 10.0], [3, 0.5, 20.0]]
    item = store.create("Weighted Dataset", fields, data)
    rev0 = item["revision"]
    assert store.get(rev0).weights is None
    assert "weights" not in store.get(rev0).descriptor()

    # Set frequency weights
    weighted = set_weights(store, rev0, "w_freq", "frequency")
    rev1 = weighted["revision"]
    assert weighted["weights"] == {"field": "w_freq", "kind": "frequency"}
    assert weighted["audit"]["total_weight"] == 5
    assert store.get(rev1).descriptor()["weights"] == {"field": "w_freq", "kind": "frequency"}

    # Save to .openstat project package
    project_pkg = tmp_path / "weighted_study.openstat"
    store.save(rev1, str(project_pkg))

    # Re-open in a fresh Store instance
    store2 = Store(tmp_path / "fresh_store")
    opened = store2.open(str(project_pkg))
    assert opened["weights"] == {"field": "w_freq", "kind": "frequency"}
    rev_opened = opened["revision"]
    assert store2.get(rev_opened).weights == {"field": "w_freq", "kind": "frequency"}

    # Switch to analytic weights
    analytic_weighted = set_weights(store2, rev_opened, "w_ana", "analytic")
    assert analytic_weighted["weights"] == {"field": "w_ana", "kind": "analytic"}
    assert analytic_weighted["audit"]["total_weight"] == 2.0

    # Clear weights
    cleared = set_weights(store2, analytic_weighted["revision"], None)
    assert cleared.get("weights") is None
    assert store2.get(cleared["revision"]).weights is None


def test_weights_preserved_on_delete_and_cleared_on_drop(store: Store) -> None:
    from openstat_engine.structure import delete_cases, drop_fields

    fields = [
        {"id": "w", "name": "Weight", "storage": "int64", "measurement": "discrete"},
        {"id": "val", "name": "Value", "storage": "int64", "measurement": "discrete"},
    ]
    created = store.create("Test", fields, [[1, 10], [2, 20], [3, 30]])
    weighted = set_weights(store, created["revision"], "w", "frequency")

    # Deleting a case preserves weights
    after_del = delete_cases(store, weighted["revision"], [1])
    assert after_del["weights"] == {"field": "w", "kind": "frequency"}

    # Dropping an unrelated field preserves weights
    after_drop_val = drop_fields(store, weighted["revision"], ["val"])
    assert after_drop_val["weights"] == {"field": "w", "kind": "frequency"}

    # Dropping the weight field clears weights
    after_drop_w = drop_fields(store, weighted["revision"], ["w"])
    assert after_drop_w.get("weights") is None

