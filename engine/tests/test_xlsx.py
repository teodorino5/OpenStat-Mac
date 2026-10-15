"""Manual OOXML literals and independently specified data expectations."""

import json
import math
import struct
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from openstat_engine import interchange as io
from openstat_engine import xlsx
from openstat_engine.errors import EngineError
from openstat_engine.store import Store

pytestmark = pytest.mark.feature("DATA-030")
NS = xlsx.NS
REL = xlsx.DOC_REL


def workbook(path: Path, rows: str, extras: dict[str, str] | None = None) -> None:
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS}" xmlns:r="{REL}">'
            f'<sheets><sheet name="Input" sheetId="1" r:id="r1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{xlsx.REL_NS}">'
            f'<Relationship Id="r1" Type="{REL}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{NS}"><sheetData>{rows}</sheetData></worksheet>'
        ),
    }
    parts.update(extras or {})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)


def text(reference: str, value: str) -> str:
    return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'


def row(index: int, cells: str) -> str:
    return f'<row r="{index}">{cells}</row>'


@pytest.fixture
def rich(store: Store) -> dict[str, Any]:
    fields = [
        {"id": "int", "name": "Integer", "storage": "int64", "measurement": "discrete"},
        {"id": "real", "name": "Real", "storage": "float64", "measurement": "continuous"},
        {"id": "flag", "name": "Flag", "storage": "bool", "measurement": "binary"},
        {
            "id": "name",
            "name": "Český název",
            "storage": "string",
            "measurement": "ordinal",
            "levels": ["žluťoučký", ""],
            "missing_codes": ["NA"],
            "value_labels": {"": "empty"},
        },
        {
            "id": "set",
            "name": "Set",
            "storage": "multiple_response",
            "measurement": "multiple_response",
        },
    ]
    dataset = store.create(
        "Typed",
        fields,
        [
            [9223372036854775807, -0.0, True, "žluťoučký", ["b", "a"]],
            [-9223372036854775808, 1.2345678901234567, False, "", []],
            [None, None, None, "NA", None],
        ],
        "population",
        "patient",
    )
    return store.edit(dataset["revision"], 2, "int", 9007199254740993)


def test_rich_roundtrip_and_stable_ids(store: Store, rich: dict[str, Any], tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    io.export_json(store, rich["revision"], str(seed))
    document = json.loads(seed.read_text())
    document["row_ids"] = [9, 2, 88]
    seed.write_text(json.dumps(document))
    imported = io.import_json(store, str(seed))
    path = tmp_path / "data.xlsx"
    result = xlsx.export_xlsx(store, imported["revision"], str(path))
    original = path.read_bytes()
    assert result["losses"] == [] and "float64_and_large_int64_are_text" in result["notes"]
    reopened = xlsx.import_xlsx(store, str(path))
    assert reopened["fields"] == rich["fields"]
    assert reopened["context"] == "population" and reopened["observation_unit"] == "patient"
    values = store.page(reopened["revision"])
    assert values["row_ids"] == [9, 2, 88]
    assert values["rows"] == [
        [9223372036854775807, -0.0, True, "žluťoučký", ["b", "a"]],
        [-9223372036854775808, 1.2345678901234567, False, "", []],
        [9007199254740993, None, None, "NA", None],
    ]
    assert struct.pack("<d", values["rows"][0][1]) == bytes.fromhex("0000000000000080")
    assert path.read_bytes() == original
    with zipfile.ZipFile(path) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
        assert '<c r="A2" t="inlineStr">' in sheet
        assert '<c r="B2" t="inlineStr">' in sheet


@pytest.mark.parametrize("count", [0, 1, 5])
def test_empty_and_multiple_batches(
    store: Store, tmp_path: Path, count: int, monkeypatch: Any
) -> None:
    monkeypatch.setattr(xlsx, "BATCH_ROWS", 2)
    item = store.create(
        "Count",
        [{"id": "count", "name": "Count", "storage": "int64", "measurement": "discrete"}],
        [[i] for i in range(count)],
    )
    path = tmp_path / "count.xlsx"
    xlsx.export_xlsx(store, item["revision"], str(path))
    restored = xlsx.import_xlsx(store, str(path), "Data")
    assert store.page(restored["revision"])["rows"] == [[i] for i in range(count)]


def test_plain_sparse_numeric_boolean_shared_and_inline(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "plain.xlsx"
    header = row(1, text("A1", "Number") + text("B1", "Boolean") + '<c r="C1" t="s"><v>0</v></c>')
    content = header + row(
        2, '<c r="A2"><v>1.5</v></c><c r="B2" t="b"><v>1</v></c><c r="C2" t="s"><v>1</v></c>'
    )
    content += row(4, '<c r="A4"><v>2</v></c><c r="B4" t="b"><v>0</v></c>' + text("C4", ""))
    workbook(
        path,
        content,
        {
            "xl/sharedStrings.xml": (
                f'<sst xmlns="{NS}"><si><t>Words</t>'
                f"</si><si><r><t>rich </t></r><r><t>text</t></r></si></sst>"
            )
        },
    )
    dataset = xlsx.import_xlsx(store, str(path), "Input")
    assert [f["storage"] for f in dataset["fields"]] == ["float64", "bool", "string"]
    assert store.page(dataset["revision"])["rows"] == [
        [1.5, True, "rich text"],
        [None, None, None],
        [2.0, False, ""],
    ]


@pytest.mark.parametrize(
    "values,expected,storage",
    [
        (["<v>12</v>", "<v>-3</v>"], [12, -3], "int64"),
        (["<v>-0.0</v>", "<v>1e-10</v>"], [-0.0, 1e-10], "float64"),
        (["<v>12</v>", "<is><t>word</t></is>"], ["12", "word"], "string"),
        (["<v>1</v>", "<v>2</v>"], ["True", "2"], "string"),
        (["", ""], [None, None], "string"),
    ],
)
def test_generic_inference(
    store: Store, tmp_path: Path, values: list[str], expected: list[Any], storage: str
) -> None:
    path = tmp_path / "inference.xlsx"
    kind1 = ' t="b"' if expected == ["True", "2"] else ""
    kind2 = ' t="inlineStr"' if expected == ["12", "word"] else ""
    workbook(
        path,
        row(1, text("A1", "Value"))
        + row(2, f'<c r="A2"{kind1}>{values[0]}</c>')
        + row(3, f'<c r="A3"{kind2}>{values[1]}</c>'),
    )
    dataset = xlsx.import_xlsx(store, str(path))
    assert dataset["fields"][0]["storage"] == storage
    actual = [r[0] for r in store.page(dataset["revision"])["rows"]]
    assert actual == expected
    if storage == "float64":
        assert math.copysign(1, actual[0]) == -1


@pytest.mark.parametrize(
    "cell,key",
    [
        ('<c r="A2"><f>1+1</f></c>', "xlsx_schema"),
        ('<c r="A2" s="1"><v>44500</v></c>', "xlsx_style"),
        ('<c r="A2" t="d"><v>2024-01-01</v></c>', "xlsx_style"),
        ('<c r="A2" t="e"><v>#DIV/0!</v></c>', "xlsx_style"),
        ('<c r="A2" t="b"><v>2</v></c>', "xlsx_schema"),
        ('<c r="A2" t="s"><v>0</v></c>', "xlsx_schema"),
        ('<c r="A2" t="unknown"><v>2</v></c>', "xlsx_schema"),
        ('<c r="A2"><v>NaN</v></c>', "nonfinite"),
        ('<c r="A2"><v>9223372036854775808</v></c>', "integer_range"),
        ('<c r="A2"><v>word</v></c>', "xlsx_schema"),
        ('<c r="A3"><v>2</v></c>', "xlsx_schema"),
        ('<c r="A2"><v>2</v></c><c r="A2"><v>3</v></c>', "xlsx_schema"),
        ('<c r="B2"><v>2</v></c>', "row_width"),
        ('<c r="bad"><v>2</v></c>', "xlsx_schema"),
        ('<c r="ZZZZ2"><v>2</v></c>', "xlsx_limit"),
    ],
)
def test_bad_cells_rejected_without_partial_import(
    store: Store, tmp_path: Path, cell: str, key: str
) -> None:
    path = tmp_path / "bad.xlsx"
    workbook(path, row(1, text("A1", "Value")) + row(2, cell))
    before = set(store.directory.iterdir())
    with pytest.raises(EngineError, match=key):
        xlsx.import_xlsx(store, str(path))
    assert set(store.directory.iterdir()) == before


@pytest.mark.parametrize(
    "extras,key",
    [
        ({"xl/vbaProject.bin": "macro"}, "xlsx_unsafe"),
        ({"xl/externalLinks/externalLink1.xml": "external"}, "xlsx_unsafe"),
        (
            {
                "xl/custom.rels": (
                    f'<Relationships xmlns="{xlsx.REL_NS}">'
                    f'<Relationship TargetMode="External" Target="https://example.com"/></Relationships>'
                )
            },
            "xlsx_unsafe",
        ),
        ({"../escape.xml": "escape"}, "xlsx_schema"),
        (
            {
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS}"><cellXfs><xf numFmtId="14"/></cellXfs></styleSheet>'
                )
            },
            "xlsx_style",
        ),
        ({"xl/workbook.xml": '<!DOCTYPE x [<!ENTITY y "bad">]><x/>'}, "xlsx_schema"),
        ({"xl/workbook.xml": "<x>\x00</x>"}, "xlsx_schema"),
        ({"xl/workbook.xml": "<malformed>"}, "xlsx_schema"),
    ],
)
def test_unsafe_packages(store: Store, tmp_path: Path, extras: dict[str, str], key: str) -> None:
    path = tmp_path / "unsafe.xlsx"
    workbook(path, row(1, text("A1", "Header")), extras)
    with pytest.raises(EngineError, match=key):
        xlsx.import_xlsx(store, str(path))


@pytest.mark.parametrize(
    "limit,value", [("MAX_MEMBERS", 1), ("MAX_EXPANDED", 1), ("MAX_PART", 1), ("MAX_STRINGS", 0)]
)
def test_package_limits(
    store: Store, tmp_path: Path, monkeypatch: Any, limit: str, value: int
) -> None:
    path = tmp_path / "limits.xlsx"
    workbook(
        path,
        row(1, text("A1", "Header")),
        {"xl/sharedStrings.xml": f'<sst xmlns="{NS}"><si><t>a</t></si></sst>'},
    )
    monkeypatch.setattr(xlsx, limit, value)
    with pytest.raises(EngineError, match="xlsx_(schema|limit)"):
        xlsx.import_xlsx(store, str(path))


@pytest.mark.parametrize(
    "header",
    [
        row(1, text("A1", "")),
        row(1, text("A1", "Same") + text("B1", "Same")),
        row(1, '<c r="A1"><v>1</v></c>'),
        row(2, text("A2", "Late")),
        "",
    ],
)
def test_invalid_headers(store: Store, tmp_path: Path, header: str) -> None:
    path = tmp_path / "header.xlsx"
    workbook(path, header)
    with pytest.raises(EngineError):
        xlsx.import_xlsx(store, str(path))


def test_sheet_selection_and_atomic_overwrite(
    store: Store, rich: dict[str, Any], tmp_path: Path
) -> None:
    path = tmp_path / "exists.xlsx"
    path.write_text("manual")
    with pytest.raises(EngineError, match="export_exists"):
        xlsx.export_xlsx(store, rich["revision"], str(path))
    assert path.read_text() == "manual"
    xlsx.export_xlsx(store, rich["revision"], str(path), overwrite=True)
    with pytest.raises(EngineError, match="xlsx_sheet"):
        xlsx.import_xlsx(store, str(path), "Absent")
    with pytest.raises(EngineError, match="field_name"):
        xlsx.import_xlsx(store, str(path), xlsx.ID_SHEET)


@pytest.mark.parametrize(
    "limit,value", [("MAX_ROWS", 1), ("METADATA_LIMIT", 1), ("MAX_EXPANDED", 1), ("MAX_PART", 1)]
)
def test_export_limits_are_atomic(
    store: Store, rich: dict[str, Any], tmp_path: Path, monkeypatch: Any, limit: str, value: int
) -> None:
    path = tmp_path / "existing.xlsx"
    path.write_text("existing")
    monkeypatch.setattr(xlsx, limit, value)
    with pytest.raises(EngineError, match="xlsx_limit"):
        xlsx.export_xlsx(store, rich["revision"], str(path), overwrite=True)
    assert path.read_text() == "existing"
    assert not list(tmp_path.glob(".openstat-export-*"))


def test_invalid_zip(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "not-a-zip.xlsx"
    path.write_text("text")
    with pytest.raises(EngineError, match="xlsx_schema"):
        xlsx.import_xlsx(store, str(path))


def test_xlsx_hand_calculated_contract(
    store: Store, reference_fixture: Callable[[str], dict[str, Any]], tmp_path: Path
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/xlsx.json")
    created = store.create(
        name=fixture["input"]["name"],
        fields=fixture["input"]["fields"],
        rows=fixture["input"]["rows"],
        context=fixture["input"]["context"],
        observation_unit=fixture["input"]["observation_unit"],
    )
    path = tmp_path / "fixture_contract.xlsx"
    export_result = xlsx.export_xlsx(store, created["revision"], str(path))
    assert export_result["losses"] == fixture["expected"]["losses"]
    assert export_result["notes"] == fixture["expected"]["notes"]
    assert export_result["rows"] == fixture["expected"]["row_count"]

    # Verify physical structure of exported OOXML package
    with zipfile.ZipFile(path) as archive:
        namelist = set(archive.namelist())
        assert "xl/worksheets/sheet1.xml" in namelist
        assert "xl/worksheets/sheet2.xml" in namelist
        assert xlsx.CUSTOM_PART in namelist
        sheet1 = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert 't="inlineStr"' in sheet1

    # Re-import in an independent Store instance
    store2 = Store(tmp_path / "independent_store")
    imported = xlsx.import_xlsx(store2, str(path))
    assert imported["context"] == fixture["expected"]["context"]
    assert imported["observation_unit"] == fixture["expected"]["observation_unit"]
    assert imported["fields"] == created["fields"]
    assert imported["row_count"] == fixture["expected"]["row_count"]

    page = store2.page(imported["revision"])
    assert page["row_ids"] == fixture["expected"]["row_ids"]
    assert page["rows"] == fixture["expected"]["rows"]
    # Check bit-level representation of -0.0
    assert struct.pack("<d", page["rows"][0][1]) == bytes.fromhex("0000000000000080")

    # Multi-sheet workbook with cached formula cells
    multi_path = tmp_path / "multi_sheet_formulas.xlsx"
    sheet1_content = row(1, text("A1", "Aux") + text("B1", "Val")) + row(
        2, text("A2", "x") + '<c r="B2"><v>10</v></c>'
    )
    formulas_content = (
        row(
            1,
            text("A1", "ID")
            + text("B1", "SumFormula")
            + text("C1", "TextFormula")
            + text("D1", "BoolFormula"),
        )
        + row(
            2,
            '<c r="A2"><v>1</v></c>'
            + '<c r="B2"><f>1+1</f><v>2</v></c>'
            + '<c r="C2" t="str"><f>CONCAT("a","b")</f><v>ab</v></c>'
            + '<c r="D2" t="b"><f>1&gt;0</f><v>1</v></c>',
        )
        + row(
            3,
            '<c r="A3"><v>2</v></c>'
            + '<c r="B3"><v>5</v></c>'
            + text("C3", "static")
            + '<c r="D3" t="b"><v>0</v></c>',
        )
    )
    parts = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            "</Types>"
        ),
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>'
            '<sheet name="Auxiliary" sheetId="1" r:id="r1"/>'
            '<sheet name="Formulas" sheetId="2" r:id="r2"/>'
            "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{xlsx.REL_NS}">'
            f'<Relationship Id="r1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="r2" Type="{REL}/worksheet" Target="worksheets/sheet2.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{NS}"><sheetData>{sheet1_content}</sheetData></worksheet>'
        ),
        "xl/worksheets/sheet2.xml": (
            f'<worksheet xmlns="{NS}"><sheetData>{formulas_content}</sheetData></worksheet>'
        ),
    }
    with zipfile.ZipFile(multi_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)

    # Import default sheet (first sheet = Auxiliary)
    aux_imported = xlsx.import_xlsx(store2, str(multi_path))
    assert [f["name"] for f in aux_imported["fields"]] == ["Aux", "Val"]

    # Import specific sheet by name ("Formulas") with formula cached values
    formula_imported = xlsx.import_xlsx(store2, str(multi_path), sheet="Formulas")
    raw_spec = fixture["expected"]["raw_sheets"]
    for expected_field, actual_field in zip(
        raw_spec["expected_fields"], formula_imported["fields"], strict=True
    ):
        assert actual_field["name"] == expected_field["name"]
        assert actual_field["storage"] == expected_field["storage"]
        assert actual_field["measurement"] == expected_field["measurement"]
    formula_page = store2.page(formula_imported["revision"])
    assert formula_page["rows"] == raw_spec["expected_rows"]
