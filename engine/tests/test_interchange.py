"""Original literal interoperability fixtures; no external vendor data."""

import csv
import json
import math
import sqlite3
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from openstat_engine import interchange as io
from openstat_engine.errors import EngineError
from openstat_engine.store import ROW_ID, Store

FIELDS = [
    {"id": "int", "name": "Integer", "storage": "int64", "measurement": "discrete"},
    {"id": "float", "name": "Float", "storage": "float64", "measurement": "continuous"},
    {
        "id": "text",
        "name": "Český text",
        "storage": "string",
        "measurement": "ordinal",
        "levels": ["žluťoučký", ""],
        "value_labels": {"žluťoučký": "Label"},
        "missing_codes": ["NA"],
    },
    {
        "id": 'bool";DROP TABLE bad;--',
        "name": "Boolean",
        "storage": "bool",
        "measurement": "binary",
    },
    {
        "id": "responses",
        "name": "Responses",
        "storage": "multiple_response",
        "measurement": "multiple_response",
        "levels": ["a", "b"],
    },
]
ROWS = [
    [9223372036854775807, -0.0, "žluťoučký", True, ["b", "a"]],
    [-9223372036854775808, 1.2345678901234567, "", False, []],
    [None, None, "NA", None, None],
]


@pytest.fixture
def rich(store: Store) -> dict[str, Any]:
    dataset = store.create("Interchange fixture", FIELDS, ROWS, "population", "person")
    return store.edit(dataset["revision"], 2, "int", 9007199254740993)


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("parquet", marks=pytest.mark.feature("DATA-032")),
        pytest.param("json", marks=pytest.mark.feature("DATA-031")),
        pytest.param("sqlite", marks=pytest.mark.feature("DATA-036")),
    ],
)
def test_rich_roundtrip(store: Store, rich: dict[str, Any], tmp_path: Path, kind: str) -> None:
    path = tmp_path / f"dataset.{kind}"
    exported = getattr(io, f"export_{kind}")(store, rich["revision"], str(path))
    assert exported["losses"] == [] and exported["rows"] == 3
    original_hash = path.read_bytes()
    other = Store(tmp_path / "other")
    imported = getattr(io, f"import_{kind}")(other, str(path))
    assert imported["name"] == "Interchange fixture"
    assert imported["context"] == "population" and imported["observation_unit"] == "person"
    assert imported["fields"] == rich["fields"]
    actual = other.page(imported["revision"])["rows"]
    assert actual == [ROWS[0], ROWS[1], [9007199254740993, None, "NA", None, None]]
    assert struct.pack("<d", actual[0][1]) == b"\x00\x00\x00\x00\x00\x00\x00\x80"
    assert other.page(imported["revision"])["row_ids"] == [0, 1, 2]
    assert path.read_bytes() == original_hash
    assert imported["id"] != rich["id"]


def test_sqlite_rich_roundtrip_without_extension_toggle_api(
    store: Store, rich: dict[str, Any], tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "dataset.sqlite"
    io.export_sqlite(store, rich["revision"], str(path))
    real_connect = sqlite3.connect

    class ConnectionWithoutExtensionToggle(sqlite3.Connection):
        def __getattribute__(self, name: str) -> Any:
            if name == "enable_load_extension":
                raise AttributeError(name)
            return super().__getattribute__(name)

    def connect_without_toggle(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs["factory"] = ConnectionWithoutExtensionToggle
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(io.sqlite3, "connect", connect_without_toggle)
    other = Store(tmp_path / "other")
    imported = io.import_sqlite(other, str(path))
    assert imported["fields"] == rich["fields"]
    actual = other.page(imported["revision"])["rows"]
    assert actual == [ROWS[0], ROWS[1], [9007199254740993, None, "NA", None, None]]

    connection = real_connect(path, factory=ConnectionWithoutExtensionToggle)
    with connection:
        with pytest.raises(sqlite3.OperationalError, match="not authorized"):
            connection.execute("SELECT load_extension('unavailable')")


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("parquet", marks=pytest.mark.feature("DATA-032")),
        pytest.param("json", marks=pytest.mark.feature("DATA-031")),
        pytest.param("sqlite", marks=pytest.mark.feature("DATA-036")),
    ],
)
def test_empty_and_batched(store: Store, tmp_path: Path, kind: str, monkeypatch: Any) -> None:
    monkeypatch.setattr(io, "BATCH_ROWS", 2)
    for count in [0, 5]:
        original = store.create("Empty or batched", [FIELDS[0]], [[i] for i in range(count)])
        path = tmp_path / f"{count}.{kind}"
        getattr(io, f"export_{kind}")(store, original["revision"], str(path))
        reopened = getattr(io, f"import_{kind}")(store, str(path))
        assert reopened["row_count"] == count
        assert store.page(reopened["revision"])["rows"] == [[i] for i in range(count)]


@pytest.mark.parametrize(
    "delimiter,decimal",
    [
        pytest.param(",", ".", marks=pytest.mark.feature("DATA-028")),
        pytest.param("\t", ".", marks=pytest.mark.feature("DATA-029")),
        pytest.param(";", ",", marks=pytest.mark.feature("DATA-028")),
    ],
)
def test_flat_text(
    store: Store, rich: dict[str, Any], tmp_path: Path, delimiter: str, decimal: str
) -> None:
    path = tmp_path / "text.csv"
    exported = io.export_csv(store, rich["revision"], str(path), delimiter, decimal)
    assert "null_empty_string_distinction" in exported["losses"]
    with path.open(newline="") as stream:
        rows = list(csv.reader(stream, delimiter=delimiter))
    assert rows[0] == [f["name"] for f in FIELDS]
    assert rows[1] == [
        "9223372036854775807",
        "-0" + decimal + "0",
        "žluťoučký",
        "true",
        '["b","a"]',
    ]
    assert rows[2][1] == "1" + decimal + "2345678901234567"
    assert rows[3] == ["9007199254740993", "", "NA", "", ""]


@pytest.mark.parametrize("kind", ["csv", "parquet", "json", "sqlite"])
def test_atomic_overwrite_and_protected_paths(
    store: Store, rich: dict[str, Any], tmp_path: Path, kind: str
) -> None:
    export = getattr(io, f"export_{kind}")
    target = tmp_path / "target"
    target.write_text("manual content")
    with pytest.raises(EngineError, match="export_exists"):
        export(store, rich["revision"], str(target))
    assert target.read_text() == "manual content"
    export(store, rich["revision"], str(target), overwrite=True)
    assert target.read_bytes() != b"manual content"
    symbolic = tmp_path / "symbolic"
    symbolic.symlink_to(target)
    for path in [symbolic, store.get(rich["revision"]).base, tmp_path / "absent" / "target"]:
        with pytest.raises(EngineError, match="export_path"):
            export(store, rich["revision"], str(path), overwrite=True)
    with pytest.raises(EngineError, match="export_exists"):
        export(store, rich["revision"], str(tmp_path), overwrite=True)
    with pytest.raises(EngineError, match="export_path"):
        export(store, rich["revision"], str(tmp_path / "unknown"), overwrite=1)
    assert not list(tmp_path.glob(".openstat-export-*"))


@pytest.mark.parametrize("delimiter,decimal", [("|", "."), (",", ","), (";", "x")])
def test_bad_csv_options(
    store: Store, rich: dict[str, Any], tmp_path: Path, delimiter: str, decimal: str
) -> None:
    with pytest.raises(EngineError, match="csv_options"):
        io.export_csv(store, rich["revision"], str(tmp_path / "bad.csv"), delimiter, decimal)


def test_plain_parquet_import(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "plain.parquet"
    pq.write_table(
        pa.table(
            {
                "count": pa.array([9223372036854775807, None], type=pa.int64()),
                "real": [0.5, None],
                "flag": [True, None],
                "name": ["one", "two"],
                "sets": [["a", "b"], None],
            }
        ),
        path,
    )
    dataset = io.import_parquet(store, str(path))
    assert [f["storage"] for f in dataset["fields"]] == [
        "int64",
        "float64",
        "bool",
        "string",
        "multiple_response",
    ]
    assert store.page(dataset["revision"])["rows"] == [
        [9223372036854775807, 0.5, True, "one", ["a", "b"]],
        [None, None, None, "two", None],
    ]


@pytest.mark.parametrize(
    "table,key",
    [
        (pa.table({"bad": pa.array([1], type=pa.uint64())}), "interchange_schema"),
        (pa.table({"bad": [math.inf]}), "nonfinite"),
        (pa.table({"bad": [["a", "a"]]}), "duplicate_response"),
        (pa.table({"_openstat_custom": [1]}), "interchange_schema"),
    ],
)
def test_bad_plain_parquet(store: Store, tmp_path: Path, table: Any, key: str) -> None:
    path = tmp_path / "bad.parquet"
    pq.write_table(table, path)
    before = list(store.directory.iterdir())
    with pytest.raises(EngineError, match=key):
        io.import_parquet(store, str(path))
    assert list(store.directory.iterdir()) == before


@pytest.mark.parametrize(
    "mutation,key",
    [
        (lambda d: d.update(version=True), "interchange_schema"),
        (lambda d: d.update(format="other"), "interchange_schema"),
        (lambda d: d["dataset"].update(name=5), "interchange_schema"),
        (lambda d: d["dataset"].update(fields="wrong"), "interchange_schema"),
        (lambda d: d["dataset"]["fields"][0].update(id=5), "interchange_schema"),
        (lambda d: d["dataset"]["fields"][0].update(levels=[1]), "interchange_schema"),
        (lambda d: d["dataset"]["fields"][0].update(missing_codes=None), "interchange_schema"),
        (lambda d: d["dataset"]["fields"][0].update(value_labels={"a": 1}), "interchange_schema"),
        (lambda d: d.update(rows=None), "interchange_schema"),
        (lambda d: d.update(row_ids=[True, 1, 2]), "interchange_schema"),
        (lambda d: d.update(row_ids=[1, 1, 2]), "interchange_schema"),
        (lambda d: d["rows"].__setitem__(0, [0]), "row_width"),
        (lambda d: d["rows"][0].__setitem__(0, 1.5), "value_type"),
        (lambda d: d["dataset"].pop("context"), "interchange_schema"),
    ],
)
def test_json_rejects_incompatible(
    store: Store, rich: dict[str, Any], tmp_path: Path, mutation: Any, key: str
) -> None:
    path = tmp_path / "data.json"
    io.export_json(store, rich["revision"], str(path))
    document = json.loads(path.read_text())
    mutation(document)
    path.write_text(json.dumps(document))
    before = set(store.directory.iterdir())
    with pytest.raises(EngineError, match=key):
        io.import_json(store, str(path))
    assert set(store.directory.iterdir()) == before


@pytest.mark.parametrize(
    "raw,key",
    [
        (b'{"a":1,"a":2}', "interchange_schema"),
        (b"NaN", "nonfinite"),
        (b"{", "interchange_schema"),
        (b"\xff", "interchange_schema"),
        (b"[]", "interchange_schema"),
    ],
)
def test_json_bad_encoding(store: Store, tmp_path: Path, raw: bytes, key: str) -> None:
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(EngineError, match=key):
        io.import_json(store, str(path))


def test_limits_leave_outputs_intact(
    store: Store, rich: dict[str, Any], tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "target"
    path.write_text("existing")
    monkeypatch.setattr(io, "JSON_LIMIT", 64)
    with pytest.raises(EngineError, match="interchange_limit"):
        io.export_json(store, rich["revision"], str(path), overwrite=True)
    assert path.read_text() == "existing"
    path.write_bytes(b"x" * 65)
    with pytest.raises(EngineError, match="interchange_limit"):
        io.import_json(store, str(path))
    monkeypatch.setattr(io, "METADATA_LIMIT", 10)
    for kind in ("sqlite", "parquet"):
        with pytest.raises(EngineError, match="interchange_limit"):
            getattr(io, f"export_{kind}")(store, rich["revision"], str(tmp_path / kind))


@pytest.mark.parametrize(
    "sql,key",
    [
        ('UPDATE "_openstat_data" SET "float"=1.0', "interchange_schema"),
        ('UPDATE "_openstat_data" SET "float"=X\'0000\'', "interchange_schema"),
        ('UPDATE "_openstat_data" SET "responses"=42', "value_type"),
        ('UPDATE "_openstat_data" SET "responses"=\'["a","a"]\'', "duplicate_response"),
        ('UPDATE "_openstat_data" SET "bool"";DROP TABLE bad;--"=2', "value_type"),
        ('DELETE FROM "_openstat_metadata"', "interchange_schema"),
        ('ALTER TABLE "_openstat_data" ADD COLUMN "unexpected" TEXT', "interchange_schema"),
        ('DROP TABLE "_openstat_data"', "interchange_schema"),
    ],
)
def test_sqlite_incompatible(
    store: Store, rich: dict[str, Any], tmp_path: Path, sql: str, key: str
) -> None:
    path = tmp_path / "bad.sqlite"
    io.export_sqlite(store, rich["revision"], str(path))
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    original = path.read_bytes()
    before = set(store.directory.iterdir())
    with pytest.raises(EngineError, match=key):
        io.import_sqlite(store, str(path))
    assert path.read_bytes() == original
    assert set(store.directory.iterdir()) == before


def test_sqlite_unknown_database_and_missing_path(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "generic.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE arbitrary (x INTEGER)")
    with pytest.raises(EngineError, match="interchange_schema"):
        io.import_sqlite(store, str(path))
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(EngineError, match="interchange_schema"):
        io.import_sqlite(store, str(missing))
    assert not missing.exists()


def test_rich_parquet_schema_and_identity_rejected(
    store: Store, rich: dict[str, Any], tmp_path: Path
) -> None:
    path = tmp_path / "bad.parquet"
    io.export_parquet(store, rich["revision"], str(path))
    original = pq.read_table(path)
    for table in [
        original.drop(["int"]),
        original.set_column(0, ROW_ID, pa.array([0, 0, 2])),
        original.set_column(0, ROW_ID, pa.array([-1, 1, 2])),
    ]:
        pq.write_table(table, path)
        with pytest.raises(EngineError, match="interchange_schema"):
            io.import_parquet(store, str(path))


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("parquet", marks=pytest.mark.feature("DATA-032")),
        pytest.param("json", marks=pytest.mark.feature("DATA-031")),
        pytest.param("sqlite", marks=pytest.mark.feature("DATA-036")),
    ],
)
def test_noncontiguous_stable_ids_and_order(store: Store, tmp_path: Path, kind: str) -> None:
    """A sorted/filtered rich revision keeps identities and its current display order."""
    path = tmp_path / "seed.json"
    dataset = store.create("Identity fixture", [FIELDS[0]], [[90], [20]])
    io.export_json(store, dataset["revision"], str(path))
    document = json.loads(path.read_text())
    document["row_ids"] = [9, 2]
    path.write_text(json.dumps(document))
    imported = io.import_json(store, str(path))
    typed_path = tmp_path / f"preserve.{kind}"
    io.export_parquet(store, imported["revision"], str(tmp_path / "identity-check.parquet"))
    assert pq.read_table(tmp_path / "identity-check.parquet").column(ROW_ID).to_pylist() == [9, 2]
    getattr(io, f"export_{kind}")(store, imported["revision"], str(typed_path))
    restored = getattr(io, f"import_{kind}")(store, str(typed_path))
    assert [
        v
        for batch in store.iter_tables(restored["revision"])
        for v in batch.column(ROW_ID).to_pylist()
    ] == [9, 2]
    assert [
        v
        for batch in store.iter_tables(restored["revision"])
        for v in batch.column("int").to_pylist()
    ] == [90, 20]


def test_sqlite_metadata_limit_and_nontext(
    store: Store, rich: dict[str, Any], tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "metadata.sqlite"
    io.export_sqlite(store, rich["revision"], str(path))
    monkeypatch.setattr(io, "METADATA_LIMIT", 10)
    with pytest.raises(EngineError, match="interchange_limit"):
        io.import_sqlite(store, str(path))
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE "_openstat_metadata" SET document=?', (b"\x00",))
    with pytest.raises(EngineError, match="interchange_schema"):
        io.import_sqlite(store, str(path))


@pytest.mark.parametrize("delimiter,feature", [(",", "DATA-028"), ("\t", "DATA-029")])
@pytest.mark.feature("DATA-028")
@pytest.mark.feature("DATA-029")
def test_numeric_flat_text_import_export(
    store: Store, tmp_path: Path, delimiter: str, feature: str
) -> None:
    dataset = store.create(
        "Numeric",
        FIELDS[:2],
        [[9007199254740993, 1.2345678901234567], [-9223372036854775808, -0.0], [None, None]],
    )
    path = tmp_path / feature
    io.export_csv(store, dataset["revision"], str(path), delimiter)
    reopened = store.import_csv(str(path), delimiter)
    values = store.page(reopened["revision"])["rows"]
    assert values == [
        [9007199254740993, 1.2345678901234567],
        [-9223372036854775808, -0.0],
        [None, None],
    ]
    assert math.copysign(1.0, values[1][1]) == -1.0


@pytest.mark.feature("DATA-028")
@pytest.mark.feature("DATA-029")
def test_csv_tsv_hand_calculated_contract(
    store: Store, tmp_path: Path, reference_fixture: Callable[[str], dict[str, Any]]
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/csv_tsv.json")
    dataset = store.create(
        fixture["input"]["name"],
        fixture["input"]["fields"],
        fixture["input"]["rows"],
    )
    expected = fixture["expected"]

    # Comma delimiter, dot decimal (DATA-028)
    csv_path = tmp_path / "export.csv"
    res_csv = io.export_csv(
        store, dataset["revision"], str(csv_path), delimiter=",", decimal_point="."
    )
    assert res_csv["losses"] == expected["losses"]
    with csv_path.open(newline="", encoding="utf-8") as stream:
        assert list(csv.reader(stream, delimiter=",")) == expected["csv_rows"]

    # Tab delimiter, dot decimal (DATA-029)
    tsv_path = tmp_path / "export.tsv"
    res_tsv = io.export_csv(
        store, dataset["revision"], str(tsv_path), delimiter="\t", decimal_point="."
    )
    assert res_tsv["losses"] == expected["losses"]
    with tsv_path.open(newline="", encoding="utf-8") as stream:
        assert list(csv.reader(stream, delimiter="\t")) == expected["tsv_rows"]

    # Semicolon delimiter, comma decimal (DATA-028 locale option)
    locale_path = tmp_path / "export_locale.csv"
    res_locale = io.export_csv(
        store, dataset["revision"], str(locale_path), delimiter=";", decimal_point=","
    )
    assert res_locale["losses"] == expected["losses"]
    with locale_path.open(newline="", encoding="utf-8") as stream:
        assert list(csv.reader(stream, delimiter=";")) == expected["locale_rows"]

    # Re-import through new store and verify typed rows + negative zero preservation
    other = Store(tmp_path / "other")
    imported = other.import_csv(str(csv_path), delimiter=",", decimal_point=".")
    reimported_rows = other.page(imported["revision"])["rows"]
    assert reimported_rows == expected["reimport_rows"]
    assert math.copysign(1.0, reimported_rows[0][1]) == -1.0

