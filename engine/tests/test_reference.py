from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from openstat_engine.store import Store


@pytest.mark.feature("DATA-003")
@pytest.mark.feature("DATA-004")
@pytest.mark.feature("DATA-005")
def test_original_codebook_contract(
    store: Store, tmp_path: Path, reference_fixture: Callable[[str], dict[str, Any]]
) -> None:
    fixture = reference_fixture("engine/fixtures/foundations/codebook.json")
    result = store.create("Original contract", fixture["input"]["fields"], fixture["input"]["rows"])
    store.save(result["revision"], str(tmp_path / "Original.openstat"))
    reopened = store.open(str(tmp_path / "Original.openstat"))
    page = store.page(reopened["revision"])
    expected = fixture["expected"]
    assert page["rows"] == expected["rows"]
    assert page["row_ids"] == expected["row_ids"]
    field = reopened["fields"][0]
    assert list(field["levels"]) == expected["rank_levels"]
    assert field["value_labels"] == expected["rank_value_labels"]
    assert list(field["missing_codes"]) == expected["rank_missing_codes"]
    assert list(reopened["fields"][2]["missing_codes"]) == expected["numeric_missing_codes"]
