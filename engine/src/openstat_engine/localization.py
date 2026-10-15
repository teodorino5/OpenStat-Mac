"""English and Czech localization: String Catalog access, locale-aware parsing and collation."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import EngineError

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = ROOT_DIR / "App/Resources/Localizable.xcstrings"

# Czech alphabet order according to CSN 97 6030
# 'ch' is treated as a separate primary letter between 'h' and 'i'.
CZECH_ALPHABET = [
    "a", "á", "b", "c", "č", "d", "ď", "e", "é", "ě",
    "f", "g", "h", "ch", "i", "í", "j", "k", "l", "m",
    "n", "ň", "o", "ó", "p", "q", "r", "ř", "s", "š",
    "t", "ť", "u", "ú", "ů", "v", "w", "x", "y", "ý",
    "z", "ž",
]
CZECH_CHAR_MAP = {letter: idx for idx, letter in enumerate(CZECH_ALPHABET)}


@dataclass(frozen=True)
class LocaleConfig:
    identifier: str
    language: str
    decimal_separator: str
    grouping_separator: str


LOCALES = {
    "en": LocaleConfig(
        identifier="en",
        language="en",
        decimal_separator=".",
        grouping_separator=",",
    ),
    "en_us": LocaleConfig(
        identifier="en_US",
        language="en",
        decimal_separator=".",
        grouping_separator=",",
    ),
    "cs": LocaleConfig(
        identifier="cs",
        language="cs",
        decimal_separator=",",
        grouping_separator=" ",
    ),
    "cs_cz": LocaleConfig(
        identifier="cs_CZ",
        language="cs",
        decimal_separator=",",
        grouping_separator=" ",
    ),
}


def get_locale_config(locale: str) -> LocaleConfig:
    key = locale.lower().replace("-", "_")
    if key in LOCALES:
        return LOCALES[key]
    if key.startswith("cs"):
        return LOCALES["cs"]
    return LOCALES["en"]


def parse_localized_number(text: str, locale: str = "en") -> float:
    """Parse a locale-formatted decimal number string into float."""
    if not isinstance(text, str):
        raise EngineError("error.operation_options")
    cleaned = text.strip().replace("\u00a0", " ").replace("\u202f", " ")
    if not cleaned:
        raise EngineError("error.operation_options")

    cfg = get_locale_config(locale)
    if cfg.language == "cs":
        integer = r"(?:\d{1,3}(?: \d{3})+|\d+)"
        decimal = ","
        grouping = " "
    else:
        integer = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
        decimal = r"\."
        grouping = ","

    number_pattern = rf"[+-]?(?:{integer}(?:{decimal}\d*)?|{decimal}\d+)(?:[eE][+-]?\d+)?"
    if re.fullmatch(number_pattern, cleaned) is None:
        raise EngineError("error.operation_options")

    normalized = cleaned.replace(grouping, "").replace(cfg.decimal_separator, ".")

    # Preserve negative zero token
    is_neg_zero = normalized in {"-0", "-0.0", "-0."}
    try:
        val = float(normalized)
    except ValueError as exc:
        raise EngineError("error.operation_options") from exc

    if not math.isfinite(val):
        raise EngineError("error.nonfinite")

    return -0.0 if is_neg_zero else val


def format_localized_number(
    value: float,
    locale: str = "en",
    precision: int | None = None,
) -> str:
    """Format a float using locale conventions."""
    if not isinstance(value, (int, float)):
        raise EngineError("error.operation_options")
    if not math.isfinite(value):
        raise EngineError("error.nonfinite")

    cfg = get_locale_config(locale)
    is_neg = math.copysign(1.0, value) < 0 and value == 0.0

    if precision is not None:
        if precision < 0:
            raise EngineError("error.operation_options")
        formatted = f"{value:.{precision}f}"
    else:
        formatted = str(value)

    if is_neg and not formatted.startswith("-"):
        formatted = f"-{formatted}"

    if cfg.decimal_separator != ".":
        formatted = formatted.replace(".", cfg.decimal_separator)

    return formatted


def czech_sort_key(s: str) -> list[int]:
    """Generate a sort key for Czech text taking into account 'ch' and diacritics."""
    tokens: list[str] = []
    i = 0
    lower = s.lower()
    while i < len(lower):
        if i + 1 < len(lower) and lower[i : i + 2] == "ch":
            tokens.append("ch")
            i += 2
        else:
            tokens.append(lower[i])
            i += 1

    return [
        CZECH_CHAR_MAP[token] if token in CZECH_CHAR_MAP else ord(token[0]) + 1000
        for token in tokens
    ]


def sort_strings(items: list[str], locale: str = "en") -> list[str]:
    """Sort a list of strings using the specified locale rules."""
    cfg = get_locale_config(locale)
    if cfg.language == "cs":
        return sorted(items, key=czech_sort_key)
    return sorted(items)


class StringCatalog:
    """Read-only access to compiled String Catalog resources."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CATALOG_PATH
        self._data: dict[str, Any] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    @property
    def is_loaded(self) -> bool:
        return bool(self._data)

    def total_keys(self) -> int:
        return len(self._data.get("strings", {}))

    def translate(self, key: str, locale: str = "en") -> str:
        cfg = get_locale_config(locale)
        strings = self._data.get("strings", {})
        if key not in strings:
            raise EngineError("error.unknown_field")
        loc_entry = strings[key].get("localizations", {})
        lang_entry = loc_entry.get(cfg.language)
        if not lang_entry:
            lang_entry = loc_entry.get("en", {})
        val = lang_entry.get("stringUnit", {}).get("value")
        if val is None:
            raise EngineError("error.unknown_field")
        return str(val)

    def catalog_info(self) -> dict[str, Any]:
        strings = self._data.get("strings", {})
        total = len(strings)
        en_count = sum(1 for e in strings.values() if "en" in e.get("localizations", {}))
        cs_count = sum(1 for e in strings.values() if "cs" in e.get("localizations", {}))
        return {
            "total_keys": total,
            "languages": ["en", "cs"],
            "coverage": {
                "en": en_count / total if total > 0 else 0.0,
                "cs": cs_count / total if total > 0 else 0.0,
            },
        }
