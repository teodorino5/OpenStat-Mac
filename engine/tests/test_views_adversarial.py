import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from openstat_engine import jobs, views
from openstat_engine.errors import EngineError
from openstat_engine.store import ROW_ID, Store, digest


def test_noncontiguous_row_ids_survive_sort_filter_extend_edit_save_open(
    store: Store, tmp_path: Path
) -> None:
    source = store.create(
        "Stable IDs",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[20], [10]],
    )
    item = store.get(source["revision"])
    table = pq.read_table(item.base)
    table = table.set_column(0, ROW_ID, pa.array([9, 2], type=pa.int64()))
    pq.write_table(table, item.base)

    sorted_result = views.sort_cases(store, source["revision"], [{"field": "x"}])
    assert store.page(sorted_result["revision"])["row_ids"] == [2, 9]
    assert store.page(source["revision"])["row_ids"] == [9, 2]
    filtered = views.filter_cases(
        store, sorted_result["revision"], {"op": "ge", "field": "x", "value": 10}
    )
    appended = store.extend(filtered["revision"], rows=1)
    edited = store.edit(appended["revision"], 9, "x", 25)
    saved = tmp_path / "Stable.openstat"
    store.save(edited["revision"], str(saved))
    reopened_store = Store(tmp_path / "reopened")
    reopened = reopened_store.open(str(saved))
    page = reopened_store.page(reopened["revision"])
    assert page["row_ids"] == [2, 9, 10]
    assert page["rows"] == [[10], [25], [None]]


def test_open_rejects_duplicate_row_ids_after_valid_checksums(
    store: Store, tmp_path: Path
) -> None:
    source = store.create(
        "Duplicate IDs",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[1], [2]],
    )
    project = tmp_path / "Duplicate.openstat"
    store.save(source["revision"], str(project))
    manifest_path = project / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    data_path = project / manifest["data"]
    table = pq.read_table(data_path)
    table = table.set_column(0, ROW_ID, pa.array([0, 0], type=pa.int64()))
    pq.write_table(table, data_path)
    manifest["sha256"] = digest(data_path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(EngineError, match="error.project_schema"):
        Store(tmp_path / "bad-open").open(str(project))


def test_frequency_weights_keep_exact_int64_sums(store: Store) -> None:
    source = store.create(
        "Large counts",
        [{"id": "w", "name": "Weight", "storage": "int64", "measurement": "discrete"}],
        [[2**63 - 1], [2**63 - 1]],
    )
    result = views.weights(store, source["revision"], "w")
    assert type(result["total_weight"]) is int
    assert result["total_weight"] == 2 * (2**63 - 1)


def test_analytic_weight_sum_overflow_is_engine_error(store: Store) -> None:
    source = store.create(
        "Large analytic weights",
        [{"id": "w", "name": "Weight", "storage": "float64", "measurement": "continuous"}],
        [[1e308], [1e308]],
    )
    with pytest.raises(EngineError, match="error.weight_value"):
        views.weights(store, source["revision"], "w", kind="analytic")


def test_ordinal_predicates_use_level_order(store: Store) -> None:
    source = store.create(
        "Ordered categories",
        [{
            "id": "rating",
            "name": "Rating",
            "storage": "string",
            "measurement": "ordinal",
            "levels": ["low", "middle", "high"],
        }],
        [["low"], ["middle"], ["high"], [None]],
    )
    selected = views.select(
        store, source["revision"], {"op": "lt", "field": "rating", "value": "high"}
    )
    assert selected["selected"] == 2
    assert selected["unknown"] == 1


def test_predicate_rejects_unhashable_operator_as_engine_error(store: Store) -> None:
    source = store.create(
        "Malformed predicate",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[1]],
    )
    with pytest.raises(EngineError, match="error.predicate"):
        views.select(store, source["revision"], {"op": [], "field": "x", "value": 1})


def test_sort_cancellation_during_merge_cleans_files(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = store.create(
        "Sort cancellation",
        [{"id": "x", "name": "Value", "storage": "int64", "measurement": "discrete"}],
        [[i] for i in range(9000, 0, -1)],
    )
    active_job = SimpleNamespace(lock=threading.RLock(), cancel_requested=False, progress=None)
    original_merge = views._merge

    def cancel_then_merge(*args: Any, **kwargs: Any) -> None:
        with active_job.lock:
            active_job.cancel_requested = True
        original_merge(*args, **kwargs)

    monkeypatch.setattr(views, "_merge", cancel_then_merge)
    before = set(store.directory.glob("*.parquet"))
    previous = getattr(jobs._context, "job", None)
    jobs._context.job = active_job
    try:
        with pytest.raises(EngineError, match="error.job_cancelled"):
            views.sort_cases(store, source["revision"], [{"field": "x"}])
    finally:
        if previous is None:
            del jobs._context.job
        else:
            jobs._context.job = previous
    assert set(store.directory.glob("*.parquet")) == before
    assert not list(store.directory.glob("openstat-sort-*"))

