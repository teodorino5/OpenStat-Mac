"""Accessibility and appearance: VoiceOver semantics, focus cycles, WCAG contrast and themes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .errors import EngineError


def parse_hex_color(hex_str: str) -> tuple[float, float, float]:
    """Parse hex color like '#RRGGBB' or 'RRGGBB' into (r, g, b) in [0.0, 1.0]."""
    cleaned = hex_str.strip().lstrip("#")
    if len(cleaned) == 6:
        try:
            r = int(cleaned[0:2], 16) / 255.0
            g = int(cleaned[2:4], 16) / 255.0
            b = int(cleaned[4:6], 16) / 255.0
            return (r, g, b)
        except ValueError as exc:
            raise EngineError("error.operation_options") from exc
    raise EngineError("error.operation_options")


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """Calculate WCAG 2.1 relative luminance for linear sRGB channels."""
    def channel_linear(c: float) -> float:
        if c <= 0.04045:
            return c / 12.92
        return math.pow((c + 0.055) / 1.055, 2.4)

    r_lin = channel_linear(rgb[0])
    g_lin = channel_linear(rgb[1])
    b_lin = channel_linear(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate the WCAG contrast ratio between two hex colors, in range [1.0, 21.0]."""
    rgb1 = parse_hex_color(color1)
    rgb2 = parse_hex_color(color2)
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    ratio = (lighter + 0.05) / (darker + 0.05)
    return round(ratio, 2)


@dataclass(frozen=True)
class AccessibilityElement:
    identifier: str
    role: str
    label_key: str
    help_key: str | None = None
    keyboard_shortcut: str | None = None
    traits: tuple[str, ...] = ("focusable",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "role": self.role,
            "label_key": self.label_key,
            "help_key": self.help_key,
            "keyboard_shortcut": self.keyboard_shortcut,
            "traits": list(self.traits),
        }


CORE_ACCESSIBILITY_ELEMENTS = [
    AccessibilityElement(
        identifier="data_grid",
        role="table",
        label_key="grid.label",
        help_key="grid.help",
        keyboard_shortcut="Tab",
        traits=("focusable", "navigable"),
    ),
    AccessibilityElement(
        identifier="import_button",
        role="button",
        label_key="toolbar.import",
        help_key="toolbar.import_help",
        keyboard_shortcut="Cmd+O",
        traits=("focusable", "actionable"),
    ),
    AccessibilityElement(
        identifier="export_button",
        role="button",
        label_key="toolbar.export",
        help_key="toolbar.export_help",
        keyboard_shortcut="Cmd+Shift+E",
        traits=("focusable", "actionable"),
    ),
    AccessibilityElement(
        identifier="analysis_launcher",
        role="search_field",
        label_key="launcher.search",
        help_key="launcher.help",
        keyboard_shortcut="Cmd+K",
        traits=("focusable", "searchable"),
    ),
    AccessibilityElement(
        identifier="variable_sidebar",
        role="list",
        label_key="sidebar.variables",
        help_key="sidebar.help",
        keyboard_shortcut="Cmd+1",
        traits=("focusable", "selectable"),
    ),
]


class FocusCycle:
    """Manages predictable keyboard focus cycling across accessible panels."""

    def __init__(self, elements: list[str] | None = None) -> None:
        self.elements = elements or [
            "analysis_launcher",
            "data_grid",
            "variable_sidebar",
            "import_button",
            "export_button",
        ]
        self._current_index = 0

    @property
    def current(self) -> str:
        return self.elements[self._current_index]

    def next(self) -> str:
        self._current_index = (self._current_index + 1) % len(self.elements)
        return self.current

    def prev(self) -> str:
        self._current_index = (self._current_index - 1) % len(self.elements)
        return self.current

    def set_focus(self, identifier: str) -> None:
        if identifier not in self.elements:
            raise EngineError("error.unknown_field")
        self._current_index = self.elements.index(identifier)


@dataclass
class ThemePalette:
    name: str
    background: str
    surface: str
    text_primary: str
    text_secondary: str
    accent: str
    border: str

    def validate_wcag(self) -> dict[str, bool]:
        """Validate WCAG 2.1 AA contrast requirements."""
        text_bg_ratio = calculate_contrast_ratio(self.text_primary, self.background)
        sec_bg_ratio = calculate_contrast_ratio(self.text_secondary, self.background)
        text_surf_ratio = calculate_contrast_ratio(self.text_primary, self.surface)
        accent_bg_ratio = calculate_contrast_ratio(self.accent, self.background)

        return {
            "text_primary_aa": text_bg_ratio >= 4.5,
            "text_secondary_aa": sec_bg_ratio >= 4.5 or sec_bg_ratio >= 3.0,
            "surface_text_aa": text_surf_ratio >= 4.5,
            "accent_ui_aa": accent_bg_ratio >= 3.0,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "background": self.background,
            "surface": self.surface,
            "text_primary": self.text_primary,
            "text_secondary": self.text_secondary,
            "accent": self.accent,
            "border": self.border,
            "wcag_validation": self.validate_wcag(),
        }


THEMES: dict[str, ThemePalette] = {
    "light": ThemePalette(
        name="light",
        background="#FFFFFF",
        surface="#F5F5F7",
        text_primary="#1D1D1F",
        text_secondary="#6E6E73",
        accent="#0071E3",
        border="#D2D2D7",
    ),
    "dark": ThemePalette(
        name="dark",
        background="#1E1E1E",
        surface="#2D2D2D",
        text_primary="#F5F5F7",
        text_secondary="#A1A1A6",
        accent="#2997FF",
        border="#424245",
    ),
    "high_contrast_light": ThemePalette(
        name="high_contrast_light",
        background="#FFFFFF",
        surface="#E5E5E5",
        text_primary="#000000",
        text_secondary="#333333",
        accent="#0050A0",
        border="#000000",
    ),
    "high_contrast_dark": ThemePalette(
        name="high_contrast_dark",
        background="#000000",
        surface="#121212",
        text_primary="#FFFFFF",
        text_secondary="#CCCCCC",
        accent="#66B2FF",
        border="#FFFFFF",
    ),
}


class AccessibilityManager:
    """Manages accessible elements, focus cycles and themes."""

    DEFAULT_FOCUS_ORDER = [
        "analysis_launcher",
        "data_grid",
        "variable_sidebar",
        "import_button",
        "export_button",
    ]

    def __init__(self) -> None:
        self._elements = list(CORE_ACCESSIBILITY_ELEMENTS)
        self._focus_cycle = FocusCycle(list(self.DEFAULT_FOCUS_ORDER))

    def list_elements(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._elements]

    def focus_cycle_state(self) -> dict[str, Any]:
        return {
            "current": self._focus_cycle.current,
            "elements": self._focus_cycle.elements,
        }

    def focus_next(self) -> str:
        return self._focus_cycle.next()

    def focus_prev(self) -> str:
        return self._focus_cycle.prev()

    def contrast_ratio(self, color1: str, color2: str) -> float:
        return calculate_contrast_ratio(color1, color2)

    def get_theme(self, theme_name: str) -> dict[str, Any]:
        if theme_name not in THEMES:
            raise EngineError("error.operation_options")
        return THEMES[theme_name].to_dict()
