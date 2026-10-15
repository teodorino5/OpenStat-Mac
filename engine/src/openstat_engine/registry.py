"""Stable command registry shared between Statistics menu and Searchable Analysis Launcher."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Command:
    id: str
    title: str
    category: str
    phase: int
    keywords: tuple[str, ...]
    method: str | None = None

    def to_dict(self, enabled: bool) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "phase": self.phase,
            "keywords": list(self.keywords),
            "method": self.method,
            "enabled": enabled,
        }


DEFAULT_COMMANDS: tuple[Command, ...] = (
    # Phase 0: Foundations & Data Transformations
    Command(
        id="columns.compute",
        title="Compute Variable",
        category="transform",
        phase=0,
        keywords=("formula", "calculate", "expression", "math", "add"),
        method="columns.compute",
    ),
    Command(
        id="columns.recode",
        title="Recode Values",
        category="transform",
        phase=0,
        keywords=("replace", "map", "categories", "transform"),
        method="columns.recode",
    ),
    Command(
        id="columns.standardize",
        title="Standardize Variable (Z-Score)",
        category="transform",
        phase=0,
        keywords=("zscore", "scale", "normalize", "center"),
        method="columns.standardize",
    ),
    Command(
        id="columns.outliers",
        title="Flag Outliers",
        category="transform",
        phase=0,
        keywords=("tukey", "fence", "iqr", "anomaly", "zscore"),
        method="columns.outliers",
    ),
    Command(
        id="columns.box_cox",
        title="Box-Cox Power Transformation",
        category="transform",
        phase=0,
        keywords=("power", "lambda", "mle", "log", "normal"),
        method="columns.box_cox",
    ),
    Command(
        id="classification.intervals",
        title="Interval Classification",
        category="classification",
        phase=0,
        keywords=("bins", "cut", "group", "brackets", "categorize"),
        method="classification.intervals",
    ),
    Command(
        id="dataset.missing_audit",
        title="Missing Data Pattern Audit",
        category="classification",
        phase=0,
        keywords=("null", "na", "incomplete", "patterns", "valid"),
        method="dataset.missing_audit",
    ),
    Command(
        id="dataset.contingency",
        title="Contingency Table",
        category="classification",
        phase=0,
        keywords=("crosstab", "cross", "two-way", "marginal", "frequency"),
        method="dataset.contingency",
    ),
    Command(
        id="tables.aggregate",
        title="Group Aggregation",
        category="tables",
        phase=0,
        keywords=("summary", "mean", "sum", "split", "combine"),
        method="tables.aggregate",
    ),
    Command(
        id="tables.pivot",
        title="Pivot Table (Wide)",
        category="tables",
        phase=0,
        keywords=("unstack", "reshape", "crosstab", "spread"),
        method="tables.pivot",
    ),
    Command(
        id="tables.melt",
        title="Melt Table (Long)",
        category="tables",
        phase=0,
        keywords=("unpivot", "gather", "long", "reshape"),
        method="tables.melt",
    ),
    Command(
        id="tables.transpose",
        title="Transpose Table",
        category="tables",
        phase=0,
        keywords=("swap", "flip", "matrix", "rows", "columns"),
        method="tables.transpose",
    ),
    Command(
        id="tables.join",
        title="Join Tables",
        category="tables",
        phase=0,
        keywords=("merge", "lookup", "combine", "relational"),
        method="tables.join",
    ),
    Command(
        id="tables.stack",
        title="Stack Tables (Union)",
        category="tables",
        phase=0,
        keywords=("append", "union", "concatenate", "rows"),
        method="tables.stack",
    ),
    Command(
        id="dataset.sort",
        title="Sort Cases",
        category="cases",
        phase=0,
        keywords=("order", "rank", "ascending", "descending"),
        method="dataset.sort",
    ),
    Command(
        id="dataset.filter",
        title="Filter Cases",
        category="cases",
        phase=0,
        keywords=("subset", "query", "condition", "where"),
        method="dataset.filter",
    ),
    # Phase 1: Descriptive Statistics & Basic Tests (Gated until Phase 0 complete)
    Command(
        id="stats.descriptives",
        title="Descriptive Statistics",
        category="descriptive",
        phase=1,
        keywords=("mean", "median", "variance", "sd", "skewness", "kurtosis"),
        method=None,
    ),
    Command(
        id="stats.frequencies",
        title="Frequency Table & Histogram",
        category="descriptive",
        phase=1,
        keywords=("counts", "distribution", "bar", "histogram"),
        method=None,
    ),
    Command(
        id="stats.ttest_1samp",
        title="One-Sample T-Test",
        category="inference",
        phase=1,
        keywords=("student", "mean", "hypothesis", "p-value"),
        method=None,
    ),
    Command(
        id="stats.ttest_ind",
        title="Independent Two-Sample T-Test",
        category="inference",
        phase=1,
        keywords=("two groups", "difference", "welch", "student"),
        method=None,
    ),
    Command(
        id="stats.ttest_rel",
        title="Paired Samples T-Test",
        category="inference",
        phase=1,
        keywords=("repeated", "matched", "before after", "dependent"),
        method=None,
    ),
)


class CommandRegistry:
    def __init__(
        self,
        commands: tuple[Command, ...] = DEFAULT_COMMANDS,
        available_methods: set[str] | None = None,
    ) -> None:
        self._commands = commands
        self._available_methods = (
            None if available_methods is None else frozenset(available_methods)
        )

    def set_available_methods(self, available_methods: set[str]) -> None:
        self._available_methods = frozenset(available_methods)

    def _is_enabled(self, command: Command) -> bool:
        if command.phase != 0 or command.method is None:
            return False
        return self._available_methods is None or command.method in self._available_methods

    def list_commands(self, phase: int | None = None) -> list[dict[str, Any]]:
        result = [
            c.to_dict(self._is_enabled(c))
            for c in self._commands
            if phase is None or c.phase == phase
        ]
        return result

    def categories(self) -> list[str]:
        seen: list[str] = []
        for c in self._commands:
            if c.category not in seen:
                seen.append(c.category)
        return seen

    def search(
        self,
        query: str = "",
        max_phase: int | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        tokens = [t.lower() for t in query.strip().split() if t]
        matched: list[dict[str, Any]] = []
        for cmd in self._commands:
            if category is not None and cmd.category != category:
                continue
            if max_phase is not None and cmd.phase > max_phase:
                continue
            if not tokens:
                matched.append(cmd.to_dict(self._is_enabled(cmd)))
                continue
            searchable = (
                f"{cmd.id} {cmd.title} {cmd.category} {' '.join(cmd.keywords)}".lower()
            )
            if all(token in searchable for token in tokens):
                matched.append(cmd.to_dict(self._is_enabled(cmd)))
        return matched
