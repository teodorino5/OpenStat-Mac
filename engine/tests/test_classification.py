"""Independent classification/count fixtures and typed immutable-revision edge cases."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from openstat_engine.classification import categories, contingency, intervals, missing_audit
from openstat_engine.errors import EngineError
from openstat_engine.store import ROW_ID, Store

OUTPUT = {"id": "class", "name": "Class", "storage": "string", "measurement": "ordinal"}
NUMERIC = [{"id": "amount", "name": "Amount", "storage": "int64", "measurement": "discrete"}]
CLASSES = [
    {"label": "low", "lower": None, "upper": 0, "include_lower": False, "include_upper": False},
    {"label": "high", "lower": 0, "upper": None, "include_lower": True, "include_upper": False},
]


@pytest.mark.feature("DATA-016")
@pytest.mark.feature("DATA-017")
@pytest.mark.feature("DATA-018")
@pytest.mark.feature("DATA-019")
@pytest.mark.feature("DATA-020")
def test_original_classification_contract(
    store: Store, reference_fixture: Callable[[str], dict[str, Any]]
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/classification.json")
    source, expected = fixture["input"], fixture["expected"]
    original = store.create("Original", source["fields"], source["rows"])
    revision = original["revision"]
    mapped = categories(store, revision, "amount", OUTPUT, source["mapping"])
    finite = intervals(store, revision, "amount", OUTPUT, source["classes"])
    opened = intervals(store, revision, "amount", OUTPUT, source["open_classes"])
    for result, key in [
        (mapped, "category_labels"),
        (finite, "interval_labels"),
        (opened, "interval_labels"),
    ]:
        page = store.page(result["revision"])
        assert page["row_ids"] == expected["row_ids"]
        assert [row[-1] for row in page["rows"]] == expected[key]
        assert [row[:-1] for row in page["rows"]] == store.page(revision)["rows"]
        assert result["id"] == original["id"]
    table = contingency(store, finite["revision"], "group", "class")
    membership = contingency(store, revision, "group", "response", "response_membership")
    for actual, key in [(table, "exclusive"), (membership, "membership")]:
        for field, value in expected[key].items():
            assert actual[field] == value
    assert table["row_levels"] == ["A", "B"]
    assert table["column_levels"] == ["low", "middle", "high"]
    assert table["denominator"] == "eligible_cases"
    assert membership["denominator"] == "response_pairs"
    audit = missing_audit(store, revision)
    assert audit["fields"] == expected["audit"]
    assert audit["complete_cases"] == expected["complete_cases"]
    assert audit["total_cases"] == 9
    assert audit["denominator"] == "total_cases"
    assert audit["pattern_fields"] == expected["pattern_fields"]
    assert audit["patterns"] == expected["patterns"]
    assert store.get(revision).fields == tuple(store.get(mapped["revision"]).fields[:-1])


def test_overlay_batches_and_noncontiguous_identity(store: Store) -> None:
    original = store.create("Large", NUMERIC, [[index] for index in range(8200)])
    edited = store.edit(original["revision"], 8194, "amount", -2)
    item = store.get(edited["revision"])
    changed = intervals(store, item.id, "amount", OUTPUT, CLASSES)
    assert store.get(changed["revision"]).edits == ()
    assert store.page(changed["revision"], 8190, 10)["rows"][4] == [-2, "low"]
    assert store.page(original["revision"], 8190, 10)["rows"][4] == [8194]
    # Construct a valid noncontiguous row-ID base independently of filter implementation.
    path = store.directory / "selected.parquet"
    pq.write_table(pa.table({ROW_ID: pa.array([4, 9], type=pa.int64()), "amount": [0, -1]}), path)
    selected = replace(item, id="selected", base=path, row_count=2, edits=())
    store._record(selected)
    result = intervals(store, selected.id, "amount", OUTPUT, CLASSES)
    assert store.page(result["revision"])["row_ids"] == [4, 9]
    assert store.page(result["revision"])["rows"] == [[0, "high"], [-1, "low"]]


def test_empty_and_unmatched(store: Store) -> None:
    empty = store.create("Empty", NUMERIC, [])
    result = intervals(store, empty["revision"], "amount", OUTPUT, CLASSES)
    assert store.page(result["revision"])["rows"] == []
    assert missing_audit(store, empty["revision"])["complete_cases"] == 0
    data = store.create("Data", NUMERIC, [[0], [1]])
    mapping = [{"value": 0, "label": "zero"}]
    before = set(store.directory.iterdir())
    with pytest.raises(EngineError, match="error.classification_unmatched"):
        categories(store, data["revision"], "amount", OUTPUT, mapping)
    assert set(store.directory.iterdir()) == before
    result = categories(store, data["revision"], "amount", OUTPUT, mapping, "missing")
    assert store.page(result["revision"])["rows"] == [[0, "zero"], [1, None]]
    with pytest.raises(EngineError, match="error.classification_options"):
        categories(store, data["revision"], "amount", OUTPUT, mapping, "guess")


@pytest.mark.parametrize(
    "mapping",
    [
        [],
        [{"value": 0, "label": ""}],
        [{"value": 0, "label": 1}],
        [{"value": 0, "label": "a", "extra": 1}],
        [{"value": None, "label": "a"}],
        [{"value": 0, "label": "a"}, {"value": 0, "label": "b"}],
    ],
)
def test_invalid_mapping(store: Store, mapping: list[dict[str, Any]]) -> None:
    data = store.create("Data", NUMERIC, [[0]])
    with pytest.raises(EngineError):
        categories(store, data["revision"], "amount", OUTPUT, mapping)


@pytest.mark.parametrize(
    "patch",
    [
        {"storage": "int64", "measurement": "discrete"},
        {"measurement": "binary", "levels": ["a", "b"]},
        {"role": "identifier"},
        {"missing_codes": ["NA"]},
        {"levels": ["different"]},
        {"id": "amount"},
        {"name": "Amount"},
    ],
)
def test_invalid_output(store: Store, patch: dict[str, Any]) -> None:
    data = store.create("Data", NUMERIC, [[0]])
    with pytest.raises(EngineError):
        intervals(store, data["revision"], "amount", {**OUTPUT, **patch}, CLASSES)


@pytest.mark.parametrize(
    "patch",
    [
        {"label": ""},
        {"label": 2},
        {"include_lower": 1},
        {"include_upper": "yes"},
        {"lower": True},
        {"lower": float("inf")},
        {"upper": float("nan")},
        {"include_lower": True},
        {"lower": 0, "upper": 0},
        {"lower": 2, "upper": 1},
        {"extra": 1},
    ],
)
def test_invalid_interval_options(store: Store, patch: dict[str, Any]) -> None:
    data = store.create("Data", NUMERIC, [[0]])
    with pytest.raises(EngineError):
        intervals(store, data["revision"], "amount", OUTPUT, [{**CLASSES[0], **patch}])


def test_interval_order_overlap_gaps_and_int64(store: Store) -> None:
    data = store.create("Data", NUMERIC, [[-(2**63)], [0], [2**63 - 1]])
    result = intervals(store, data["revision"], "amount", OUTPUT, CLASSES)
    assert store.page(result["revision"])["rows"] == [
        [-(2**63), "low"],
        [0, "high"],
        [2**63 - 1, "high"],
    ]
    for definitions in [
        [],
        list(reversed(CLASSES)),
        [CLASSES[0], CLASSES[0]],
        [{**CLASSES[0], "include_upper": True}, CLASSES[1]],
        [CLASSES[0], {**CLASSES[1], "lower": -1}],
        [{**CLASSES[0], "upper": None}, CLASSES[1]],
        [{**CLASSES[1], "include_upper": True}],
    ]:
        with pytest.raises(EngineError):
            intervals(store, data["revision"], "amount", OUTPUT, definitions)
    gap = [{**CLASSES[0], "upper": -1}, {**CLASSES[1], "lower": 1}]
    result = intervals(store, data["revision"], "amount", OUTPUT, gap, "missing")
    assert [row[-1] for row in store.page(result["revision"])["rows"]] == ["low", None, "high"]
    right_closed = [{**CLASSES[0], "include_upper": True}, {**CLASSES[1], "include_lower": False}]
    result = intervals(store, data["revision"], "amount", OUTPUT, right_closed)
    assert store.page(result["revision"])["rows"][1][-1] == "low"


def test_sources_codes_modes_and_audit_selection(store: Store) -> None:
    definitions = [
        {
            "id": "label",
            "name": "Label",
            "storage": "string",
            "measurement": "nominal",
            "missing_codes": ["NA"],
        },
        {
            "id": "response",
            "name": "Response",
            "storage": "multiple_response",
            "measurement": "multiple_response",
        },
        {"id": "boolean", "name": "Boolean", "storage": "bool", "measurement": "binary"},
        {**NUMERIC[0], "role": "identifier"},
    ]
    data = store.create(
        "Data",
        definitions,
        [["x", ["a", "b"], True, 0], ["y", [], False, 1], ["NA", None, None, 2]],
    )
    revision = data["revision"]
    with pytest.raises(EngineError, match="error.field_id"):
        missing_audit(store, revision, ["absent"])
    for fields in [[], ["label", "label"]]:
        with pytest.raises(EngineError, match="error.field_id"):
            missing_audit(store, revision, fields)
    audit_label = missing_audit(store, revision, ["label"])
    assert audit_label["fields"] == {
        "label": {"null": 0, "coded_missing": 1, "valid": 2, "empty_response": 0}
    }
    assert audit_label["patterns"] == [
        {"pattern": {"label": "valid"}, "kinds": ["valid"], "count": 2, "complete": True},
        {
            "pattern": {"label": "coded_missing"},
            "kinds": ["coded_missing"],
            "count": 1,
            "complete": False,
        },
    ]
    for source in ["label", "response"]:
        with pytest.raises(EngineError, match="error.classification_source"):
            intervals(store, revision, source, OUTPUT, CLASSES)
    with pytest.raises(EngineError, match="error.classification_source"):
        categories(store, revision, "response", OUTPUT, [{"value": [], "label": "x"}])
    with pytest.raises(EngineError, match="error.classification_options"):
        categories(store, revision, "label", OUTPUT, [{"value": "NA", "label": "x"}])
    for mode in ["exclusive", "unknown"]:
        with pytest.raises(EngineError, match="error.contingency_mode"):
            contingency(store, revision, "label", "response", mode)
    with pytest.raises(EngineError, match="error.contingency_source"):
        contingency(store, revision, "amount", "label")
    table = contingency(store, revision, "label", "boolean")
    assert table["row_levels"] == ["x", "y"]
    assert table["column_levels"] == ["True", "False"]
    assert table["counts"] == [[1, 0], [0, 1]]
    table = contingency(store, revision, "response", "response", "response_membership")
    assert table["counts"] == [[1, 1], [1, 1]]
    assert table["eligible_cases"] == 2
    assert table["pair_count"] == 4
    assert table["empty_response_cases"] == 1
    mapped = categories(
        store,
        revision,
        "boolean",
        {**OUTPUT, "levels": ["yes", "no"]},
        [{"value": True, "label": "yes"}, {"value": False, "label": "no"}],
    )
    assert [row[-1] for row in store.page(mapped["revision"])["rows"]] == ["yes", "no", None]


def test_contingency_size_limit(store: Store) -> None:
    levels = [str(value) for value in range(1001)]
    fields = [
        {
            "id": source,
            "name": source,
            "storage": "string",
            "measurement": "nominal",
            "levels": levels,
        }
        for source in ["a", "b"]
    ]
    for rows in [[], [["0", "0"]]]:
        dataset = store.create("Too wide", fields, rows)
        with pytest.raises(EngineError, match="error.classification_limit"):
            contingency(store, dataset["revision"], "a", "b")


def test_extreme_bounds_and_missing_all_rows(store: Store) -> None:
    dataset = store.create("Extremes", NUMERIC, [[0], [1]])
    huge = [
        {
            "label": "inside",
            "lower": -(10**1000),
            "upper": 10**1000,
            "include_lower": True,
            "include_upper": True,
        }
    ]
    classified = intervals(store, dataset["revision"], "amount", OUTPUT, huge)
    assert [row[-1] for row in store.page(classified["revision"])["rows"]] == ["inside", "inside"]
    fields = [
        {
            "id": "a",
            "name": "A",
            "storage": "string",
            "measurement": "nominal",
            "missing_codes": ["NA"],
        }
    ]
    missing = store.create("Missing", fields, [[None], ["NA"]])
    table = contingency(store, missing["revision"], "a", "a")
    assert table["counts"] == []
    assert table["row_totals"] == table["column_totals"] == []
    assert table["eligible_cases"] == table["pair_count"] == 0
    assert table["excluded_null_cases"] == table["excluded_coded_missing_cases"] == 1
