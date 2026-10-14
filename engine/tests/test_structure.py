"""Immutable deletion tests for stable case and variable identity."""

from __future__ import annotations

import struct
from typing import Any

import pyarrow.parquet as pq
import pytest

from openstat_engine.errors import EngineError
from openstat_engine.store import Store, digest
from openstat_engine.structure import delete_cases, drop_fields


def structure_fields() -> list[dict[str, Any]]:
    return [
        {
            "id": "score",
            "name": "Score",
            "storage": "float64",
            "measurement": "continuous",
            "value_labels": {"1": "low"},
        },
        {
            "id": "group",
            "name": "Group",
            "storage": "string",
            "measurement": "ordinal",
            "levels": ["low", "high"],
            "missing_codes": ["?"],
            "value_labels": {"low": "Low", "high": "High"},
        },
        {
            "id": "responses",
            "name": "Responses",
            "storage": "multiple_response",
            "measurement": "multiple_response",
            "missing_codes": ["?"],
        },
    ]


def test_delete_cases_preserves_sparse_ids_values_metadata_and_source(
    store: Store,
) -> None:
    source = store.create(
        "Cases",
        structure_fields(),
        [[-0.0, "low", ["a"]], [1.25, "?", []], [2.5, "high", None], [3.75, "low", ["b"]]],
        context="sample",
        observation_unit="people",
    )
    original = store.get(source["revision"])
    base_hash = digest(original.base)
    edited = store.edit(source["revision"], 2, "score", 4.5)
    edited_source = store.get(edited["revision"])
    edited_base_hash = digest(edited_source.base)

    result = delete_cases(store, edited["revision"], [3, 1])
    current = store.get(result["revision"])
    assert result["id"] == source["id"]
    assert result["row_count"] == 2
    assert result["context"] == "sample"
    assert result["observation_unit"] == "people"
    assert current.edits == ()
    page = store.page(result["revision"])
    assert page["row_ids"] == [0, 2]
    assert page["rows"] == [[-0.0, "low", ["a"]], [4.5, "high", None]]
    assert struct.pack("<d", page["rows"][0][0]) == struct.pack("<d", -0.0)
    assert digest(original.base) == base_hash
    assert digest(edited_source.base) == edited_base_hash
    assert store.page(source["revision"])["row_ids"] == [0, 1, 2, 3]
    assert store.page(edited["revision"])["rows"][2][0] == 4.5


def test_delete_empty_and_all_cases_create_valid_revisions(store: Store) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []], [2.0, "high", None]])
    empty_request = delete_cases(store, source["revision"], [])
    assert empty_request["row_count"] == 2
    all_deleted = delete_cases(store, source["revision"], [0, 1])
    assert all_deleted["row_count"] == 0
    assert store.page(all_deleted["revision"])["rows"] == []
    assert store.page(all_deleted["revision"])["row_ids"] == []
    assert pq.ParquetFile(store.get(all_deleted["revision"]).base).metadata.num_rows == 0
    empty_without_field = drop_fields(store, all_deleted["revision"], ["group"])
    assert empty_without_field["row_count"] == 0
    assert [field.id for field in store.get(empty_without_field["revision"]).fields] == [
        "score",
        "responses",
    ]


@pytest.mark.parametrize(
    "row_ids,key",
    [
        (None, "error.inline_limit"),
        ([True], "error.row_id"),
        ([-1], "error.row_id"),
        ([0, 0], "error.row_id"),
        ([99], "error.row_id"),
    ],
)
def test_delete_cases_rejects_invalid_ids_without_recording_revision(
    store: Store, row_ids: Any, key: str
) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []]])
    with pytest.raises(EngineError, match=key):
        delete_cases(store, source["revision"], row_ids)
    assert len(store.revisions) == 1


def test_delete_cases_rejects_more_than_request_limit(store: Store) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []]])
    with pytest.raises(EngineError, match="error.inline_limit"):
        delete_cases(store, source["revision"], list(range(100_001)))
    assert len(store.revisions) == 1


def test_drop_fields_preserves_metadata_source_values_and_float_bits(store: Store) -> None:
    source = store.create(
        "Cases",
        structure_fields(),
        [[-0.0, "low", ["one", "two"]], [1.25, "high", None]],
        context="population",
        observation_unit="households",
    )
    original = store.get(source["revision"])
    base_hash = digest(original.base)
    edited = store.edit(source["revision"], 1, "score", -0.0)
    result = drop_fields(store, edited["revision"], ["group"])
    current = store.get(result["revision"])
    assert result["id"] == source["id"]
    assert result["context"] == "population"
    assert result["observation_unit"] == "households"
    assert [field.id for field in current.fields] == ["score", "responses"]
    assert current.fields[0].value_labels == {"1": "low"}
    assert current.edits == ()
    page = store.page(result["revision"])
    assert page["rows"] == [[-0.0, ["one", "two"]], [-0.0, None]]
    assert all(struct.pack("<d", row[0]) == struct.pack("<d", -0.0) for row in page["rows"])
    assert digest(original.base) == base_hash
    assert store.page(source["revision"])["rows"][0][1] == "low"
    assert [field.id for field in store.get(source["revision"]).fields] == [
        "score",
        "group",
        "responses",
    ]


@pytest.mark.parametrize(
    "fields,key",
    [
        (["missing"], "error.field_id"),
        (["score", "score"], "error.duplicate_fields"),
        (["score", "group", "responses"], "error.field_id"),
        ([1], "error.field_id"),
        (None, "error.field_id"),
    ],
)
def test_drop_fields_rejects_invalid_requests(store: Store, fields: Any, key: str) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []]])
    with pytest.raises(EngineError, match=key):
        drop_fields(store, source["revision"], fields)
    assert len(store.revisions) == 1


def test_drop_empty_field_list_copies_revision_and_retains_schema(store: Store) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []]])
    result = drop_fields(store, source["revision"], [])
    assert [field.id for field in store.get(result["revision"]).fields] == [
        "score",
        "group",
        "responses",
    ]
    assert store.page(result["revision"])["rows"] == [[1.0, "low", []]]


@pytest.mark.parametrize("operation", ["delete", "drop"])
def test_cancelled_operation_removes_partial_file_and_revision(
    store: Store, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []], [2.0, "high", []]])
    initial_files = set(store.directory.glob("*.parquet"))
    calls = 0

    def cancel(processed: int, total: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise EngineError("error.job_cancelled")

    monkeypatch.setattr("openstat_engine.structure.checkpoint", cancel)
    with pytest.raises(EngineError, match="error.job_cancelled"):
        if operation == "delete":
            delete_cases(store, source["revision"], [0])
        else:
            drop_fields(store, source["revision"], ["group"])
    assert len(store.revisions) == 1
    assert set(store.directory.glob("*.parquet")) == initial_files


def test_delete_cases_writer_failure_cleans_partial_file(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = store.create("Cases", structure_fields(), [[1.0, "low", []]])
    initial_files = set(store.directory.glob("*.parquet"))
    original_writer = pq.ParquetWriter

    class FailingWriter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.delegate = original_writer(*args, **kwargs)

        def __enter__(self) -> FailingWriter:
            self.delegate.__enter__()
            return self

        def write_table(self, *args: Any, **kwargs: Any) -> None:
            self.delegate.write_table(*args, **kwargs)
            raise OSError("disk full")

        def __exit__(self, *args: Any) -> Any:
            return self.delegate.__exit__(*args)

    monkeypatch.setattr("openstat_engine.structure.pq.ParquetWriter", FailingWriter)
    with pytest.raises(OSError, match="disk full"):
        delete_cases(store, source["revision"], [])
    assert len(store.revisions) == 1
    assert set(store.directory.glob("*.parquet")) == initial_files
