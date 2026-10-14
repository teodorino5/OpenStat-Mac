"""Cross-module pipeline contracts for exact values and stable case IDs."""

import struct
from pathlib import Path

import pytest

from openstat_engine import columns, interchange, views, xlsx
from openstat_engine.store import Store


@pytest.mark.feature("DATA-006")
@pytest.mark.feature("DATA-010")
@pytest.mark.feature("DATA-030")
def test_compute_filter_sort_export_reimport_and_edit(
    store: Store, tmp_path: Path
) -> None:
    fields = [
        {
            "id": "x",
            "name": "Measure",
            "storage": "float64",
            "measurement": "continuous",
            "missing_codes": ["-999.0"],
        },
        {
            "id": "group",
            "name": "Group",
            "storage": "string",
            "measurement": "nominal",
            "levels": ["A", "B"],
            "missing_codes": ["?"],
        },
    ]
    source = store.create(
        "Pipeline",
        fields,
        [[3.0, "A"], [-0.0, "?"], [None, "B"], [-999.0, "A"], [2.0, None]],
        "sample",
        "case",
    )
    expression = {"op": "multiply", "args": [{"field": "x"}, {"constant": 2}]}
    derived = columns.compute(store, source["revision"], "Double", expression)
    y = derived["fields"][-1]["id"]
    filtered = views.filter_cases(
        store, derived["revision"], {"op": "ge", "field": y, "value": 0}
    )
    ordered = views.sort_cases(
        store, filtered["revision"], [{"field": y, "ascending": False}]
    )
    assert store.page(ordered["revision"])["row_ids"] == [0, 4, 1]
    edited = store.edit(ordered["revision"], 4, "x", 8.0)
    expected_rows = [[3.0, "A", 6.0], [8.0, None, 4.0], [-0.0, "?", -0.0]]
    expected_ids = [0, 4, 1]
    assert store.page(edited["revision"])["rows"] == expected_rows

    export_import = [
        ("json", interchange.export_json, interchange.import_json),
        ("parquet", interchange.export_parquet, interchange.import_parquet),
        ("xlsx", xlsx.export_xlsx, xlsx.import_xlsx),
    ]
    for suffix, export, import_ in export_import:
        path = tmp_path / f"pipeline.{suffix}"
        export(store, edited["revision"], str(path))
        restored = import_(store, str(path))
        page = store.page(restored["revision"])
        assert page["row_ids"] == expected_ids
        assert page["rows"] == expected_rows
        assert restored["fields"] == edited["fields"]
        assert restored["context"] == "sample"
        assert restored["observation_unit"] == "case"
        after_edit = store.edit(restored["revision"], 4, "x", -0.0)
        assert store.page(after_edit["revision"])["row_ids"] == expected_ids
        assert struct.pack("<d", store.page(after_edit["revision"])["rows"][2][0]) == bytes.fromhex(
            "0000000000000080"
        )
