"""Generate original data-contract inputs with Apache PyArrow for the Swift reader.

The expected literal values in ArrowSmoke.swift are independently specified. These
are interoperability fixtures, not numerical reference results or source datasets.
"""

from pathlib import Path

import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/arrow-fixtures"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("_openstat_row_id", pa.int64()),
            ("i", pa.int64()),
            ("f", pa.float64()),
            ("s", pa.string()),
            ("b", pa.bool_()),
            ("m", pa.list_(pa.string())),
        ]
    )
    table = pa.table(
        {
            "_openstat_row_id": [42, 43, 44],
            "i": [-(2**63), 2**63 - 1, None],
            "f": [-0.0, 5e-324, 1.2345678901234567],
            "s": ["česky 🧪", "", None],
            "b": [True, False, None],
            "m": [["česky", "blue"], [], None],
        },
        schema=schema,
    )
    for name, options, data in [
        ("typed", None, table),
        ("empty", None, table.slice(0, 0)),
        ("compressed", pa.ipc.IpcWriteOptions(compression="zstd"), table),
        ("nonfinite", None, table.set_column(2, "f", pa.array([float("inf"), 0.0, 1.0]))),
        (
            "duplicate-response",
            None,
            table.set_column(5, "m", pa.array([["x", "x"], [], None], type=pa.list_(pa.string()))),
        ),
        (
            "null-response",
            None,
            table.set_column(5, "m", pa.array([[None], [], None], type=pa.list_(pa.string()))),
        ),
    ]:
        with (
            pa.OSFile(str(OUTPUT / f"{name}.arrow"), "wb") as sink,
            pa.ipc.new_file(sink, data.schema, options=options) as writer,
        ):
            # Multiple record batches exercise concatenation and stable row IDs.
            writer.write_table(data, max_chunksize=2)
    print("Generated 6 original Arrow interoperability inputs.")


if __name__ == "__main__":
    main()
