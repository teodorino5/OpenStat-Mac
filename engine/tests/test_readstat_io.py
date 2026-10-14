import math
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pyreadstat
import pytest

from openstat_engine import readstat_io
from openstat_engine.classification import missing_kind
from openstat_engine.errors import EngineError
from openstat_engine.model import Field
from openstat_engine.readstat_io import (
    _field_for,
    export_dta,
    export_sav,
    import_dta,
    import_sas7bdat,
    import_sav,
)
from openstat_engine.store import Store


def _fixture(path: Path, fmt: str) -> None:
    comments = [None, "", "x" * 3000] if fmt == "sav" else ["first", "", "x" * 3000]
    frame = pd.DataFrame(
        {
            "score": pd.array([1, 2, None], dtype="Int64"),
            "group_code": pd.array([1, 2, 1], dtype="Int64"),
            "comment": pd.array(comments, dtype="string"),
        }
    )
    writer = pyreadstat.write_sav if fmt == "sav" else pyreadstat.write_dta
    options = {"variable_value_labels": {"group_code": {1: "Control", 2: "Treatment"}}}
    if fmt == "sav":
        options["variable_measure"] = {"score": "scale", "group_code": "nominal"}
    writer(frame, path, **options)


@pytest.mark.parametrize("fmt,importer", [("sav", import_sav), ("dta", import_dta)])
def test_import_generated_file_keeps_values_labels_and_reports_flat_file_losses(
    tmp_path: Path, fmt: str, importer
) -> None:
    source = tmp_path / f"original.{fmt}"
    _fixture(source, fmt)
    store = Store(tmp_path / "store")
    descriptor = importer(store, str(source))

    fields = {field["name"]: field for field in descriptor["fields"]}
    assert descriptor["row_count"] == 3
    assert fields["group_code"]["value_labels"] == {"1.0": "Control", "2.0": "Treatment"}
    assert fields["group_code"]["levels"] == ["1.0", "2.0"]
    assert descriptor["source_metadata"]["format"] == fmt
    assert "source_metadata_not_persisted" in descriptor["losses"]
    assert "source_null_and_empty_string_may_be_indistinguishable" in descriptor["losses"]
    batch = next(store.iter_tables(descriptor["revision"]))
    assert batch[fields["score"]["id"]].to_pylist() == [1.0, 2.0, None]
    assert batch[fields["group_code"]["id"]].to_pylist() == [1, 2, 1]
    # Both blank and physical-null source strings may map to empty on read.
    expected_comments = ["", "", "x" * 3000] if fmt == "sav" else ["first", "", "x" * 3000]
    assert batch[fields["comment"]["id"]].to_pylist() == expected_comments


@pytest.mark.parametrize(
    "fmt,exporter,reader",
    [
        ("sav", export_sav, pyreadstat.read_sav),
        ("dta", export_dta, pyreadstat.read_dta),
    ],
)
def test_export_real_writer_preserves_supported_values_and_labels(
    tmp_path: Path, fmt: str, exporter, reader
) -> None:
    store = Store(tmp_path / "store")
    descriptor = store.create(
        "Survey",
        [
            {"id": "score", "name": "score", "storage": "int64", "measurement": "discrete"},
            {
                "id": "group",
                "name": "group_code",
                "storage": "int64",
                "measurement": "nominal",
                "levels": ["1", "2"],
                "value_labels": {"1": "Control", "2": "Treatment"},
            },
            {"id": "comment", "name": "comment", "storage": "string", "measurement": "nominal"},
            {"id": "active", "name": "active", "storage": "bool", "measurement": "binary"},
        ],
        [[1, 1, None, True], [2, 2, "", False], [None, 1, "last", None]],
    )
    target = tmp_path / f"exported.{fmt}"
    report = exporter(store, descriptor["revision"], str(target))
    data, metadata = reader(target, output_format="dict", user_missing=True)
    assert report["rows"] == 3
    assert "row_ids" in report["losses"]
    assert "null_empty_string_distinction" in report["losses"]
    assert data["score"] == [1.0, 2.0, None]
    assert data["group_code"] == [1.0, 2.0, 1.0]
    assert data["comment"] == ["", "", "last"]
    assert data["active"] == [True, False, None]
    assert metadata.variable_value_labels["group_code"] == {1.0: "Control", 2.0: "Treatment"}


def test_export_rejects_inexact_large_integer_and_multiple_response(tmp_path: Path) -> None:
    store = Store(tmp_path / "store")
    large = store.create(
        "Large",
        [{"id": "x", "name": "x", "storage": "int64", "measurement": "discrete"}],
        [[2**53 + 1]],
    )
    with pytest.raises(EngineError, match="error.readstat_precision"):
        export_sav(store, large["revision"], str(tmp_path / "large.sav"))

    multiple = store.create(
        "Multiple",
        [
            {
                "id": "x",
                "name": "x",
                "storage": "multiple_response",
                "measurement": "multiple_response",
            }
        ],
        [[["a", "b"]]],
    )
    with pytest.raises(EngineError, match="error.readstat_multiple_response"):
        export_dta(store, multiple["revision"], str(tmp_path / "multiple.dta"))


def test_export_respects_overwrite_gate(tmp_path: Path) -> None:
    store = Store(tmp_path / "store")
    descriptor = store.create(
        "One",
        [{"id": "x", "name": "x", "storage": "int64", "measurement": "discrete"}],
        [[1]],
    )
    target = tmp_path / "one.sav"
    export_sav(store, descriptor["revision"], str(target))
    with pytest.raises(EngineError, match="error.export_exists"):
        export_sav(store, descriptor["revision"], str(target))


def test_import_records_discrete_user_missing_code(tmp_path: Path) -> None:
    source = tmp_path / "missing.sav"
    pyreadstat.write_sav(
        pd.DataFrame({"answer": [1, 9, 2]}), source, missing_ranges={"answer": [9]}
    )
    store = Store(tmp_path / "store")
    result = import_sav(store, str(source))
    answer = result["fields"][0]
    assert answer["missing_codes"] == ["9.0"]
    table = next(store.iter_tables(result["revision"]))
    assert table[answer["id"]].to_pylist() == [1.0, 9.0, 2.0]


def test_import_rejects_dates_and_row_over_limit(tmp_path: Path, monkeypatch) -> None:
    date_path = tmp_path / "date.sav"
    pyreadstat.write_sav(
        pd.DataFrame({"when": [1, 2]}), date_path, variable_format={"when": "DATE11"}
    )
    with pytest.raises(EngineError, match="error.readstat_date_format"):
        import_sav(Store(tmp_path / "dates"), str(date_path))

    stata_date = tmp_path / "date.dta"
    pyreadstat.write_dta(
        pd.DataFrame({"when": [1, 2]}), stata_date, variable_format={"when": "%td"}
    )
    with pytest.raises(EngineError, match="error.readstat_date_format"):
        import_dta(Store(tmp_path / "stata-dates"), str(stata_date))

    plain_path = tmp_path / "plain.dta"
    pyreadstat.write_dta(pd.DataFrame({"x": [1, 2, 3]}), plain_path)
    monkeypatch.setattr(readstat_io, "MAX_ROWS", 2)
    with pytest.raises(EngineError, match="error.readstat_limit"):
        import_dta(Store(tmp_path / "limited"), str(plain_path))


def test_import_preserves_system_null_separately_from_coded_missing(tmp_path: Path) -> None:
    source = tmp_path / "nullable.sav"
    pyreadstat.write_sav(
        pd.DataFrame({"answer": [1.0, 9.0, None]}),
        source,
        missing_ranges={"answer": [9]},
    )
    store = Store(tmp_path / "store")
    result = import_sav(store, str(source))
    field = result["fields"][0]
    values = next(store.iter_tables(result["revision"]))[field["id"]].to_pylist()
    assert values == [1.0, 9.0, None]
    assert field["missing_codes"] == ["9.0"]
    definition = Field.from_dict(field)
    assert missing_kind(definition, values[1]) == "coded_missing"
    assert missing_kind(definition, values[2]) == "null"


def test_import_rejects_ranges_tagged_missing_invalid_and_truncated_files(tmp_path: Path) -> None:
    ranged = tmp_path / "range.sav"
    pyreadstat.write_sav(
        pd.DataFrame({"x": [1, 8, 9]}),
        ranged,
        missing_ranges={"x": [{"lo": 8, "hi": 9}]},
    )
    with pytest.raises(EngineError, match="error.readstat_missing_range"):
        import_sav(Store(tmp_path / "range-store"), str(ranged))

    tagged = tmp_path / "tagged.dta"
    pyreadstat.write_dta(
        pd.DataFrame({"x": [3, "a", 4]}),
        tagged,
        missing_user_values={"x": ["a"]},
    )
    with pytest.raises(EngineError, match="error.readstat_tagged_missing"):
        import_dta(Store(tmp_path / "tagged-store"), str(tagged))

    invalid = tmp_path / "invalid.sav"
    invalid.write_bytes(b"not an SPSS file")
    with pytest.raises(EngineError, match="error.readstat_file"):
        import_sav(Store(tmp_path / "invalid-store"), str(invalid))

    truncated = tmp_path / "truncated.dta"
    pyreadstat.write_dta(pd.DataFrame({"x": [1, 2, 3]}), truncated)
    truncated.write_bytes(truncated.read_bytes()[:16])
    with pytest.raises(EngineError, match="error.readstat_file"):
        import_dta(Store(tmp_path / "truncated-store"), str(truncated))


def test_import_rejects_byte_and_cell_limits_before_reading_rows(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "wide.dta"
    pyreadstat.write_dta(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), source)
    original_reader = readstat_io._READERS["dta"]
    calls = []

    def spy_reader(path, **options):
        calls.append(options.get("metadataonly", False))
        return original_reader(path, **options)

    monkeypatch.setitem(readstat_io._READERS, "dta", spy_reader)
    monkeypatch.setattr(readstat_io, "MAX_CELLS", 3)
    with pytest.raises(EngineError, match="error.readstat_limit"):
        import_dta(Store(tmp_path / "cells"), str(source))
    assert calls == [True]

    monkeypatch.setattr(readstat_io, "MAX_CELLS", 100)
    monkeypatch.setattr(readstat_io, "MAX_SOURCE_BYTES", source.stat().st_size - 1)
    with pytest.raises(EngineError, match="error.readstat_limit"):
        import_dta(Store(tmp_path / "bytes"), str(source))


def _metadata(names, types=None, row_count=1, **changes):
    values = {
        "column_names": names,
        "column_names_to_labels": {},
        "original_variable_types": {},
        "file_label": "",
        "file_encoding": "UTF-8",
        "mr_sets": {},
        "number_rows": row_count,
        "variable_value_labels": {},
        "readstat_variable_types": types or {name: "double" for name in names},
        "missing_user_values": {},
        "missing_ranges": {},
        "variable_measure": {},
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _fake_reader(monkeypatch, meta, data):
    calls = []

    def reader(_path, **options):
        calls.append(options)
        return (None, meta) if options.get("metadataonly") else (data, meta)

    monkeypatch.setitem(readstat_io._READERS, "sav", reader)
    return calls


def test_metadata_preflight_stops_before_data_read(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "fake.sav"
    source.write_bytes(b"fixture")
    meta = _metadata(["x"], row_count=3)
    calls = _fake_reader(monkeypatch, meta, {"x": [1.0, 2.0, 3.0]})
    monkeypatch.setattr(readstat_io, "MAX_ROWS", 2)
    with pytest.raises(EngineError, match="error.readstat_limit"):
        import_sav(Store(tmp_path / "store"), str(source))
    assert len(calls) == 1
    assert calls[0]["metadataonly"] is True


@pytest.mark.parametrize("names", [[], ["x", "x"]])
def test_import_rejects_empty_or_duplicate_names(tmp_path: Path, monkeypatch, names) -> None:
    source = tmp_path / "fake.sav"
    source.write_bytes(b"fixture")
    meta = _metadata(names, types={name: "double" for name in names})
    calls = _fake_reader(monkeypatch, meta, {name: [] for name in names})
    with pytest.raises(EngineError, match="error.readstat_schema"):
        import_sav(Store(tmp_path / "store"), str(source))
    assert len(calls) == 1


@pytest.mark.parametrize(
    "native_type,data,error",
    [
        ("mystery", [1], "error.readstat_type"),
        ("int32", [1.5], "error.readstat_type"),
        ("int32", [2**63], "error.readstat_type"),
        ("double", [float("inf")], "error.nonfinite"),
        ("string", [123], "error.readstat_type"),
    ],
)
def test_import_rejects_unsupported_or_invalid_cells(
    tmp_path: Path, monkeypatch, native_type, data, error
) -> None:
    source = tmp_path / "fake.sav"
    source.write_bytes(b"fixture")
    meta = _metadata(["x"], types={"x": native_type})
    _fake_reader(monkeypatch, meta, {"x": data})
    with pytest.raises(EngineError, match=error):
        import_sav(Store(tmp_path / "store"), str(source))


def test_field_conversion_accepts_ordinal_and_rejects_malformed_missing_range() -> None:
    meta = _metadata(
        ["x"],
        types={"x": "int32"},
        variable_measure={"x": "ordinal"},
        missing_ranges={"x": [SimpleNamespace(lo=7, hi=7)]},
        variable_value_labels={"x": {1.0: "Low", 2.0: "High"}},
    )
    field = _field_for("x", meta, "sav")
    assert field.measurement == "ordinal"
    assert field.levels == ("1", "2", "7")
    assert field.missing_codes == ("7",)

    meta.missing_ranges = {"x": [{"lo": 8}]}
    with pytest.raises(EngineError, match="error.readstat_schema"):
        _field_for("x", meta, "sav")


def test_import_rejects_metadata_and_codebook_limits(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "fake.sav"
    source.write_bytes(b"fixture")
    meta = _metadata(["x"], column_names_to_labels={"x": "long"})
    _fake_reader(monkeypatch, meta, {"x": [1.0]})
    monkeypatch.setattr(readstat_io, "MAX_METADATA_CHARS", 1)
    with pytest.raises(EngineError, match="error.readstat_limit"):
        import_sav(Store(tmp_path / "metadata"), str(source))

    monkeypatch.setattr(readstat_io, "MAX_METADATA_CHARS", 3)
    meta.column_names_to_labels = {}
    meta.variable_value_labels = {"x": {1.0: "one"}}
    with pytest.raises(EngineError, match="error.readstat_limit"):
        import_sav(Store(tmp_path / "codebook"), str(source))


@pytest.mark.parametrize("fmt,importer", [("sav", import_sav), ("dta", import_dta)])
def test_import_plain_conversions_and_export_negative_zero(
    tmp_path: Path, fmt: str, importer
) -> None:
    source = tmp_path / f"plain.{fmt}"
    frame = pd.DataFrame({"integer": [1, 2], "real": [-0.0, 1.25], "text": ["", "word"]})
    (pyreadstat.write_sav if fmt == "sav" else pyreadstat.write_dta)(frame, source)
    store = Store(tmp_path / "store")
    imported = importer(store, str(source))
    fields = {field["name"]: field for field in imported["fields"]}
    assert (
        fields["integer"]["storage"] == "float64"
    )  # PyReadStat exposes numeric columns as doubles.
    page = next(store.iter_tables(imported["revision"]))
    assert page[fields["text"]["id"]].to_pylist() == ["", "word"]

    export = tmp_path / f"negative-zero.{fmt}"
    one = store.create(
        "Negative zero",
        [{"id": "real", "name": "real", "storage": "float64", "measurement": "continuous"}],
        [[-0.0], [0.0], [1.23456789012345]],
    )
    (export_sav if fmt == "sav" else export_dta)(store, one["revision"], str(export))
    reader = pyreadstat.read_sav if fmt == "sav" else pyreadstat.read_dta
    values, _ = reader(export, output_format="dict")
    assert math.copysign(1, values["real"][0]) == -1
    assert math.copysign(1, values["real"][1]) == 1
    assert values["real"][2] == 1.23456789012345


def test_import_rejects_reserved_field_and_sas_bad_file(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "reserved.sav"
    source.write_bytes(b"synthetic metadata test")
    meta = SimpleNamespace(
        column_names=["_openstat_row_id"],
        column_names_to_labels={},
        original_variable_types={},
        file_label="",
        file_encoding="UTF-8",
        mr_sets={},
        number_rows=1,
        variable_value_labels={},
        readstat_variable_types={"_openstat_row_id": "int32"},
        missing_user_values={},
        missing_ranges={},
        variable_measure={},
    )

    def reader(_path, **kwargs):
        if kwargs.get("metadataonly"):
            return None, meta
        return {"_openstat_row_id": [1]}, meta

    monkeypatch.setitem(readstat_io._READERS, "sav", reader)
    with pytest.raises(EngineError, match="error.field_name"):
        import_sav(Store(tmp_path / "reserved-store"), str(source))
    monkeypatch.undo()
    source.write_bytes(b"invalid SAS")
    with pytest.raises(EngineError, match="error.readstat_file"):
        import_sas7bdat(Store(tmp_path / "sas-store"), str(source))


def test_export_rejects_long_names_private_paths_symlinks_and_cleans_failed_stage(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "store")
    long_name = store.create(
        "Long name",
        [{"id": "x", "name": "x" * 33, "storage": "int64", "measurement": "discrete"}],
        [[1]],
    )
    with pytest.raises(EngineError, match="error.readstat_name"):
        export_dta(store, long_name["revision"], str(tmp_path / "long.dta"))

    ordinary = store.create(
        "Ordinary",
        [{"id": "bad name", "name": "bad name", "storage": "int64", "measurement": "discrete"}],
        [[1]],
    )
    target = tmp_path / "invalid-name.sav"
    with pytest.raises(EngineError, match="error.readstat_export"):
        export_sav(store, ordinary["revision"], str(target))
    assert not target.exists()
    assert list(tmp_path.glob(".openstat-export-*")) == []

    protected = store.directory / "private.sav"
    with pytest.raises(EngineError, match="error.export_path"):
        export_sav(store, ordinary["revision"], str(protected))

    link = tmp_path / "symlink.sav"
    link.symlink_to(tmp_path / "missing-target.sav")
    with pytest.raises(EngineError, match="error.export_path"):
        export_sav(store, ordinary["revision"], str(link), overwrite=True)


def test_export_preserves_long_strings_and_exact_integer_boundary(tmp_path: Path) -> None:
    store = Store(tmp_path / "store")
    descriptor = store.create(
        "Long and exact",
        [
            {"id": "text", "name": "text", "storage": "string", "measurement": "nominal"},
            {"id": "integer", "name": "integer", "storage": "int64", "measurement": "discrete"},
        ],
        [["x" * 3000, 2**53], ["", -(2**53)]],
    )
    path = tmp_path / "long.dta"
    export_dta(store, descriptor["revision"], str(path))
    data, _ = pyreadstat.read_dta(path, output_format="dict")
    assert data["text"] == ["x" * 3000, ""]
    assert data["integer"] == [float(2**53), float(-(2**53))]


@pytest.mark.feature("DATA-034")
def test_stata_reference_fixture(
    store: Store,
    tmp_path: Path,
    reference_fixture: Callable[[str], dict[str, Any]],
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/stata.json")
    raw_input = fixture["input"]
    expected = fixture["expected"]
    source_path = tmp_path / "source.dta"

    # 1. Author source Stata file matching fixture input
    df = pd.DataFrame(
        {
            "mpg": pd.array(raw_input["columns"]["mpg"], dtype="Float64"),
            "foreign": pd.array(raw_input["columns"]["foreign"], dtype="Int64"),
            "make": pd.array(raw_input["columns"]["make"], dtype="string"),
        }
    )
    val_labels = {
        col: {int(k) if k.isdigit() else float(k): v for k, v in labels.items()}
        for col, labels in raw_input["variable_value_labels"].items()
    }
    pyreadstat.write_dta(
        df,
        source_path,
        version=raw_input["version"],
        column_labels=raw_input["column_labels"],
        variable_value_labels=val_labels,
    )

    # 2. Import into OpenStat
    import_desc = import_dta(store, str(source_path))
    assert import_desc["row_count"] == expected["row_count"]
    assert import_desc["losses"] == expected["import_losses"]
    assert import_desc["source_metadata"]["format"] == expected["source_metadata"]["format"]
    assert (
        import_desc["source_metadata"]["column_labels"]
        == expected["source_metadata"]["column_labels"]
    )

    fields = import_desc["fields"]
    for expected_field, actual_field in zip(expected["imported_fields"], fields, strict=True):
        assert actual_field["name"] == expected_field["name"]
        assert actual_field["storage"] == expected_field["storage"]
        assert actual_field["measurement"] == expected_field["measurement"]
        assert actual_field["missing_codes"] == expected_field["missing_codes"]
        assert actual_field["value_labels"] == expected_field["value_labels"]

    # Verify rows & negative zero
    batch = next(store.iter_tables(import_desc["revision"]))
    imported_rows = [
        [batch[f["id"]].to_pylist()[i] for f in fields]
        for i in range(import_desc["row_count"])
    ]
    assert imported_rows == expected["imported_rows"]

    # Verify IEEE negative zero
    mpg_col = batch[fields[0]["id"]].to_pylist()
    assert math.copysign(1.0, mpg_col[1]) == -1.0

    # 3. Export to target DTA file with explicit format version (14 and 15)
    for v in expected["versions_tested"]:
        export_path = tmp_path / f"exported_v{v}.dta"
        export_desc = export_dta(
            store, import_desc["revision"], str(export_path), version=v
        )
        assert export_desc["rows"] == expected["row_count"]
        assert export_desc["losses"] == expected["export_losses"]
        assert export_desc["version"] == v

        # 4. Re-import in an independent store instance
        store2 = Store(tmp_path / f"store_v{v}")
        reimport_desc = import_dta(store2, str(export_path))
        assert reimport_desc["row_count"] == expected["row_count"]

        batch2 = next(store2.iter_tables(reimport_desc["revision"]))
        fields2 = reimport_desc["fields"]
        reimported_rows = [
            [batch2[f["id"]].to_pylist()[i] for f in fields2]
            for i in range(reimport_desc["row_count"])
        ]
        assert reimported_rows == expected["imported_rows"]
        assert fields2[1]["value_labels"] == expected["imported_fields"][1]["value_labels"]

    # 5. Invalid version rejection
    with pytest.raises(EngineError, match="error.readstat_export"):
        export_dta(store, import_desc["revision"], str(tmp_path / "bad.dta"), version=99)

