"""Reject missing translations or undeclared engine message keys."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / "App/Resources/Localizable.xcstrings").read_text())["strings"]
for key, entry in catalog.items():
    for language in ("en", "cs"):
        assert entry["localizations"][language]["stringUnit"]["value"], (key, language)
for path in (ROOT / "engine/src/openstat_engine").glob("*.py"):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith("error."):
                assert node.value in catalog, (path, node.value)
print(f"Localization checked: {len(catalog)} keys, complete English/Czech coverage.")
