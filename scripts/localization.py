"""Compile the checked-in String Catalog for Command Line Tools contributor builds."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "App/Resources/Localizable.xcstrings"


def compile_catalog() -> None:
    catalog = json.loads(CATALOG.read_text())
    for language in ("en", "cs"):
        target = CATALOG.parent / f"{language}.lproj"
        target.mkdir(exist_ok=True)
        rows = []
        for key, entry in sorted(catalog["strings"].items()):
            value = entry["localizations"][language]["stringUnit"]["value"]
            rows.append(
                f"{json.dumps(key, ensure_ascii=False)} = {json.dumps(value, ensure_ascii=False)};"
            )
        (target / "Localizable.strings").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    compile_catalog()
