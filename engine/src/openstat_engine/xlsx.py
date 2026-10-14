"""Original bounded OOXML tabular subset; never evaluates workbook code."""

import math
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import IO, Any
from uuid import uuid4
from xml.sax.saxutils import escape

import pyarrow as pa

from .errors import EngineError
from .interchange import (
    BATCH_ROWS,
    METADATA_LIMIT,
    _decode,
    _definitions,
    _destination,
    _encode,
    _import_batches,
    _metadata,
    _schema,
)
from .model import Field, validate_fields
from .store import ARROW_TYPES, ROW_ID, Store

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MAX_MEMBERS = 128
MAX_EXPANDED = 128 * 1024 * 1024
MAX_PART = 64 * 1024 * 1024
MAX_ROWS = 1_048_575
MAX_COLUMNS = 1024
MAX_STRINGS = 1_000_000
DATA_SHEET = "Data"
ID_SHEET = "_OpenStat_RowIDs"
CUSTOM_PART = "customXml/openstat.xml"


def _tag(name: str) -> str:
    return "{" + NS + "}" + name


def _xml_check(archive: zipfile.ZipFile, name: str) -> None:
    tail = b""
    with archive.open(name) as stream:
        while chunk := stream.read(65536):
            scanned = (tail + chunk).upper()
            if b"<!DOCTYPE" in scanned or b"<!ENTITY" in scanned or b"\x00" in scanned:
                raise EngineError("error.xlsx_schema")
            tail = scanned[-16:]


def _tree(archive: zipfile.ZipFile, name: str) -> ET.Element:
    _xml_check(archive, name)
    return ET.fromstring(archive.read(name))


def _validate_archive(archive: zipfile.ZipFile) -> None:
    members = archive.infolist()
    if len(members) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_EXPANDED:
        raise EngineError("error.xlsx_limit")
    seen = set()
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        if (
            name in seen
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or member.flag_bits & 1
            or name.endswith("/")
            or member.file_size > MAX_PART
            or member.file_size > max(1, member.compress_size) * 1000
        ):
            raise EngineError("error.xlsx_schema")
        seen.add(name)
        if "vba" in name.lower() or "externallinks" in name.lower():
            raise EngineError("error.xlsx_unsafe")
        if name.endswith(".rels"):
            for relation in _tree(archive, name):
                if (
                    relation.attrib.get("TargetMode") == "External"
                    or "externalLink" in relation.attrib.get("Type", "")
                    or "vbaProject" in relation.attrib.get("Type", "")
                ):
                    raise EngineError("error.xlsx_unsafe")
    for required in ("[Content_Types].xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"):
        if required not in seen:
            raise EngineError("error.xlsx_schema")
    content = _tree(archive, "[Content_Types].xml")
    if any("macroEnabled" in e.attrib.get("ContentType", "") for e in content):
        raise EngineError("error.xlsx_unsafe")


def _sheets(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = _tree(archive, "xl/workbook.xml")
    relations = {}
    for relation in _tree(archive, "xl/_rels/workbook.xml.rels"):
        if relation.attrib.get("Type") == DOC_REL + "/worksheet":
            target = relation.attrib["Target"]
            destination = posixpath.normpath(posixpath.join("xl", target))
            if target.startswith("/"):
                destination = target[1:]
            if (
                not destination.startswith("xl/worksheets/")
                or destination not in archive.namelist()
            ):
                raise EngineError("error.xlsx_schema")
            relations[relation.attrib["Id"]] = destination
    result = {}
    for sheet in workbook.findall("./" + _tag("sheets") + "/" + _tag("sheet")):
        name = sheet.attrib["name"]
        if name in result:
            raise EngineError("error.xlsx_schema")
        result[name] = relations[sheet.attrib["{" + DOC_REL + "}id"]]
    if not result:
        raise EngineError("error.xlsx_schema")
    return result


def _shared(archive: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in archive.namelist():
        return []
    _xml_check(archive, name)
    strings = []
    with archive.open(name) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == _tag("si"):
                strings.append("".join(t.text or "" for t in element.iter(_tag("t"))))
                element.clear()
                if len(strings) > MAX_STRINGS:
                    raise EngineError("error.xlsx_limit")
    return strings


def _cell_value(cell: ET.Element, shared: list[str]) -> Any:
    if cell.find(_tag("f")) is not None:
        raise EngineError("error.xlsx_unsafe")
    if cell.attrib.get("s", "0") != "0":
        raise EngineError("error.xlsx_style")
    kind = cell.attrib.get("t", "n")
    value = cell.find(_tag("v"))
    text = value.text if value is not None else None
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(_tag("t")))
    if text is None:
        return None
    if kind == "s":
        index = int(text)
        if not 0 <= index < len(shared):
            raise EngineError("error.xlsx_schema")
        return shared[index]
    if kind == "b":
        if text not in ("0", "1"):
            raise EngineError("error.xlsx_schema")
        return text == "1"
    if kind in {"str", "e", "d"}:
        raise EngineError("error.xlsx_style")
    if kind != "n":
        raise EngineError("error.xlsx_schema")
    if re.fullmatch(r"[+-]?\d+", text):
        number: Any = int(text)
        if not -(2**63) <= number < 2**63:
            raise EngineError("error.integer_range")
    else:
        number = float(text)
        if not math.isfinite(number):
            raise EngineError("error.nonfinite")
    return number


def _column(reference: str) -> int:
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", reference)
    if not match:
        raise EngineError("error.xlsx_schema")
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - ord("A") + 1
    if column > MAX_COLUMNS:
        raise EngineError("error.xlsx_limit")
    return column - 1


def _rows(archive: zipfile.ZipFile, name: str, shared: list[str]) -> Iterator[list[Any]]:
    _xml_check(archive, name)
    previous = 0
    width = 0
    with archive.open(name) as stream:
        parser = ET.iterparse(stream, events=("start", "end"))
        root = next(parser)[1]
        for event, row in parser:
            if event != "end" or row.tag != _tag("row"):
                continue
            index = int(row.attrib.get("r", previous + 1))
            if index <= previous or index > MAX_ROWS + 1:
                raise EngineError("error.xlsx_limit")
            if previous == 0 and index != 1:
                raise EngineError("error.xlsx_schema")
            for _ in range(previous + 1, index):
                yield [None] * width
            values: dict[int, Any] = {}
            for cell in row.findall(_tag("c")):
                reference = cell.attrib.get("r", "")
                column = _column(reference)
                suffix = re.search(r"\d+$", reference)
                if column in values or suffix is None or int(suffix[0]) != index:
                    raise EngineError("error.xlsx_schema")
                values[column] = _cell_value(cell, shared)
            if previous == 0:
                width = max(values, default=-1) + 1
                if not width:
                    raise EngineError("error.xlsx_schema")
            if max(values, default=-1) >= width:
                raise EngineError("error.row_width")
            yield [values.get(i) for i in range(width)]
            previous = index
            row.clear()
            # Clear completed rows from sheetData to avoid retaining an empty element per case.
            for data in root.findall(_tag("sheetData")):
                data.clear()
    if previous == 0:
        raise EngineError("error.xlsx_schema")


def _letter(index: int) -> str:
    output = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        output = chr(65 + remainder) + output
    return output


class _PartWriter:
    def __init__(self, stream: IO[bytes]) -> None:
        self.stream = stream
        self.size = 0

    def write(self, text: str) -> None:
        data = text.encode("utf-8")
        if self.size + len(data) > MAX_PART:
            raise EngineError("error.xlsx_limit")
        self.stream.write(data)
        self.size += len(data)


def _cell(reference: str, value: Any, kind: str) -> str:
    if value is None:
        return ""
    if kind == "bool":
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if kind == "int64" and abs(value) < 10**15:
        return f'<c r="{reference}"><v>{value}</v></c>'
    text = _encode(value) if kind == "multiple_response" else str(value)
    if len(text) > 32767:
        raise EngineError("error.xlsx_limit")
    if any(ord(c) < 32 and c not in "\t\n\r" for c in text):
        raise EngineError("error.xlsx_schema")
    return (
        f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'
    )


def export_xlsx(store: Store, revision: str, path: str, overwrite: bool = False) -> dict[str, Any]:
    item = store.get(revision)
    metadata = _metadata(item)
    metadata["data_sheet"] = DATA_SHEET
    metadata["id_sheet"] = ID_SHEET
    encoded = _encode(metadata)
    _definitions(_decode(encoded))
    if (
        item.row_count > MAX_ROWS
        or len(item.fields) > MAX_COLUMNS
        or len(encoded.encode()) > METADATA_LIMIT
    ):
        raise EngineError("error.xlsx_limit")
    with (
        _destination(store, path, overwrite) as staging,
        zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as archive,
    ):
        archive.writestr(
            "[Content_Types].xml",
            """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels"
ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml"
ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml"
ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml"
ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml"
ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            f'''<Relationships xmlns="{REL_NS}">
<Relationship Id="r1" Type="{DOC_REL}/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="r2" Type="{DOC_REL}/customXml" Target="{CUSTOM_PART}"/>
</Relationships>''',
        )
        archive.writestr(
            "xl/workbook.xml",
            f'''<workbook xmlns="{NS}" xmlns:r="{DOC_REL}"><sheets>
<sheet name="{DATA_SHEET}" sheetId="1" r:id="r1"/>
<sheet name="{ID_SHEET}" sheetId="2" state="veryHidden" r:id="r2"/></sheets></workbook>''',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'''<Relationships xmlns="{REL_NS}">
<Relationship Id="r1" Type="{DOC_REL}/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="r2" Type="{DOC_REL}/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>''',
        )
        archive.writestr(
            CUSTOM_PART,
            '<openstat xmlns="urn:openstat:interchange:v1">' + escape(encoded) + "</openstat>",
        )
        with archive.open("xl/worksheets/sheet1.xml", "w") as raw_stream:
            stream = _PartWriter(raw_stream)
            stream.write(f'<worksheet xmlns="{NS}"><sheetData><row r="1">')
            for column, field in enumerate(item.fields, 1):
                stream.write(_cell(_letter(column) + "1", field.name, "string"))
            stream.write("</row>")
            index = 2
            for batch in store.iter_tables(revision, batch_size=BATCH_ROWS):
                values = batch.to_pydict()
                for row in range(batch.num_rows):
                    stream.write(f'<row r="{index}">')
                    for column, field in enumerate(item.fields, 1):
                        stream.write(
                            
                            _cell(
                                _letter(column) + str(index), values[field.id][row], field.storage
                            ),
                        )
                    stream.write("</row>")
                    index += 1
            stream.write("</sheetData></worksheet>")
        with archive.open("xl/worksheets/sheet2.xml", "w") as raw_stream:
            stream = _PartWriter(raw_stream)
            stream.write(
                f'<worksheet xmlns="{NS}"><sheetData><row r="1">'
                + _cell("A1", ROW_ID, "string")
                + "</row>"
            )
            index = 2
            for batch in store.iter_tables(revision, batch_size=BATCH_ROWS):
                for row_id in batch.column(ROW_ID).to_pylist():
                    stream.write(
                        
                        f'<row r="{index}">'
                        + _cell("A" + str(index), str(row_id), "string")
                        + "</row>",
                    )
                    index += 1
            stream.write("</sheetData></worksheet>")
        members = archive.infolist()
        if sum(m.file_size for m in members) > MAX_EXPANDED or any(
            m.file_size > MAX_PART for m in members
        ):
            raise EngineError("error.xlsx_limit")
    return {
        "path": str(Path(path).absolute()),
        "rows": item.row_count,
        "losses": [],
        "notes": ["float64_and_large_int64_are_text", "metadata_required_for_typed_roundtrip"],
    }


def _typed(store: Store, field: Field, cell: Any) -> Any:
    if cell is None:
        return None
    if field.storage == "int64" and isinstance(cell, str):
        if not re.fullmatch(r"[+-]?\d+", cell):
            raise EngineError("error.value_type")
        cell = int(cell)
    elif field.storage == "float64" and isinstance(cell, str):
        cell = float(cell)
    elif field.storage == "multiple_response" and isinstance(cell, str):
        cell = _decode(cell)
    return store._value(field, cell)


def import_xlsx(store: Store, path: str, sheet: str | None = None) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            _validate_archive(archive)
            if "xl/styles.xml" in archive.namelist():
                styles = _tree(archive, "xl/styles.xml")
                defaults = styles.find(_tag("cellXfs"))
                if (
                    defaults is not None
                    and len(defaults)
                    and defaults[0].attrib.get("numFmtId", "0") != "0"
                ):
                    raise EngineError("error.xlsx_style")
            sheets = _sheets(archive)
            selected = sheet if sheet is not None else next(iter(sheets))
            if selected not in sheets:
                raise EngineError("error.xlsx_sheet")
            shared = _shared(archive)
            iterator = _rows(archive, sheets[selected], shared)
            header = next(iterator)
            if not all(isinstance(h, str) and h.strip() for h in header) or len(set(header)) != len(
                header
            ):
                raise EngineError("error.field_name")
            metadata = None
            identities: Iterator[list[Any]] | None = None
            if CUSTOM_PART in archive.namelist():
                if archive.getinfo(CUSTOM_PART).file_size > METADATA_LIMIT:
                    raise EngineError("error.xlsx_limit")
                metadata = _decode(_tree(archive, CUSTOM_PART).text or "")
                if selected != metadata.get("data_sheet"):
                    metadata = None
                else:
                    _, fields, _, _ = _definitions(metadata)
                    if [f.name for f in fields] != header:
                        raise EngineError("error.xlsx_schema")
                    identities = _rows(archive, sheets[metadata["id_sheet"]], shared)
                    if next(identities) != [ROW_ID]:
                        raise EngineError("error.xlsx_schema")
            if metadata is None:
                flags: list[set[str]] = [set() for _ in header]
                for row in iterator:
                    for index, cell in enumerate(row):
                        if cell is not None:
                            flags[index].add(
                                "bool"
                                if isinstance(cell, bool)
                                else "int64"
                                if isinstance(cell, int)
                                else "float64"
                                if isinstance(cell, float)
                                else "string"
                            )
                fields_list = []
                for name, candidates in zip(header, flags, strict=True):
                    if (
                        not candidates
                        or "string" in candidates
                        or ("bool" in candidates and len(candidates) > 1)
                    ):
                        storage = "string"
                    else:
                        storage = "float64" if "float64" in candidates else next(iter(candidates))
                    measurement = {
                        "int64": "discrete",
                        "float64": "continuous",
                        "bool": "binary",
                    }.get(storage, "nominal")
                    fields_list.append(Field(str(uuid4()), name, storage, measurement))
                fields = tuple(fields_list)
                validate_fields(fields)
                metadata = {
                    "format": "openstat-data",
                    "version": 1,
                    "dataset": {
                        "name": Path(path).stem,
                        "fields": [f.to_dict() for f in fields],
                        "context": "unspecified",
                        "observation_unit": "",
                    },
                }
                # Field.asdict tuples are normalized through the wire representation.
                metadata = _decode(_encode(metadata))
                iterator = _rows(archive, sheets[selected], shared)
                next(iterator)

            def batches() -> Iterator[Any]:
                values: list[list[Any]] = [[] for _ in fields]
                ids: list[int] = []
                count = 0
                for row in iterator:
                    if identities is None:
                        row_id = count
                    else:
                        identity = next(identities, None)
                        if (
                            identity is None
                            or len(identity) != 1
                            or not isinstance(identity[0], str)
                            or not re.fullmatch(r"\d+", identity[0])
                        ):
                            raise EngineError("error.xlsx_schema")
                        row_id = int(identity[0])
                        if row_id >= 2**63:
                            raise EngineError("error.integer_range")
                    ids.append(row_id)
                    for index, field in enumerate(fields):
                        cell = row[index]
                        if identities is None and field.storage == "string" and cell is not None:
                            cell = str(cell)
                        values[index].append(_typed(store, field, cell))
                    count += 1
                    if len(ids) == BATCH_ROWS:
                        yield pa.Table.from_arrays(
                            [
                                pa.array(ids, type=pa.int64()),
                                *[
                                    pa.array(v, type=ARROW_TYPES[f.storage])
                                    for f, v in zip(fields, values, strict=True)
                                ],
                            ],
                            schema=_schema(fields),
                        )
                        values = [[] for _ in fields]
                        ids = []
                if identities is not None and next(identities, None) is not None:
                    raise EngineError("error.xlsx_schema")
                if ids:
                    yield pa.Table.from_arrays(
                        [
                            pa.array(ids, type=pa.int64()),
                            *[
                                pa.array(v, type=ARROW_TYPES[f.storage])
                                for f, v in zip(fields, values, strict=True)
                            ],
                        ],
                        schema=_schema(fields),
                    )

            return _import_batches(store, metadata, batches())
    except (
        zipfile.BadZipFile,
        ET.ParseError,
        KeyError,
        ValueError,
        IndexError,
        RuntimeError,
    ) as exc:
        raise EngineError("error.xlsx_schema") from exc
