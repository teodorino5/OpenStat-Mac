"""Explicit, atomic interchange contracts for typed Phase 0 datasets.

Parquet and SQLite carry the complete codebook. JSON is a bounded portable snapshot.
Flat text exports are deliberately lossy and report their limitations to callers.
"""

import csv
import json
import os
import sqlite3
import struct
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .errors import EngineError
from .model import Field, validate_context, validate_fields
from .store import ARROW_TYPES, ROW_ID, Revision, Store

BATCH_ROWS = 8192
JSON_LIMIT = 32 * 1024 * 1024
METADATA_LIMIT = 1024 * 1024
METADATA_KEY = b"openstat.interchange.v1"
FORMAT = "openstat-data"


def _schema(fields: tuple[Field, ...]) -> Any:
    return pa.schema([(ROW_ID, pa.int64()), *[(f.id, ARROW_TYPES[f.storage]) for f in fields]])


def _metadata(item: Revision) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "version": 1,
        "dataset": {
            "name": item.name,
            "fields": [f.to_dict() for f in item.fields],
            "context": item.context,
            "observation_unit": item.observation_unit,
        },
    }


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _decode(raw: str | bytes) -> Any:
    def forbidden(value: str) -> Any:
        raise EngineError("error.nonfinite")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EngineError("error.interchange_schema")
            result[key] = value
        return result

    try:
        return json.loads(raw, parse_constant=forbidden, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EngineError("error.interchange_schema") from exc


def _definitions(value: Any) -> tuple[str, tuple[Field, ...], str, str]:
    try:
        if value["format"] != FORMAT or type(value["version"]) is not int or value["version"] != 1:
            raise EngineError("error.interchange_schema")
        dataset = value["dataset"]
        name, context, unit = dataset["name"], dataset["context"], dataset["observation_unit"]
        if not all(isinstance(v, str) for v in (name, context, unit)) or not name.strip():
            raise EngineError("error.interchange_schema")
        raw_fields = dataset["fields"]
        if not isinstance(raw_fields, list) or len(raw_fields) > 1024:
            raise EngineError("error.interchange_schema")
        # Reject coercion of untrusted metadata into a different storage contract.
        for f in raw_fields:
            if not isinstance(f, dict) or not all(
                isinstance(f.get(key), str) for key in ("id", "name", "storage", "measurement")
            ):
                raise EngineError("error.interchange_schema")
            if not isinstance(f.get("levels", []), list) or not all(
                isinstance(v, str) for v in f.get("levels", [])
            ):
                raise EngineError("error.interchange_schema")
            if not isinstance(f.get("missing_codes", []), list) or not all(
                isinstance(v, str) for v in f.get("missing_codes", [])
            ):
                raise EngineError("error.interchange_schema")
            if not isinstance(f.get("value_labels", {}), dict) or not all(
                isinstance(k, str) and isinstance(v, str)
                for k, v in f.get("value_labels", {}).items()
            ):
                raise EngineError("error.interchange_schema")
        fields = tuple(Field.from_dict(f) for f in raw_fields)
        validate_fields(fields)
        validate_context(context)
        return name, fields, context, unit
    except (KeyError, TypeError, AttributeError) as exc:
        raise EngineError("error.interchange_schema") from exc


@contextmanager
def _destination(store: Store, path: str, overwrite: bool) -> Iterator[Path]:
    target = Path(path).absolute()
    if type(overwrite) is not bool or target.is_symlink() or not target.parent.is_dir():
        raise EngineError("error.export_path")
    if target.exists() and (not overwrite or not target.is_file()):
        raise EngineError("error.export_exists")
    protected = [r.base.resolve() for r in store.revisions.values()]
    if target.resolve() in protected or target.resolve().is_relative_to(store.directory.resolve()):
        raise EngineError("error.export_path")
    fd, temporary = tempfile.mkstemp(prefix=".openstat-export-", dir=target.parent)
    os.close(fd)
    staging = Path(temporary)
    try:
        yield staging
        with staging.open("rb") as stream:
            os.fsync(stream.fileno())
        if overwrite:
            if target.is_symlink():
                raise EngineError("error.export_path")
            staging.replace(target)
        else:
            try:
                os.link(staging, target)
            except FileExistsError as exc:
                raise EngineError("error.export_exists") from exc
    finally:
        staging.unlink(missing_ok=True)


def _batches(store: Store, item: Revision) -> Iterator[Any]:
    yield from store.iter_tables(item.id, batch_size=BATCH_ROWS)


def _import_batches(
    store: Store,
    metadata: Any,
    batches: Iterator[Any],
) -> dict[str, Any]:
    name, fields, context, unit = _definitions(metadata)
    schema = _schema(fields)
    destination = store.directory / f"{uuid4()}.parquet"
    count = 0
    identity_path = store.directory / f"{uuid4()}.sqlite"
    try:
        with (
            closing(sqlite3.connect(identity_path)) as identities,
            pq.ParquetWriter(destination, schema) as writer,
        ):
            identities.execute("CREATE TABLE ids (value INTEGER PRIMARY KEY)")
            for batch in batches:
                if not batch.schema.equals(schema, check_metadata=False):
                    raise EngineError("error.interchange_schema")
                values = batch.to_pydict()
                ids = values[ROW_ID]
                if any(type(v) is not int or v < 0 for v in ids):
                    raise EngineError("error.interchange_schema")
                try:
                    identities.executemany("INSERT INTO ids VALUES (?)", ((v,) for v in ids))
                except sqlite3.IntegrityError as exc:
                    raise EngineError("error.interchange_schema") from exc
                for field in fields:
                    for value in values[field.id]:
                        store._value(field, value)
                writer.write_table(pa.Table.from_pydict(values, schema=schema))
                count += batch.num_rows
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        identity_path.unlink(missing_ok=True)
    return store._record(
        Revision(str(uuid4()), str(uuid4()), name, destination, fields, count, context, unit)
    )


def export_csv(
    store: Store,
    revision: str,
    path: str,
    delimiter: str = ",",
    decimal_point: str = ".",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write UTF-8 CSV/TSV with shortest-roundtrip floats and explicit loss reporting."""
    if delimiter not in {",", "\t", ";"} or decimal_point not in {".", ","}:
        raise EngineError("error.csv_options")
    if delimiter == decimal_point:
        raise EngineError("error.csv_options")
    item = store.get(revision)
    with (
        _destination(store, path, overwrite) as staging,
        staging.open("w", encoding="utf-8", newline="") as stream,
    ):
        writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
        writer.writerow([f.name for f in item.fields])
        for batch in _batches(store, item):
            values = batch.to_pydict()
            for row in range(batch.num_rows):
                rendered: list[str] = []
                for field in item.fields:
                    value = values[field.id][row]
                    if value is None:
                        text = ""
                    elif field.storage == "multiple_response":
                        text = _encode(value)
                    elif field.storage == "bool":
                        text = "true" if value else "false"
                    else:
                        text = str(value)
                        if field.storage == "float64":
                            text = text.replace(".", decimal_point)
                    rendered.append(text)
                writer.writerow(rendered)
    return {
        "path": str(Path(path).absolute()),
        "rows": item.row_count,
        "losses": [
            "codebook",
            "field_ids",
            "context",
            "null_empty_string_distinction",
            "multiple_response_type",
        ],
    }


def export_parquet(
    store: Store,
    revision: str,
    path: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    item = store.get(revision)
    metadata = _encode(_metadata(item)).encode()
    _definitions(_decode(metadata))
    if len(metadata) > METADATA_LIMIT:
        raise EngineError("error.interchange_limit")
    schema = _schema(item.fields).with_metadata({METADATA_KEY: metadata})
    with (
        _destination(store, path, overwrite) as staging,
        pq.ParquetWriter(staging, schema) as writer,
    ):
        for batch in _batches(store, item):
            writer.write_table(batch.replace_schema_metadata(schema.metadata))
    return {"path": str(Path(path).absolute()), "rows": item.row_count, "losses": []}


def import_parquet(store: Store, path: str) -> dict[str, Any]:
    source = pq.ParquetFile(
        path, thrift_string_size_limit=METADATA_LIMIT, thrift_container_size_limit=METADATA_LIMIT
    )
    raw = (source.schema_arrow.metadata or {}).get(METADATA_KEY)
    if raw is None:
        fields: list[Field] = []
        for column in source.schema_arrow:
            candidates = [
                storage for storage, arrow_type in ARROW_TYPES.items() if column.type == arrow_type
            ]
            if not candidates or column.name.startswith("_openstat_"):
                raise EngineError("error.interchange_schema")
            storage = candidates[0]
            measurement = {
                "int64": "discrete",
                "float64": "continuous",
                "bool": "binary",
                "multiple_response": "multiple_response",
            }.get(storage, "nominal")
            fields.append(Field(str(uuid4()), column.name, storage, measurement))
        validate_fields(tuple(fields))
        dummy = Revision("", "", Path(path).stem, Path(path), tuple(fields), 0)
        metadata = _decode(_encode(_metadata(dummy)))

        def converted() -> Iterator[Any]:
            offset = 0
            for batch in source.iter_batches(batch_size=BATCH_ROWS):
                arrays = [
                    pa.array(range(offset, offset + batch.num_rows), type=pa.int64()),
                    *batch.columns,
                ]
                yield pa.Table.from_arrays(arrays, schema=_schema(tuple(fields)))
                offset += batch.num_rows

        return _import_batches(store, metadata, converted())
    if len(raw) > METADATA_LIMIT:
        raise EngineError("error.interchange_limit")
    return _import_batches(store, _decode(raw), iter(source.iter_batches(batch_size=BATCH_ROWS)))


def export_json(
    store: Store,
    revision: str,
    path: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    item = store.get(revision)
    metadata = _encode(_metadata(item))
    _definitions(_decode(metadata))
    if len(metadata.encode()) > METADATA_LIMIT:
        raise EngineError("error.interchange_limit")
    if item.row_count > JSON_LIMIT // 4:
        raise EngineError("error.interchange_limit")
    with _destination(store, path, overwrite) as staging, staging.open("wb") as stream:
        prefix = metadata[:-1] + ',"row_ids":['
        stream.write(prefix.encode("utf-8"))
        first_id = True
        for batch in _batches(store, item):
            for row_id in batch.column(ROW_ID).to_pylist():
                stream.write((b"" if first_id else b",") + str(row_id).encode())
                first_id = False
                if stream.tell() + 12 > JSON_LIMIT:
                    raise EngineError("error.interchange_limit")
        stream.write(b'],"rows":[')
        first = True
        for batch in _batches(store, item):
            values = batch.to_pydict()
            for row in range(batch.num_rows):
                encoded = _encode([values[f.id][row] for f in item.fields]).encode("utf-8")
                stream.write((b"" if first else b",") + encoded)
                first = False
                if stream.tell() + 2 > JSON_LIMIT:
                    raise EngineError("error.interchange_limit")
        stream.write(b"]}")
        if stream.tell() > JSON_LIMIT:
            raise EngineError("error.interchange_limit")
    return {"path": str(Path(path).absolute()), "rows": item.row_count, "losses": []}


def import_json(store: Store, path: str) -> dict[str, Any]:
    with Path(path).open("rb") as stream:
        raw = stream.read(JSON_LIMIT + 1)
    if len(raw) > JSON_LIMIT:
        raise EngineError("error.interchange_limit")
    value = _decode(raw)
    _, fields, _, _ = _definitions(value)
    rows = value.get("rows")
    ids = value.get("row_ids")
    if not isinstance(rows, list) or not isinstance(ids, list) or len(ids) != len(rows):
        raise EngineError("error.interchange_schema")

    def batches() -> Iterator[Any]:
        for offset in range(0, len(rows), BATCH_ROWS):
            part = rows[offset : offset + BATCH_ROWS]
            if any(not isinstance(row, list) or len(row) != len(fields) for row in part):
                raise EngineError("error.row_width")
            selected_ids = ids[offset : offset + len(part)]
            if any(type(v) is not int or not 0 <= v < 2**63 for v in selected_ids):
                raise EngineError("error.interchange_schema")
            arrays = [pa.array(selected_ids, type=pa.int64())]
            for index, field in enumerate(fields):
                values = [store._value(field, row[index]) for row in part]
                arrays.append(pa.array(values, type=ARROW_TYPES[field.storage]))
            yield pa.Table.from_arrays(arrays, schema=_schema(fields))

    return _import_batches(store, value, batches())


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def export_sqlite(
    store: Store,
    revision: str,
    path: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    item = store.get(revision)
    metadata = _encode(_metadata(item))
    _definitions(_decode(metadata))
    if len(metadata.encode()) > METADATA_LIMIT:
        raise EngineError("error.interchange_limit")
    columns = [ROW_ID, *[f.id for f in item.fields]]
    with (
        _destination(store, path, overwrite) as staging,
        closing(sqlite3.connect(staging)) as connection,
    ):
        connection.execute('CREATE TABLE "_openstat_metadata" ("document" TEXT NOT NULL)')
        connection.execute('INSERT INTO "_openstat_metadata" VALUES (?)', (metadata,))
        types = {
            "int64": "INTEGER",
            "float64": "BLOB",
            "bool": "INTEGER",
            "string": "TEXT",
            "multiple_response": "TEXT",
        }
        definition = [
            "_openstat_position INTEGER PRIMARY KEY",
            f"{_quote(ROW_ID)} INTEGER NOT NULL UNIQUE",
            *[f"{_quote(f.id)} {types[f.storage]}" for f in item.fields],
        ]
        connection.execute('CREATE TABLE "_openstat_data" (' + ",".join(definition) + ")")
        insert = (
            'INSERT INTO "_openstat_data" VALUES ('
            + ",".join("?" for _ in range(len(columns) + 1))
            + ")"
        )
        position = 0
        for batch in _batches(store, item):
            values = batch.to_pydict()
            records = []
            for row in range(batch.num_rows):
                record = [position, values[ROW_ID][row]]
                position += 1
                for field in item.fields:
                    cell = values[field.id][row]
                    if cell is not None and field.storage == "multiple_response":
                        cell = _encode(cell)
                    # SQLite REAL canonicalizes negative zero. Preserve float bit patterns as blobs.
                    if cell is not None and field.storage == "float64":
                        cell = struct.pack("<d", cell)
                    record.append(cell)
                records.append(record)
            connection.executemany(insert, records)
        connection.commit()
    return {"path": str(Path(path).absolute()), "rows": item.row_count, "losses": []}


def import_sqlite(store: Store, path: str) -> dict[str, Any]:
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.enable_load_extension(False)
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA query_only=ON")
            tables = dict(
                connection.execute(
                    "SELECT name,type FROM sqlite_schema WHERE name IN (?,?)",
                    ("_openstat_metadata", "_openstat_data"),
                )
            )
            if tables != {"_openstat_metadata": "table", "_openstat_data": "table"}:
                raise EngineError("error.interchange_schema")
            sizes = connection.execute(
                'SELECT typeof("document"), length(CAST("document" AS BLOB)) '
                'FROM "_openstat_metadata" LIMIT 2'
            ).fetchall()
            if len(sizes) != 1 or sizes[0][0] != "text":
                raise EngineError("error.interchange_schema")
            if sizes[0][1] > METADATA_LIMIT:
                raise EngineError("error.interchange_limit")
            metadata_rows = connection.execute(
                'SELECT "document" FROM "_openstat_metadata" LIMIT 1'
            ).fetchall()
            metadata = _decode(metadata_rows[0][0])
            _, fields, _, _ = _definitions(metadata)
            actual = [row[1] for row in connection.execute('PRAGMA table_info("_openstat_data")')]
            columns = [ROW_ID, *[f.id for f in fields]]
            if actual != ["_openstat_position", *columns]:
                raise EngineError("error.interchange_schema")
            cursor = connection.execute(
                "SELECT "
                + ",".join(_quote(c) for c in columns)
                + ' FROM "_openstat_data" ORDER BY '
                + '"_openstat_position"'
            )

            def batches() -> Iterator[Any]:
                while records := cursor.fetchmany(BATCH_ROWS):
                    arrays = [pa.array([row[0] for row in records], type=pa.int64())]
                    for index, field in enumerate(fields, 1):
                        values = []
                        for row in records:
                            cell = row[index]
                            if cell is not None and field.storage == "multiple_response":
                                if not isinstance(cell, str):
                                    raise EngineError("error.interchange_schema")
                                cell = _decode(cell)
                            if cell is not None and field.storage == "float64":
                                if not isinstance(cell, bytes) or len(cell) != 8:
                                    raise EngineError("error.interchange_schema")
                                cell = struct.unpack("<d", cell)[0]
                            if cell is not None and field.storage == "bool":
                                if type(cell) is not int or cell not in (0, 1):
                                    raise EngineError("error.value_type")
                                cell = bool(cell)
                            values.append(store._value(field, cell))
                        arrays.append(pa.array(values, type=ARROW_TYPES[field.storage]))
                    yield pa.Table.from_arrays(arrays, schema=_schema(fields))

            return _import_batches(store, metadata, batches())
    except (sqlite3.Error, pa.ArrowException) as exc:
        raise EngineError("error.interchange_schema") from exc
