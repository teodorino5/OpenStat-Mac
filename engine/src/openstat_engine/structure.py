"""Immutable case and variable removal operations."""

from __future__ import annotations

from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .errors import EngineError
from .jobs import checkpoint
from .store import ROW_ID, Revision, Store

MAX_DELETE_IDS = 100_000


def delete_cases(store: Store, revision: str, row_ids: list[int]) -> dict[str, object]:
    """Create a revision without requested stable case IDs."""
    item = store.get(revision)
    if not isinstance(row_ids, list) or len(row_ids) > MAX_DELETE_IDS:
        raise EngineError("error.inline_limit")
    if any(type(row_id) is not int or row_id < 0 for row_id in row_ids):
        raise EngineError("error.row_id")
    requested = set(row_ids)
    if len(requested) != len(row_ids):
        raise EngineError("error.row_id")

    target = store.directory / f"{uuid4()}.parquet"
    remaining = set(requested)
    count = 0
    processed = 0
    schema = store._parquet(item.base).schema_arrow
    try:
        with pq.ParquetWriter(target, schema) as writer:
            checkpoint(0, item.row_count)
            for table in store.iter_tables(revision):
                identifiers = table[ROW_ID].to_pylist()
                keep: list[bool] = []
                for identifier in identifiers:
                    matched = identifier in requested
                    if matched:
                        remaining.discard(identifier)
                    keep.append(not matched)
                retained = table.filter(pa.array(keep, type=pa.bool_()))
                if retained.num_rows:
                    writer.write_table(retained, row_group_size=8192)
                count += retained.num_rows
                processed += table.num_rows
                checkpoint(processed, item.row_count)
        if remaining:
            raise EngineError("error.row_id")
        checkpoint(processed, item.row_count)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return store._record(
        Revision(
            str(uuid4()),
            item.dataset_id,
            item.name,
            target,
            item.fields,
            count,
            item.context,
            item.observation_unit,
            (),
        )
    )


def drop_fields(store: Store, revision: str, fields: list[str]) -> dict[str, object]:
    """Create a revision without selected variable IDs, preserving remaining values."""
    item = store.get(revision)
    if not isinstance(fields, list) or any(not isinstance(field, str) for field in fields):
        raise EngineError("error.field_id")
    requested = set(fields)
    if len(requested) != len(fields):
        raise EngineError("error.duplicate_fields")
    known = {field.id for field in item.fields}
    if not requested <= known:
        raise EngineError("error.field_id")
    retained_fields = tuple(field for field in item.fields if field.id not in requested)
    if not retained_fields:
        raise EngineError("error.field_id")

    item_schema = store._parquet(item.base).schema_arrow
    names = [ROW_ID, *(field.id for field in retained_fields)]
    schema = pa.schema([item_schema.field(name) for name in names], metadata=item_schema.metadata)
    target = store.directory / f"{uuid4()}.parquet"
    processed = 0
    try:
        with pq.ParquetWriter(target, schema) as writer:
            checkpoint(0, item.row_count)
            for table in store.iter_tables(revision, columns=[field.id for field in item.fields]):
                selected = table.select(names)
                if selected.num_rows:
                    writer.write_table(selected, row_group_size=8192)
                processed += table.num_rows
                checkpoint(processed, item.row_count)
        checkpoint(processed, item.row_count)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return store._record(
        Revision(
            str(uuid4()),
            item.dataset_id,
            item.name,
            target,
            retained_fields,
            item.row_count,
            item.context,
            item.observation_unit,
            (),
        )
    )
