"""Immutable Parquet bases with sparse revision overlays and bounded paging."""

import copy
import hashlib
import json
import math
import os
import shutil
import sqlite3
import tempfile
import threading
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.parquet as pq

from .errors import EngineError
from .jobs import checkpoint
from .model import Field, validate_context, validate_fields

ROW_ID = "_openstat_row_id"
PAGE_LIMIT = 512
ARROW_TYPES = {
    "float64": pa.float64(),
    "int64": pa.int64(),
    "string": pa.string(),
    "bool": pa.bool_(),
    "multiple_response": pa.list_(pa.string()),
}


def atomic_json(path: Path, value: Any) -> None:
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staging = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def project_file(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise EngineError("error.project_path")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise EngineError("error.project_path")
    return target


@dataclass(frozen=True)
class Revision:
    id: str
    dataset_id: str
    name: str
    base: Path
    fields: tuple[Field, ...]
    row_count: int
    context: str = "unspecified"
    observation_unit: str = ""
    # Keyed by immutable base-row offset and field UUID. No full table copy on edit.
    edits: tuple[dict[str, Any], ...] = ()

    def descriptor(self) -> dict[str, Any]:
        return {
            "id": self.dataset_id,
            "revision": self.id,
            "name": self.name,
            "row_count": self.row_count,
            "fields": [f.to_dict() for f in self.fields],
            "context": self.context,
            "observation_unit": self.observation_unit,
        }


class Store:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.revisions: dict[str, Revision] = {}
        self._metadata_cache: OrderedDict[Path, tuple[int, int, Any, tuple[int, ...]]] = (
            OrderedDict()
        )
        self._metadata_lock = threading.RLock()

    def clear_metadata_cache(self) -> None:
        with self._metadata_lock:
            self._metadata_cache.clear()

    def _remember_metadata(self, base: Path, metadata: Any) -> tuple[int, ...]:
        stat = base.stat()
        offset = 0
        starts: list[int] = []
        for index in range(metadata.num_row_groups):
            starts.append(offset)
            offset += metadata.row_group(index).num_rows
        entry = (stat.st_size, stat.st_mtime_ns, metadata, tuple(starts))
        with self._metadata_lock:
            self._metadata_cache[base] = entry
            self._metadata_cache.move_to_end(base)
            while len(self._metadata_cache) > 2:
                self._metadata_cache.popitem(last=False)
        return entry[3]

    def _parquet(self, base: Path) -> Any:
        """Reuse immutable footer metadata, with a separate reader per concurrent scan."""
        stat = base.stat()
        with self._metadata_lock:
            cached = self._metadata_cache.get(base)
            if cached is not None and cached[:2] == (stat.st_size, stat.st_mtime_ns):
                self._metadata_cache.move_to_end(base)
                return pq.ParquetFile(base, metadata=cached[2])
        reader = pq.ParquetFile(base)
        self._remember_metadata(base, reader.metadata)
        return reader

    def _record(self, revision: Revision) -> dict[str, Any]:
        self.revisions[revision.id] = revision
        return revision.descriptor()

    def get(self, revision: str) -> Revision:
        try:
            return self.revisions[revision]
        except KeyError as exc:
            raise EngineError("error.stale_revision") from exc

    def _apply_edits(self, item: Revision, table: pa.Table) -> pa.Table:
        """Only changed columns leave Arrow; unchanged buffers keep their exact bits."""
        if not item.edits or table.num_rows == 0:
            return table
        by_field: dict[str, dict[int, Any]] = {}
        for edit in item.edits:
            if edit["field"] in table.column_names:
                by_field.setdefault(edit["field"], {})[edit["row"]] = edit["value"]
        if not by_field:
            return table
        positions = {identifier: i for i, identifier in enumerate(table[ROW_ID].to_pylist())}
        for field, changes in by_field.items():
            applicable = {
                positions[row]: value for row, value in changes.items() if row in positions
            }
            if applicable:
                values = table[field].to_pylist()
                for position, value in applicable.items():
                    values[position] = value
                index = table.schema.get_field_index(field)
                table = table.set_column(
                    index,
                    table.schema.field(index),
                    pa.array(values, type=table.schema.field(index).type),
                )
        return table

    def iter_tables(
        self, revision: str, columns: list[str] | None = None, batch_size: int = 8192
    ) -> Iterator[pa.Table]:
        """Scan current values in bounded batches, retaining the original case IDs."""
        item = self.get(revision)
        selected = columns if columns is not None else [f.id for f in item.fields]
        if type(batch_size) is not int or not 1 <= batch_size <= 8192:
            raise EngineError("error.page_bounds")
        if (
            not selected
            or len(set(selected)) != len(selected)
            or any(name not in {f.id for f in item.fields} for name in selected)
        ):
            raise EngineError("error.field_id")
        processed = 0
        checkpoint(0, item.row_count)
        for batch in self._parquet(item.base).iter_batches(
            batch_size=batch_size, columns=[ROW_ID, *selected]
        ):
            checkpoint(processed, item.row_count)
            yield self._apply_edits(item, pa.Table.from_batches([batch]))
            processed += batch.num_rows
        checkpoint(processed, item.row_count)

    def _has_row(self, base: Path, row: int) -> bool:
        parquet = self._parquet(base)
        for index in range(parquet.num_row_groups):
            stats = parquet.metadata.row_group(index).column(0).statistics
            if stats is not None and stats.has_min_max and not stats.min <= row <= stats.max:
                continue
            if row in parquet.read_row_group(index, columns=[ROW_ID])[ROW_ID].to_pylist():
                return True
        return False

    def _next_row_id(self, base: Path) -> int:
        parquet = self._parquet(base)
        maximum = -1
        for index in range(parquet.num_row_groups):
            stats = parquet.metadata.row_group(index).column(0).statistics
            if stats is not None and stats.has_min_max:
                maximum = max(maximum, stats.max)
            else:
                maximum = max(
                    (maximum, *parquet.read_row_group(index, columns=[ROW_ID])[ROW_ID].to_pylist())
                )
        return maximum + 1

    def _validate_row_ids(self, base: Path) -> None:
        """Validate untrusted case IDs with a disk index, not one Python object per case."""
        with tempfile.TemporaryDirectory(prefix="openstat-ids-", dir=self.directory) as temporary:
            database = sqlite3.connect(str(Path(temporary) / "ids.sqlite"))
            try:
                database.execute("PRAGMA journal_mode=OFF")
                database.execute("PRAGMA synchronous=OFF")
                database.execute("PRAGMA cache_size=-8192")
                database.execute("CREATE TABLE ids (id INTEGER PRIMARY KEY)")
                parquet = self._parquet(base)
                processed = 0
                for batch in parquet.iter_batches(batch_size=8192, columns=[ROW_ID]):
                    identifiers = batch.column(0).to_pylist()
                    if any(
                        type(identifier) is not int or identifier < 0 for identifier in identifiers
                    ):
                        raise EngineError("error.project_schema")
                    try:
                        database.executemany(
                            "INSERT INTO ids VALUES (?)",
                            ((identifier,) for identifier in identifiers),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise EngineError("error.project_schema") from exc
                    processed += len(identifiers)
                    checkpoint(processed, parquet.metadata.num_rows)
            finally:
                database.close()

    def create(
        self,
        name: str,
        fields: list[dict[str, Any]],
        rows: list[list[Any]],
        context: str = "unspecified",
        observation_unit: str = "",
    ) -> dict[str, Any]:
        validate_context(context)
        definitions = tuple(Field.from_dict(f) for f in fields)
        validate_fields(definitions)
        if len(rows) > 100_000:
            raise EngineError("error.inline_limit")
        if any(len(row) != len(definitions) for row in rows):
            raise EngineError("error.row_width")
        dataset_id, revision_id = str(uuid4()), str(uuid4())
        arrays = [pa.array(range(len(rows)), type=pa.int64())]
        for index, definition in enumerate(definitions):
            values = [self._value(definition, row[index]) for row in rows]
            arrays.append(pa.array(values, type=ARROW_TYPES[definition.storage]))
        table = pa.Table.from_arrays(arrays, names=[ROW_ID, *[f.id for f in definitions]])
        path = self.directory / f"{dataset_id}.parquet"
        pq.write_table(table, path, row_group_size=8192)
        return self._record(
            Revision(
                revision_id,
                dataset_id,
                name,
                path,
                definitions,
                len(rows),
                context,
                observation_unit,
            )
        )

    def extend(
        self, revision: str, fields: list[dict[str, Any]] | None = None, rows: int = 0
    ) -> dict[str, Any]:
        """Append nullable variables/cases without changing prior revision files or IDs."""
        item = self.get(revision)
        if type(rows) is not int or not 0 <= rows <= 100000:
            raise EngineError("error.inline_limit")
        additions = tuple(Field.from_dict(f) for f in (fields or []))
        definitions = (*item.fields, *additions)
        validate_fields(definitions)
        if not additions and rows == 0:
            raise EngineError("error.empty_change")
        schema = pa.schema(
            [(ROW_ID, pa.int64()), *[(f.id, ARROW_TYPES[f.storage]) for f in definitions]]
        )
        path = self.directory / f"{uuid4()}.parquet"
        next_id = self._next_row_id(item.base)
        if next_id + rows > 2**63:
            raise EngineError("error.integer_range")
        try:
            with pq.ParquetWriter(path, schema) as writer:
                for batch in self._parquet(item.base).iter_batches(batch_size=8192):
                    arrays = [
                        *batch.columns,
                        *[pa.nulls(batch.num_rows, type=ARROW_TYPES[f.storage]) for f in additions],
                    ]
                    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
                for start in range(next_id, next_id + rows, 8192):
                    count = min(8192, next_id + rows - start)
                    arrays = [
                        pa.array(range(start, start + count), type=pa.int64()),
                        *[pa.nulls(count, type=ARROW_TYPES[f.storage]) for f in definitions],
                    ]
                    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self._record(
            replace(
                item,
                id=str(uuid4()),
                base=path,
                fields=definitions,
                row_count=item.row_count + rows,
            )
        )

    @staticmethod
    def _value(definition: Field, value: Any) -> Any:
        if value is None:
            return None
        storage = definition.storage
        if storage == "string":
            if not isinstance(value, str):
                raise EngineError("error.value_type")
        elif storage == "bool":
            if not isinstance(value, bool):
                raise EngineError("error.value_type")
        elif storage == "int64":
            if isinstance(value, bool) or not isinstance(value, int):
                raise EngineError("error.value_type")
            if not -(2**63) <= value < 2**63:
                raise EngineError("error.integer_range")
        elif storage == "float64":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EngineError("error.value_type")
            if not math.isfinite(value):
                raise EngineError("error.nonfinite")
            value = float(value)
        else:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise EngineError("error.value_type")
            if len(set(value)) != len(value):
                raise EngineError("error.duplicate_response")
        if definition.levels:
            candidates = value if isinstance(value, list) else [str(value)]
            if any(
                v not in definition.levels and v not in definition.missing_codes for v in candidates
            ):
                raise EngineError("error.unknown_level")
        return copy.deepcopy(value)

    def page(
        self,
        revision: str,
        offset: int = 0,
        limit: int = 128,
        fields: list[str] | None = None,
        format: str = "json",
    ) -> dict[str, Any]:
        item = self.get(revision)
        if (
            type(offset) is not int
            or type(limit) is not int
            or offset < 0
            or not 1 <= limit <= PAGE_LIMIT
            or format not in {"json", "arrow"}
        ):
            raise EngineError("error.page_bounds")
        columns = fields if fields is not None else [f.id for f in item.fields]
        definitions = {f.id: f for f in item.fields}
        if (
            not columns
            or len(set(columns)) != len(columns)
            or any(f not in definitions for f in columns)
        ):
            raise EngineError("error.field_id")
        parquet = self._parquet(item.base)
        batches: list[Any] = []
        remaining = min(limit, max(0, item.row_count - offset))
        with self._metadata_lock:
            starts = self._metadata_cache.get(item.base, (0, 0, None, ()))[3]
        if not starts:
            starts = self._remember_metadata(item.base, parquet.metadata)
        first = max(0, bisect_right(starts, offset) - 1)
        start = starts[first] if starts else 0
        for index in range(first, parquet.num_row_groups):
            size = parquet.metadata.row_group(index).num_rows
            if start + size <= offset:
                start += size
                continue
            if remaining == 0:
                break
            local_offset = max(0, offset - start)
            count = min(size - local_offset, remaining)
            batches.append(
                parquet.read_row_group(index, columns=[ROW_ID, *columns]).slice(local_offset, count)
            )
            remaining -= count
            start += size
        schema = pa.schema(
            [
                (ROW_ID, pa.int64()),
                *[(field_id, ARROW_TYPES[definitions[field_id].storage]) for field_id in columns],
            ]
        )
        table = pa.concat_tables(batches) if batches else pa.Table.from_batches([], schema=schema)
        table = self._apply_edits(item, table)
        row_ids = table[ROW_ID].to_pylist()
        result: dict[str, Any] = {
            "revision": revision,
            "offset": offset,
            "count": table.num_rows,
            "row_ids": row_ids,
            "fields": columns,
            "format": format,
        }
        if format == "json":
            values = table.to_pydict()
            result["rows"] = [[values[f][i] for f in columns] for i in range(table.num_rows)]
        else:
            handle = str(uuid4())
            path = self.directory / f"{handle}.arrow"
            options = pa.ipc.IpcWriteOptions(
                metadata_version=pa.ipc.MetadataVersion.V5, compression=None
            )
            with (
                pa.OSFile(str(path), "wb") as sink,
                pa.ipc.new_file(sink, schema, options=options) as writer,
            ):
                writer.write_table(table)
            size = path.stat().st_size
            if size > 32 * 1024 * 1024:
                path.unlink()
                raise EngineError("error.arrow_limit")
            result["artifact"] = {
                "handle": handle,
                "path": str(path),
                "sha256": digest(path),
                "bytes": size,
            }
        return result

    def release(self, handle: str) -> dict[str, bool]:
        try:
            canonical = str(UUID(handle))
        except ValueError as exc:
            raise EngineError("error.artifact_handle") from exc
        (self.directory / f"{canonical}.arrow").unlink(missing_ok=True)
        return {"released": True}

    def edit(self, revision: str, row: int, field: str, value: Any) -> dict[str, Any]:
        item = self.get(revision)
        if type(row) is not int or row < 0 or not self._has_row(item.base, row):
            raise EngineError("error.row_id")
        definition = next((f for f in item.fields if f.id == field), None)
        if definition is None:
            raise EngineError("error.field_id")
        value = self._value(definition, value)
        edits = tuple(e for e in item.edits if (e["row"], e["field"]) != (row, field))
        return self._record(
            replace(
                item, id=str(uuid4()), edits=(*edits, {"row": row, "field": field, "value": value})
            )
        )

    def metadata(
        self,
        revision: str,
        fields: list[dict[str, Any]],
        context: str,
        observation_unit: str,
    ) -> dict[str, Any]:
        item = self.get(revision)
        validate_context(context)
        definitions = tuple(Field.from_dict(f) for f in fields)
        validate_fields(definitions)
        if [(f.id, f.storage) for f in definitions] != [(f.id, f.storage) for f in item.fields]:
            raise EngineError("error.storage_change")
        # A rename/role/context change cannot make stored values invalid. Narrowed
        # codebooks are checked by one streamed scan of only the affected fields.
        changed = [
            new
            for old, new in zip(item.fields, definitions, strict=True)
            if (old.levels, old.missing_codes) != (new.levels, new.missing_codes)
        ]
        if changed:
            for table in self.iter_tables(revision, [field.id for field in changed]):
                for definition in changed:
                    for value in table[definition.id].to_pylist():
                        self._value(definition, value)
        return self._record(
            replace(
                item,
                id=str(uuid4()),
                fields=definitions,
                context=context,
                observation_unit=observation_unit,
            )
        )

    def import_csv(
        self, path: str, delimiter: str = ",", decimal_point: str = "."
    ) -> dict[str, Any]:
        if len(delimiter) != 1 or decimal_point not in {".", ","} or delimiter == decimal_point:
            raise EngineError("error.csv_options")
        source = Path(path)
        reader = csv.open_csv(
            source,
            parse_options=csv.ParseOptions(delimiter=delimiter),
            convert_options=csv.ConvertOptions(decimal_point=decimal_point),
        )
        fields: list[Field] = []
        for column in reader.schema:
            if pa.types.is_integer(column.type):
                storage, measurement = "int64", "discrete"
            elif pa.types.is_floating(column.type):
                storage, measurement = "float64", "continuous"
            elif pa.types.is_boolean(column.type):
                storage, measurement = "bool", "binary"
            elif pa.types.is_string(column.type):
                storage, measurement = "string", "nominal"
            else:
                raise EngineError("error.csv_schema")
            fields.append(Field(str(uuid4()), column.name, storage, measurement))
        definitions = tuple(fields)
        validate_fields(definitions)
        dataset_id, revision_id = str(uuid4()), str(uuid4())
        destination = self.directory / f"{dataset_id}.parquet"
        schema = pa.schema(
            [(ROW_ID, pa.int64()), *[(f.id, ARROW_TYPES[f.storage]) for f in fields]]
        )
        count = 0
        try:
            with pq.ParquetWriter(destination, schema) as writer:
                for batch in reader:
                    checkpoint(0, 0)
                    arrays = [pa.array(range(count, count + batch.num_rows), type=pa.int64())]
                    for i, definition in enumerate(fields):
                        column = batch.column(i).cast(ARROW_TYPES[definition.storage])
                        if definition.storage == "float64":
                            if any(
                                v is not None and not math.isfinite(v) for v in column.to_pylist()
                            ):
                                raise EngineError("error.nonfinite")
                        arrays.append(column)
                    table = pa.Table.from_arrays(arrays, schema=schema)
                    writer.write_table(table, row_group_size=8192)
                    count += batch.num_rows
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return self._record(
            Revision(revision_id, dataset_id, source.stem, destination, definitions, count)
        )

    def save(self, revision: str, path: str) -> dict[str, str]:
        item = self.get(revision)
        root = Path(path)
        if root.suffix != ".openstat" or root.is_symlink():
            raise EngineError("error.project_path")
        root.mkdir(parents=True, exist_ok=True)
        checksum = digest(item.base)
        relative = f"data-{checksum}.parquet"
        target = project_file(root, relative)
        if not target.exists():
            staging = root / f".{uuid4()}.tmp"
            try:
                shutil.copyfile(item.base, staging)
                staging.replace(target)
            finally:
                staging.unlink(missing_ok=True)
        elif digest(target) != checksum:
            raise EngineError("error.checksum")
        edit_path = f"edits-{item.id}.json"
        atomic_json(project_file(root, edit_path), list(item.edits))
        manifest = {
            "format": "openstat",
            "format_version": 1,
            "dataset": item.descriptor(),
            "data": relative,
            "sha256": checksum,
            "edits": edit_path,
            "edits_sha256": digest(project_file(root, edit_path)),
            "analyses": [],
            "results": [],
            "workflows": [],
        }
        atomic_json(project_file(root, "manifest.json"), manifest)
        return {"path": str(root), "revision": revision}

    def open(self, path: str) -> dict[str, Any]:
        root = Path(path)
        manifest = json.loads(project_file(root, "manifest.json").read_text())
        if manifest.get("format") != "openstat" or manifest.get("format_version") != 1:
            raise EngineError("error.project_version")
        if any(manifest.get(name) for name in ("analyses", "results", "workflows")):
            # Refuse unsupported content instead of erasing it during a later save.
            raise EngineError("error.project_version")
        data = project_file(root, manifest["data"])
        edits_path = project_file(root, manifest["edits"])
        if digest(data) != manifest["sha256"] or digest(edits_path) != manifest["edits_sha256"]:
            raise EngineError("error.checksum")
        info = manifest["dataset"]
        if type(info["row_count"]) is not int or info["row_count"] < 0:
            raise EngineError("error.project_schema")
        fields = tuple(Field.from_dict(f) for f in info["fields"])
        validate_fields(fields)
        validate_context(info["context"])
        parquet = self._parquet(data)
        expected = pa.schema(
            [(ROW_ID, pa.int64()), *[(f.id, ARROW_TYPES[f.storage]) for f in fields]]
        )
        if (
            not parquet.schema_arrow.equals(expected)
            or parquet.metadata.num_rows != info["row_count"]
        ):
            raise EngineError("error.project_schema")
        self._validate_row_ids(data)
        edits = json.loads(edits_path.read_text())
        if not isinstance(edits, list):
            raise EngineError("error.project_schema")
        seen_edits: set[tuple[int, str]] = set()
        definitions = {f.id: f for f in fields}
        for edit in edits:
            if (
                not isinstance(edit, dict)
                or set(edit) != {"row", "field", "value"}
                or not isinstance(edit["field"], str)
                or edit["field"] not in definitions
                or type(edit["row"]) is not int
                or edit["row"] < 0
                or not self._has_row(data, edit["row"])
            ):
                raise EngineError("error.project_schema")
            key = (edit["row"], edit["field"])
            if key in seen_edits:
                raise EngineError("error.project_schema")
            seen_edits.add(key)
            self._value(definitions[edit["field"]], edit["value"])
        # A private base copy prevents later source replacement from mutating a session.
        private = self.directory / f"{uuid4()}.parquet"
        shutil.copyfile(data, private)
        self._remember_metadata(private, parquet.metadata)
        return self._record(
            Revision(
                info["revision"],
                info["id"],
                info["name"],
                private,
                fields,
                info["row_count"],
                info["context"],
                info["observation_unit"],
                tuple(edits),
            )
        )
