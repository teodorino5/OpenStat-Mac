"""Write a local-only runtime pointer for an Xcode contributor build."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
resources = Path(sys.argv[1])
resources.mkdir(parents=True, exist_ok=True)
(resources / "development-runtime.json").write_text(
    json.dumps(
        {"python": str(root / "engine/.venv/bin/python"), "source": str(root / "engine/src")},
        indent=2,
    )
    + "\n"
)
