import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from openstat_engine.errors import EngineError
from openstat_engine.model import Field, validate_context, validate_fields
from openstat_engine.store import PAGE_LIMIT, Store, digest, project_file


@pytest.mark.feature("DATA-001")
@pytest.mark.parametrize(
    "storage,measurement,value",
    [
        ("float64", "continuous", 2.5),
        ("int64", "discrete", 7),
        ("int64", "ordinal", 3),
        ("string", "ordinal", "middle"),
        ("bool", "binary", False),
        ("string", "nominal", "blue"),
        ("multiple_response", "multiple_response", ["blue", "red"]),
    ],
)
def test_storage_scale_role_round_trip(
    store: Store, storage: str, measurement: str, value: Any
) -> None:
    fields = [
        {
            "id": "x",
            "name": "Original field",
            "storage": storage,
            "measurement": measurement,
            "role": "identifier",
        }
    ]
    result = store.create("Original table", fields, [[value], [None]])
    page = store.page(result["revision"])
    assert page["rows"] == [[value], [None]]
    assert result["fields"][0]["role"] == "identifier"
    assert result["fields"][0]["measurement"] == measurement


@pytest.mark.feature("DATA-002")
@pytest.mark.parametrize("context", ["sample", "population", "unspecified"])
def test_context_is_explicit_and_persisted(
    store: Store, numeric: list[dict[str, str]], tmp_path: Path, context: str
) -> None:
    result = store.create("Study", numeric, [[1]], context, "Newly authored observation unit")
    store.save(result["revision"], str(tmp_path / "Study.openstat"))
    reopened = store.open(str(tmp_path / "Study.openstat"))
    assert reopened["context"] == context
    assert reopened["observation_unit"] == "Newly authored observation unit"
    assert not {"p_value", "confidence_interval", "population_estimate"} & reopened.keys()


@pytest.mark.feature("DATA-003")
@pytest.mark.feature("DATA-004")
@pytest.mark.feature("DATA-005")
def test_codebook_and_raw_missing_preserve_source(store: Store, tmp_path: Path) -> None:
    definitions = [
        {
            "id": "rank",
            "name": "Rank",
            "storage": "string",
            "measurement": "ordinal",
            "levels": ["low", "middle", "high"],
            "missing_codes": ["not-recorded"],
            "value_labels": {"low": "Low original category"},
        },
        {
            "id": "choices",
            "name": "Choices",
            "storage": "multiple_response",
            "measurement": "multiple_response",
            "levels": ["blue", "red"],
        },
    ]
    rows = [["middle", ["blue", "red"]], ["not-recorded", []], [None, None]]
    original = store.create("Codebook", definitions, rows)
    store.save(original["revision"], str(tmp_path / "Study.openstat"))
    loaded = store.open(str(tmp_path / "Study.openstat"))
    assert loaded["fields"] == original["fields"]
    assert store.page(loaded["revision"])["rows"] == rows
    assert loaded["fields"][0]["levels"] == ["low", "middle", "high"]


@pytest.mark.parametrize(
    "patch,key",
    [
        ({"name": ""}, "error.field_name"),
        ({"id": ""}, "error.field_name"),
        ({"name": "_openstat_reserved"}, "error.field_name"),
        ({"storage": "opaque"}, "error.field_type"),
        ({"measurement": "ratio"}, "error.field_type"),
        ({"role": "response"}, "error.field_role"),
        ({"storage": "string"}, "error.incompatible_measurement"),
        ({"measurement": "multiple_response"}, "error.incompatible_measurement"),
        ({"levels": ["a", "a"]}, "error.duplicate_levels"),
    ],
)
def test_invalid_field_metadata(patch: dict[str, Any], key: str) -> None:
    value = {"id": "x", "name": "X", "storage": "float64", "measurement": "continuous"} | patch
    with pytest.raises(EngineError, match=key):
        Field.from_dict(value)


def test_invalid_context_and_duplicate_variables() -> None:
    with pytest.raises(EngineError, match="error.context"):
        validate_context("made-up")
    field = Field("x", "X", "float64", "continuous")
    for fields in [(), (field, field), (field, replace(field, id="y"))]:
        with pytest.raises(EngineError, match="error.duplicate_fields"):
            validate_fields(fields)


@pytest.mark.parametrize(
    "storage,value,key",
    [
        ("string", 2, "error.value_type"),
        ("bool", 1, "error.value_type"),
        ("int64", True, "error.value_type"),
        ("int64", 1.2, "error.value_type"),
        ("int64", 2**63, "error.integer_range"),
        ("float64", True, "error.value_type"),
        ("float64", "1", "error.value_type"),
        ("float64", float("nan"), "error.nonfinite"),
        ("float64", float("inf"), "error.nonfinite"),
        ("multiple_response", "red", "error.value_type"),
        ("multiple_response", ["red", 2], "error.value_type"),
        ("multiple_response", ["red", "red"], "error.duplicate_response"),
    ],
)
def test_invalid_cell_values(store: Store, storage: str, value: Any, key: str) -> None:
    measurement = {
        "string": "nominal",
        "bool": "binary",
        "int64": "discrete",
        "float64": "continuous",
        "multiple_response": "multiple_response",
    }[storage]
    with pytest.raises(EngineError, match=key):
        store.create(
            "T",
            [{"id": "x", "name": "X", "storage": storage, "measurement": measurement}],
            [[value]],
        )


def test_codes_and_binary_categories_are_checked(store: Store) -> None:
    fields = [
        {
            "id": "x",
            "name": "X",
            "storage": "string",
            "measurement": "binary",
            "levels": ["yes", "no"],
        }
    ]
    result = store.create("T", fields, [["yes"], ["no"]])
    with pytest.raises(EngineError, match="error.unknown_level"):
        store.edit(result["revision"], 0, "x", "maybe")
    fields[0]["levels"] = []
    with pytest.raises(EngineError, match="error.binary_levels"):
        store.create("T", fields, [["yes"]])


def test_inline_shape_and_count_limit(store: Store, numeric: list[dict[str, str]]) -> None:
    with pytest.raises(EngineError, match="error.row_width"):
        store.create("T", numeric, [[]])
    with pytest.raises(EngineError, match="error.inline_limit"):
        store.create("T", numeric, [[]] * 100_001)


@pytest.mark.feature("DATA-037")
def test_page_crosses_row_groups_preserves_ids_and_projects_fields(
    store: Store, numeric: list[dict[str, str]]
) -> None:
    definitions = numeric + [
        {"id": "y", "name": "Y", "storage": "int64", "measurement": "discrete"}
    ]
    result = store.create("T", definitions, [[i / 2, i] for i in range(16_500)])
    page = store.page(result["revision"], 8188, 12, ["y"])
    assert page["row_ids"] == list(range(8188, 8200))
    assert page["rows"] == [[i] for i in range(8188, 8200)]
    assert page["fields"] == ["y"]
    assert store.page(result["revision"], 50_000)["rows"] == []
    assert store.page(result["revision"], 16_498, 10)["count"] == 2


def test_empty_table_and_invalid_pages(store: Store, numeric: list[dict[str, str]]) -> None:
    result = store.create("T", numeric, [])
    assert store.page(result["revision"])["count"] == 0
    for kwargs in [
        {"offset": -1},
        {"limit": 0},
        {"limit": PAGE_LIMIT + 1},
        {"format": "pickle"},
        {"fields": []},
        {"fields": ["absent"]},
        {"fields": ["amount", "amount"]},
    ]:
        with pytest.raises(EngineError):
            store.page(result["revision"], **kwargs)
    with pytest.raises(EngineError, match="error.stale_revision"):
        store.page("nonexistent")


@pytest.mark.feature("DATA-004")
def test_arrow_page_interoperability(store: Store, numeric: list[dict[str, str]]) -> None:
    result = store.create("T", numeric, [[2.5], [None]])
    page = store.page(result["revision"], format="arrow")
    artifact = page["artifact"]
    assert digest(Path(artifact["path"])) == artifact["sha256"]
    with pa.memory_map(artifact["path"], "r") as source:
        table = pa.ipc.open_file(source).read_all()
    assert table.to_pydict() == {"_openstat_row_id": [0, 1], "amount": [2.5, None]}
    assert store.release(artifact["handle"]) == {"released": True}
    assert not Path(artifact["path"]).exists()
    assert store.release(artifact["handle"]) == {"released": True}
    with pytest.raises(EngineError, match="error.artifact_handle"):
        store.release("../../x")


@pytest.mark.feature("DATA-038")
def test_sparse_revisions_allow_undo_without_mutating_base(
    store: Store, numeric: list[dict[str, str]]
) -> None:
    initial = store.create("T", numeric, [[3], [5], [None]])
    before = digest(store.get(initial["revision"]).base)
    first = store.edit(initial["revision"], 1, "amount", 8.0)
    second = store.edit(first["revision"], 1, "amount", 9.0)
    assert store.page(initial["revision"])["rows"] == [[3], [5], [None]]
    assert store.page(first["revision"])["rows"] == [[3], [8], [None]]
    assert store.page(second["revision"])["rows"] == [[3], [9], [None]]
    assert len(store.get(second["revision"]).edits) == 1
    assert digest(store.get(second["revision"]).base) == before
    with pytest.raises(EngineError, match="error.row_id"):
        store.edit(second["revision"], 3, "amount", 1)
    with pytest.raises(EngineError, match="error.field_id"):
        store.edit(second["revision"], 0, "missing", 1)


def test_metadata_revision_validates_existing_values(
    store: Store, numeric: list[dict[str, str]]
) -> None:
    result = store.create("T", numeric, [[1], [2]])
    fields = [dict(result["fields"][0], name="New name", role="identifier")]
    modified = store.metadata(result["revision"], fields, "sample", "plant")
    assert modified["fields"][0]["name"] == "New name"
    assert result["fields"][0]["name"] == "Amount"
    assert modified["context"] == "sample"
    with pytest.raises(EngineError, match="error.storage_change"):
        store.metadata(result["revision"], [dict(fields[0], storage="int64")], "sample", "")
    with pytest.raises(EngineError, match="error.unknown_level"):
        store.metadata(
            result["revision"], [dict(fields[0], measurement="ordinal", levels=["3"])], "sample", ""
        )


@pytest.mark.feature("DATA-028")
@pytest.mark.feature("DATA-029")
@pytest.mark.parametrize(
    "delimiter,decimal,content,expected",
    [
        (",", ".", "Name,Value\ncedar,1.5\nclover,2.75\n", [["cedar", 1.5], ["clover", 2.75]]),
        (";", ",", "Name;Value\nčervená;1,5\nmodrá;2,75\n", [["červená", 1.5], ["modrá", 2.75]]),
        ("\t", ".", "Name\tValue\ncedar\t1.5\nclover\t2.75\n", [["cedar", 1.5], ["clover", 2.75]]),
    ],
)
def test_streamed_locale_import(
    store: Store,
    tmp_path: Path,
    delimiter: str,
    decimal: str,
    content: str,
    expected: list[list[Any]],
) -> None:
    path = tmp_path / "Original.csv"
    path.write_text(content)
    result = store.import_csv(str(path), delimiter, decimal)
    assert result["row_count"] == 2
    assert store.page(result["revision"])["rows"] == expected
    assert result["context"] == "unspecified"


def test_import_type_failures_clean_staging(store: Store, tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    for delimiter, decimal in [("", "."), (",", ","), (",", ";")]:
        with pytest.raises(EngineError, match="error.csv_options"):
            store.import_csv(str(source), delimiter, decimal)
    source.write_text("Date\n2026-10-14\n")
    with pytest.raises(EngineError, match="error.csv_schema"):
        store.import_csv(str(source))
    source.write_text("X\nnan\ninf\n")
    with pytest.raises(EngineError, match="error.nonfinite"):
        store.import_csv(str(source))
    assert not list(store.directory.glob("*.parquet"))
    source.write_text("Whole,Flag\n2,true\n3,false\n")
    result = store.import_csv(str(source))
    assert store.page(result["revision"])["rows"] == [[2, True], [3, False]]


@pytest.mark.feature("DATA-036")
def test_manifest_integrity_overlay_and_source_isolation(
    store: Store, numeric: list[dict[str, str]], tmp_path: Path
) -> None:
    result = store.create("T", numeric, [[1], [None]])
    modified = store.edit(result["revision"], 0, "amount", 4.25)
    project = tmp_path / "Original česky.openstat"
    saved = store.save(modified["revision"], str(project))
    assert saved["revision"] == modified["revision"]
    store.save(modified["revision"], str(project))
    assert len(list(project.glob("data-*.parquet"))) == 1
    reopened = store.open(str(project))
    assert store.page(reopened["revision"])["rows"] == [[4.25], [None]]
    manifest = json.loads((project / "manifest.json").read_text())
    data = project / manifest["data"]
    data.write_bytes(b"corrupt")
    assert store.page(reopened["revision"])["rows"] == [[4.25], [None]]
    with pytest.raises(EngineError, match="error.checksum"):
        store.open(str(project))
    with pytest.raises(EngineError, match="error.checksum"):
        store.save(modified["revision"], str(project))


@pytest.mark.parametrize("relative", ["../outside", "/outside", ".", "nested/../../outside"])
def test_project_path_rejects_escape(tmp_path: Path, relative: str) -> None:
    with pytest.raises(EngineError, match="error.project_path"):
        project_file(tmp_path, relative)


def test_project_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(EngineError, match="error.project_path"):
        project_file(root, "escape/private")


def test_project_version_schema_and_overlay_validation(
    store: Store, numeric: list[dict[str, str]], tmp_path: Path
) -> None:
    result = store.create("T", numeric, [[1]])
    with pytest.raises(EngineError, match="error.project_path"):
        store.save(result["revision"], str(tmp_path / "invalid"))
    project = tmp_path / "Original.openstat"
    store.save(result["revision"], str(project))
    path = project / "manifest.json"
    original = json.loads(path.read_text())
    for patch, key in [
        ({"format_version": 9}, "error.project_version"),
        ({"dataset": original["dataset"] | {"row_count": 5}}, "error.project_schema"),
        ({"data": "../escape"}, "error.project_path"),
    ]:
        path.write_text(json.dumps(original | patch))
        with pytest.raises(EngineError, match=key):
            store.open(str(project))
    path.write_text(json.dumps(original))
    edits_path = project / original["edits"]
    edits_path.write_text(json.dumps([{"row": 5, "field": "amount", "value": 3}]))
    path.write_text(json.dumps(original | {"edits_sha256": digest(edits_path)}))
    with pytest.raises(EngineError, match="error.project_schema"):
        store.open(str(project))
    data = project / original["data"]
    pq.write_table(pa.table({"unexpected": [1]}), data)
    path.write_text(
        json.dumps(original | {"sha256": digest(data), "edits_sha256": digest(edits_path)})
    )
    with pytest.raises(EngineError, match="error.project_schema"):
        store.open(str(project))


def test_revision_does_not_retain_mutable_input_lists(store: Store) -> None:
    result = store.create(
        "T",
        [
            {
                "id": "x",
                "name": "X",
                "storage": "multiple_response",
                "measurement": "multiple_response",
            }
        ],
        [[[]]],
    )
    caller_value = ["blue"]
    edited = store.edit(result["revision"], 0, "x", caller_value)
    caller_value.append("red")
    assert store.page(edited["revision"])["rows"] == [[["blue"]]]


@pytest.mark.parametrize("row", [True, 0.5, "0"])
def test_row_addresses_must_be_integers(
    store: Store, numeric: list[dict[str, str]], row: Any
) -> None:
    result = store.create("T", numeric, [[1]])
    with pytest.raises(EngineError, match="error.row_id"):
        store.edit(result["revision"], row, "amount", 2)
    with pytest.raises(EngineError, match="error.page_bounds"):
        store.page(result["revision"], offset=row)


def test_binary_levels_validated_even_for_empty_data(store: Store) -> None:
    with pytest.raises(EngineError, match="error.binary_levels"):
        store.create(
            "T", [{"id": "x", "name": "X", "storage": "string", "measurement": "binary"}], []
        )


def test_unsupported_project_content_is_not_silently_lost(
    store: Store, numeric: list[dict[str, str]], tmp_path: Path
) -> None:
    result = store.create("T", numeric, [[1]])
    project = tmp_path / "Original.openstat"
    store.save(result["revision"], str(project))
    path = project / "manifest.json"
    manifest = json.loads(path.read_text())
    path.write_text(json.dumps(manifest | {"analyses": [{"id": "later-phase"}]}))
    original = path.read_bytes()
    with pytest.raises(EngineError, match="error.project_version"):
        store.open(str(project))
    assert path.read_bytes() == original


def test_arrow_page_enforces_file_budget_and_removes_oversize_artifact(
    store: Store,
) -> None:
    fields = [{"id": "text", "name": "Text", "storage": "string", "measurement": "nominal"}]
    result = store.create("Wide original input", fields, [["x" * (32 * 1024 * 1024)]])
    with pytest.raises(EngineError, match="error.arrow_limit"):
        store.page(result["revision"], format="arrow")
    assert not list(store.directory.glob("*.arrow"))


def test_arrow_page_preserves_negative_zero_and_signed_integer_bounds(store: Store) -> None:
    fields = [
        {"id": "f", "name": "Float", "storage": "float64", "measurement": "continuous"},
        {"id": "i", "name": "Integer", "storage": "int64", "measurement": "discrete"},
    ]
    result = store.create("Original bit patterns", fields, [[-0.0, -(2**63)], [5e-324, 2**63 - 1]])
    page = store.page(result["revision"], format="arrow")
    artifact = page["artifact"]
    assert artifact["bytes"] == Path(artifact["path"]).stat().st_size
    with pa.memory_map(artifact["path"], "r") as source:
        table = pa.ipc.open_file(source).read_all()
    import struct

    assert struct.pack("<d", table["f"][0].as_py()) == b"\0\0\0\0\0\0\0\x80"
    assert struct.pack("<d", table["f"][1].as_py()) == b"\1\0\0\0\0\0\0\0"
    assert table["i"].to_pylist() == [-(2**63), 2**63 - 1]


@pytest.mark.feature("DATA-038")
def test_extend_preserves_revisions_overlays_ids_and_save_open(
    store: Store, numeric: list[dict[str, str]], tmp_path: Path
) -> None:
    initial = store.create("T", numeric, [[2.5], [None]])
    edited = store.edit(initial["revision"], 0, "amount", 7.25)
    before = digest(store.get(edited["revision"]).base)
    field = {"id": "label", "name": "Label", "storage": "string", "measurement": "nominal"}
    extended = store.extend(edited["revision"], [field], rows=2)
    assert extended["id"] == initial["id"]
    assert extended["row_count"] == 4
    assert store.page(extended["revision"])["rows"] == [
        [7.25, None],
        [None, None],
        [None, None],
        [None, None],
    ]
    assert store.page(extended["revision"])["row_ids"] == [0, 1, 2, 3]
    assert store.page(initial["revision"])["rows"] == [[2.5], [None]]
    assert digest(store.get(edited["revision"]).base) == before
    changed = store.edit(extended["revision"], 3, "label", "česky")
    path = tmp_path / "Original-extended.openstat"
    store.save(changed["revision"], str(path))
    reopened = Store(tmp_path / "new-session")
    result = reopened.open(str(path))
    assert reopened.page(result["revision"])["rows"][-1] == [None, "česky"]
    assert reopened.page(result["revision"])["rows"][0] == [7.25, None]


@pytest.mark.parametrize("rows", [-1, 100001, True, 1.5])
def test_extend_rejects_invalid_case_counts(
    store: Store, numeric: list[dict[str, str]], rows: Any
) -> None:
    initial = store.create("T", numeric, [])
    with pytest.raises(EngineError, match="error.inline_limit"):
        store.extend(initial["revision"], rows=rows)
    assert len(store.revisions) == 1


@pytest.mark.parametrize(
    "storage,measurement",
    [
        ("int64", "discrete"),
        ("float64", "continuous"),
        ("bool", "binary"),
        ("string", "nominal"),
        ("multiple_response", "multiple_response"),
    ],
)
def test_extend_empty_table_with_every_storage_type(
    store: Store, numeric: list[dict[str, str]], storage: str, measurement: str
) -> None:
    initial = store.create("T", numeric, [])
    result = store.extend(
        initial["revision"],
        [{"id": "new", "name": "New", "storage": storage, "measurement": measurement}],
        rows=1,
    )
    assert store.page(result["revision"])["rows"] == [[None, None]]


def test_extend_no_change_duplicate_and_reserved_fields(
    store: Store, numeric: list[dict[str, str]]
) -> None:
    initial = store.create("T", numeric, [[1]])
    for fields, key in [
        ([], "error.empty_change"),
        (numeric, "error.duplicate_fields"),
        ([numeric[0] | {"id": "_openstat_row_id"}], "error.field_name"),
    ]:
        with pytest.raises(EngineError, match=key):
            store.extend(initial["revision"], fields)
    assert len(store.revisions) == 1


def test_extend_io_failure_removes_partial_file(
    store: Store, numeric: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = store.create("T", numeric, [[1]])
    before = set(store.directory.glob("*.parquet"))

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("original test failure")

    monkeypatch.setattr(pq.ParquetWriter, "write_table", fail)
    with pytest.raises(OSError):
        store.extend(initial["revision"], rows=1)
    assert set(store.directory.glob("*.parquet")) == before
    assert len(store.revisions) == 1


def test_extend_crosses_multiple_row_group_boundaries(
    store: Store, numeric: list[dict[str, str]]
) -> None:
    initial = store.create("Original batches", numeric, [[float(i)] for i in range(8193)])
    result = store.extend(initial["revision"], rows=8193)
    assert result["row_count"] == 16386
    boundary = store.page(result["revision"], 8191, 3)
    assert boundary["rows"] == [[8191.0], [8192.0], [None]]
    assert boundary["row_ids"] == [8191, 8192, 8193]
    last = store.page(result["revision"], 16384, 2)
    assert last["rows"] == [[None], [None]] and last["row_ids"] == [16384, 16385]


def test_command_registry_search_prototype(
    reference_fixture: Any,
) -> None:
    from openstat_engine.registry import CommandRegistry

    fixture = reference_fixture("engine/fixtures/foundations/command_launcher.json")
    expected = fixture["expected"]

    cmd_registry = CommandRegistry()

    # 1. Full command catalog and phase counts
    all_commands = cmd_registry.list_commands()
    assert len(all_commands) == expected["total_commands"]

    phase_0_commands = cmd_registry.list_commands(phase=0)
    assert len(phase_0_commands) == expected["phase_0_commands"]
    assert all(c["enabled"] for c in phase_0_commands)

    phase_1_commands = cmd_registry.list_commands(phase=1)
    assert len(phase_1_commands) == expected["phase_1_commands"]
    assert all(not c["enabled"] for c in phase_1_commands)

    # 2. Categories
    assert cmd_registry.categories() == expected["categories"]

    # 3. Query results
    query_results = expected["query_results"]

    # Empty query returns full catalog
    assert len(cmd_registry.search("")) == query_results["empty"]

    # "compute" matches columns.compute
    compute_matches = [c["id"] for c in cmd_registry.search("compute")]
    assert compute_matches == query_results["compute"]

    # "formula" keyword search matches columns.compute
    formula_matches = [c["id"] for c in cmd_registry.search("formula")]
    assert formula_matches == query_results["formula"]

    # "outlier" matches columns.outliers
    outlier_matches = [c["id"] for c in cmd_registry.search("outlier")]
    assert outlier_matches == query_results["outlier"]

    # "pivot" matches tables.pivot
    pivot_matches = [c["id"] for c in cmd_registry.search("pivot")]
    assert pivot_matches == query_results["pivot"]

    # "ttest" matches 3 t-test variants
    ttest_matches = [c["id"] for c in cmd_registry.search("ttest")]
    assert ttest_matches == query_results["ttest"]

    # Nonexistent query returns 0 matches
    assert (
        cmd_registry.search("nonexistent_command_xyz")
        == query_results["nonexistent_command_xyz"]
    )

    # 4. Phase gating in search: max_phase=0 filters out phase 1 t-tests
    p0_ttest = cmd_registry.search("ttest", max_phase=0)
    assert p0_ttest == []

    transform_commands = cmd_registry.search("", category="transform")
    assert [command["id"] for command in transform_commands] == query_results[
        "transform_category"
    ]

