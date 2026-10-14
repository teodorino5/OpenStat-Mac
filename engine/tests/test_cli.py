"""Command-line acceptance tests, including real subprocess entry points."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pyreadstat
import pytest

from openstat_engine.cli import main
from openstat_engine.rpc import Service

ROOT = Path(__file__).resolve().parents[2]
ENGINE_SOURCE = ROOT / "engine" / "src"


def run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    current = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(ENGINE_SOURCE) + (os.pathsep + current if current else "")
    return subprocess.run(
        [sys.executable, "-m", "openstat_engine.cli", *arguments],
        cwd=cwd or ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def read_output(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return json.loads(result.stdout)


def test_cli_import_and_inspect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source = tmp_path / "Original.csv"
    source.write_text("Amount,Group\n1.25,blue\n2.5,red\n")
    project = tmp_path / "Original.openstat"
    monkeypatch.setattr(sys, "argv", ["openstat", "import", str(source), str(project)])
    assert main() == 0
    imported = json.loads(capsys.readouterr().out)
    assert imported["row_count"] == 2
    monkeypatch.setattr(sys, "argv", ["openstat", "inspect", str(project)])
    assert main() == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["preview"]["rows"] == [[1.25, "blue"], [2.5, "red"]]
    assert inspected["revision"] == imported["revision"]
    monkeypatch.setattr(sys, "argv", ["openstat", "inspect", str(project), "--limit", "0"])
    assert main() == 1
    assert json.loads(capsys.readouterr().err)["error"] == "error.page_bounds"
    monkeypatch.setattr(sys, "argv", ["openstat", "inspect", str(tmp_path / "absent")])
    assert main() == 1
    assert json.loads(capsys.readouterr().err)["error"] == "error.file_io"


def test_cli_serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with (
        (tmp_path / "input").open("w+b") as input_stream,
        (tmp_path / "output").open("w+b") as output,
    ):

        class Wrapper:
            def __init__(self, stream: object) -> None:
                self.buffer = stream

        monkeypatch.setattr(sys, "argv", ["openstat", "serve"])
        monkeypatch.setattr(sys, "stdin", Wrapper(input_stream))
        monkeypatch.setattr(sys, "stdout", Wrapper(output))
        assert main() == 0


def test_import_auto_tsv_and_explicit_csv_options(tmp_path: Path) -> None:
    tsv = tmp_path / "values.tsv"
    tsv.write_text("amount\tgroup\n1,5\tblue\n2,5\tred\n")
    imported = read_output(
        run_cli("import", str(tsv), str(tmp_path / "tsv.openstat"), "--decimal-point", ",")
    )
    assert imported["row_count"] == 2
    inspected = read_output(run_cli("inspect", str(tmp_path / "tsv.openstat")))
    assert inspected["preview"]["rows"] == [[1.5, "blue"], [2.5, "red"]]

    csv_path = tmp_path / "semicolon.csv"
    csv_path.write_text("amount;group\n1,5;blue\n")
    read_output(
        run_cli(
            "import",
            str(csv_path),
            str(tmp_path / "csv.openstat"),
            "--format",
            "csv",
            "--delimiter",
            ";",
            "--decimal-point",
            ",",
        )
    )
    result = read_output(run_cli("inspect", str(tmp_path / "csv.openstat")))
    assert result["preview"]["rows"] == [[1.5, "blue"]]


@pytest.mark.parametrize("format_name", ["csv", "tsv", "json", "parquet", "sqlite", "xlsx"])
def test_cli_export_import_supported_formats(tmp_path: Path, format_name: str) -> None:
    source = tmp_path / "source.csv"
    source.write_text("amount,group\n1.25,blue\n2.5,red\n")
    project = tmp_path / "source.openstat"
    read_output(run_cli("import", str(source), str(project)))
    extension = "tsv" if format_name == "tsv" else format_name
    output = tmp_path / f"roundtrip.{extension}"
    exported = read_output(run_cli("export", str(project), str(output), "--format", format_name))
    assert exported["rows"] == 2
    assert isinstance(exported["losses"], list)
    assert output.exists()
    imported_path = tmp_path / f"{format_name}.openstat"
    read_output(run_cli("import", str(output), str(imported_path), "--format", format_name))
    inspected = read_output(run_cli("inspect", str(imported_path)))
    assert inspected["preview"]["rows"] == [[1.25, "blue"], [2.5, "red"]]


def test_export_requires_explicit_overwrite_and_reports_losses(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("amount,group\n1.25,blue\n")
    project = tmp_path / "source.openstat"
    read_output(run_cli("import", str(source), str(project)))
    target = tmp_path / "result.csv"
    first = read_output(run_cli("export", str(project), str(target), "--format", "csv"))
    assert "codebook" in first["losses"]
    denied = run_cli("export", str(project), str(target), "--format", "csv")
    assert denied.returncode == 1
    assert json.loads(denied.stderr) == {"error": "error.export_exists"}
    replaced = run_cli("export", str(project), str(target), "--format", "csv", "--overwrite")
    assert read_output(replaced)["rows"] == 1


def test_transform_is_declarative_and_source_project_stays_unchanged(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("amount,group\n1,blue\n2,red\n3,blue\n")
    source_project = tmp_path / "source.openstat"
    source_info = read_output(run_cli("import", str(csv_path), str(source_project)))
    field_id = source_info["fields"][0]["id"]
    params = tmp_path / "filter.json"
    params.write_text(json.dumps({"condition": {"op": "gt", "field": field_id, "value": 1}}))
    destination = tmp_path / "filtered.openstat"
    transformed = read_output(
        run_cli(
            "transform",
            str(source_project),
            str(destination),
            "--method",
            "dataset.filter",
            "--parameters-file",
            str(params),
        )
    )
    assert transformed["row_count"] == 2
    source_after = read_output(run_cli("inspect", str(source_project)))
    destination_after = read_output(run_cli("inspect", str(destination)))
    assert source_after["revision"] == source_info["revision"]
    assert source_after["preview"]["rows"] == [[1, "blue"], [2, "red"], [3, "blue"]]
    assert destination_after["preview"]["rows"] == [[2, "red"], [3, "blue"]]

    marker = tmp_path / "executed"
    params.write_text(json.dumps({"command": f"touch {marker}"}))
    denied = run_cli(
        "transform",
        str(source_project),
        str(tmp_path / "unsafe.openstat"),
        "--method",
        "python.eval",
        "--parameters-file",
        str(params),
    )
    assert denied.returncode == 1
    assert json.loads(denied.stderr) == {"error": "error.cli_method"}
    assert not marker.exists()


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '{"condition": NaN}',
        '{"condition": {}, "condition": {}}',
        '{"revision": "forged"}',
        "{" + '"x":' * 34 + "0" + "}" * 34,
    ],
)
def test_transform_rejects_invalid_or_oversized_json_structure(tmp_path: Path, raw: str) -> None:
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n")
    project = tmp_path / "source.openstat"
    read_output(run_cli("import", str(source), str(project)))
    parameters = tmp_path / "params.json"
    parameters.write_text(raw)
    result = run_cli(
        "transform",
        str(project),
        str(tmp_path / "out.openstat"),
        "--method",
        "dataset.filter",
        "--parameters-file",
        str(parameters),
    )
    assert result.returncode == 1
    assert json.loads(result.stderr) == {"error": "error.cli_parameters"}
    assert "Traceback" not in result.stderr


def test_methods_lists_registered_rpc_methods_and_no_analyses() -> None:
    result = read_output(run_cli("methods"))
    assert "dataset.filter" in result["methods"]
    assert "columns.compute" in result["methods"]
    assert result["analysis_methods"] == []
    assert "dataset.import_sav" in result["methods"]
    assert "dataset.import_dta" in result["methods"]
    assert "dataset.import_sas7bdat" in result["methods"]
    assert "dataset.export_sav" in result["methods"]
    assert "dataset.export_dta" in result["methods"]


@pytest.mark.parametrize("format_name", ["sav", "dta"])
def test_cli_readstat_import_export_and_reimport(tmp_path: Path, format_name: str) -> None:
    source = tmp_path / f"source.{format_name}"
    writer = pyreadstat.write_sav if format_name == "sav" else pyreadstat.write_dta
    writer(
        pd.DataFrame({"score": [1.25, 2.5], "group": [1, 2]}),
        source,
        variable_value_labels={"group": {1: "Control", 2: "Treatment"}},
    )
    project = tmp_path / "source.openstat"
    imported = read_output(run_cli("import", str(source), str(project)))
    assert imported["row_count"] == 2
    assert imported["source_metadata"]["format"] == format_name
    assert "source_metadata_not_persisted" in imported["losses"]

    exported_path = tmp_path / f"exported.{format_name}"
    exported = read_output(
        run_cli("export", str(project), str(exported_path), "--format", format_name)
    )
    assert exported["rows"] == 2
    assert "row_ids" in exported["losses"]

    roundtrip_project = tmp_path / f"roundtrip-{format_name}.openstat"
    roundtrip = read_output(
        run_cli(
            "import",
            str(exported_path),
            str(roundtrip_project),
            "--format",
            format_name,
        )
    )
    inspected = read_output(run_cli("inspect", str(roundtrip_project)))
    assert inspected["preview"]["rows"] == [[1.25, 1.0], [2.5, 2.0]]
    group = next(field for field in roundtrip["fields"] if field["name"] == "group")
    assert group["value_labels"] == {"1.0": "Control", "2.0": "Treatment"}


def test_rpc_readstat_methods_and_jobs_registry(tmp_path: Path) -> None:
    source = tmp_path / "source.sav"
    pyreadstat.write_sav(pd.DataFrame({"score": [1.0, 2.0]}), source)
    service = Service(tmp_path / "rpc-store")
    expected_methods = {
        "dataset.import_sav",
        "dataset.import_dta",
        "dataset.import_sas7bdat",
        "dataset.export_sav",
        "dataset.export_dta",
    }
    assert expected_methods <= set(service.methods())
    assert expected_methods <= set(service.jobs._registry)

    response = service.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "dataset.import_sav",
            "params": {"path": str(source)},
        }
    )
    assert response is not None and response["result"]["row_count"] == 2
    descriptor = response["result"]
    target = tmp_path / "rpc-export.dta"
    exported = service.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "dataset.export_dta",
            "params": {"revision": descriptor["revision"], "path": str(target)},
        }
    )
    assert exported is not None and exported["result"]["rows"] == 2
    assert "row_ids" in exported["result"]["losses"]
    failed = service.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "dataset.import_dta",
            "params": {"path": str(tmp_path / "absent.dta")},
        }
    )
    assert failed is not None
    assert failed["error"]["message"] == "error.readstat_file"
    service.stop()


def test_transform_rejects_parameters_file_over_one_megabyte(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n")
    project = tmp_path / "source.openstat"
    read_output(run_cli("import", str(source), str(project)))
    parameters = tmp_path / "large.json"
    parameters.write_text('{"condition":{"padding":"' + "x" * (1024 * 1024) + '"}}')
    result = run_cli(
        "transform",
        str(project),
        str(tmp_path / "out.openstat"),
        "--method",
        "dataset.filter",
        "--parameters-file",
        str(parameters),
    )
    assert result.returncode == 1
    assert json.loads(result.stderr) == {"error": "error.cli_parameters"}
    assert "Traceback" not in result.stderr
