"""Results workbook blocks: ordered tables, charts, notes, sections with annotations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .errors import EngineError

VALID_BLOCK_TYPES = {"table", "chart", "note", "section"}


@dataclass
class Block:
    id: str
    block_type: str
    title: str
    collapsed: bool = False
    annotation: str | None = None
    source_analysis: str | None = None
    content: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise EngineError("error.field_id")
        if self.block_type not in VALID_BLOCK_TYPES:
            raise EngineError("error.operation_options")
        if not isinstance(self.title, str):
            raise EngineError("error.title")
        if not isinstance(self.content, dict):
            raise EngineError("error.operation_options")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.block_type,
            "title": self.title,
            "collapsed": self.collapsed,
            "annotation": self.annotation,
            "source_analysis": self.source_analysis,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Block:
        if not isinstance(data, dict):
            raise EngineError("error.operation_options")
        block_id = data.get("id")
        block_type = data.get("type") or data.get("block_type")
        title = data.get("title", "")
        if not isinstance(block_id, str) or not block_id:
            raise EngineError("error.field_id")
        if not isinstance(block_type, str) or block_type not in VALID_BLOCK_TYPES:
            raise EngineError("error.operation_options")
        content = data.get("content", {})
        if not isinstance(content, dict):
            raise EngineError("error.operation_options")
        return cls(
            id=block_id,
            block_type=block_type,
            title=str(title),
            collapsed=bool(data.get("collapsed", False)),
            annotation=data.get("annotation"),
            source_analysis=data.get("source_analysis"),
            content=content,
        )


def create_table_block(
    id: str,
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    alignment: list[str] | None = None,
    footnotes: list[str] | None = None,
    collapsed: bool = False,
    annotation: str | None = None,
    source_analysis: str | None = None,
) -> Block:
    content: dict[str, Any] = {
        "headers": headers,
        "rows": rows,
    }
    if alignment is not None:
        content["alignment"] = alignment
    if footnotes is not None:
        content["footnotes"] = footnotes
    return Block(
        id=id,
        block_type="table",
        title=title,
        collapsed=collapsed,
        annotation=annotation,
        source_analysis=source_analysis,
        content=content,
    )


def create_chart_block(
    id: str,
    title: str,
    chart_type: str,
    spec: dict[str, Any],
    collapsed: bool = False,
    annotation: str | None = None,
    source_analysis: str | None = None,
) -> Block:
    content: dict[str, Any] = {
        "chart_type": chart_type,
        "spec": spec,
    }
    return Block(
        id=id,
        block_type="chart",
        title=title,
        collapsed=collapsed,
        annotation=annotation,
        source_analysis=source_analysis,
        content=content,
    )


def create_note_block(
    id: str,
    title: str,
    content: str,
    author: str = "user",
    collapsed: bool = False,
    annotation: str | None = None,
    source_analysis: str | None = None,
) -> Block:
    payload: dict[str, Any] = {
        "content": content,
        "author": author,
    }
    return Block(
        id=id,
        block_type="note",
        title=title,
        collapsed=collapsed,
        annotation=annotation,
        source_analysis=source_analysis,
        content=payload,
    )


def create_section_block(
    id: str,
    title: str,
    child_block_ids: list[str],
    collapsed: bool = False,
    annotation: str | None = None,
    source_analysis: str | None = None,
) -> Block:
    content: dict[str, Any] = {
        "child_block_ids": child_block_ids,
    }
    return Block(
        id=id,
        block_type="section",
        title=title,
        collapsed=collapsed,
        annotation=annotation,
        source_analysis=source_analysis,
        content=content,
    )


@dataclass
class Workbook:
    id: str
    title: str
    revision: int = 1
    blocks: list[Block] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise EngineError("error.field_id")
        if not isinstance(self.title, str):
            raise EngineError("error.title")
        # Ensure block ID uniqueness
        seen: set[str] = set()
        for b in self.blocks:
            if b.id in seen:
                raise EngineError("error.duplicate_fields")
            seen.add(b.id)

    def get_block(self, block_id: str) -> Block:
        for b in self.blocks:
            if b.id == block_id:
                return b
        raise EngineError("error.unknown_field")

    def add_block(self, block: Block, index: int | None = None) -> Block:
        if any(b.id == block.id for b in self.blocks):
            raise EngineError("error.duplicate_fields")
        if index is None:
            self.blocks.append(block)
        else:
            if index < 0 or index > len(self.blocks):
                raise EngineError("error.operation_options")
            self.blocks.insert(index, block)
        return block

    def remove_block(self, block_id: str) -> Block:
        for i, b in enumerate(self.blocks):
            if b.id == block_id:
                return self.blocks.pop(i)
        raise EngineError("error.unknown_field")

    def reorder_blocks(self, order: list[str]) -> None:
        if len(order) != len(self.blocks) or set(order) != {b.id for b in self.blocks}:
            raise EngineError("error.operation_options")
        block_map = {b.id: b for b in self.blocks}
        self.blocks = [block_map[bid] for bid in order]

    def move_block(self, block_id: str, new_index: int) -> None:
        block = self.get_block(block_id)
        if new_index < 0 or new_index >= len(self.blocks):
            raise EngineError("error.operation_options")
        self.blocks.remove(block)
        self.blocks.insert(new_index, block)

    def toggle_collapse(self, block_id: str, collapsed: bool | None = None) -> bool:
        block = self.get_block(block_id)
        if collapsed is None:
            block.collapsed = not block.collapsed
        else:
            block.collapsed = bool(collapsed)
        return block.collapsed

    def set_annotation(self, block_id: str, annotation: str | None) -> str | None:
        block = self.get_block(block_id)
        block.annotation = annotation
        return block.annotation

    def rerun_update(
        self,
        new_blocks: list[Block],
        preserve_annotations: bool = True,
        preserve_collapse: bool = True,
    ) -> int:
        """Update computed results while preserving user annotations and collapse states."""
        saved_annotations: dict[str, str | None] = {
            b.id: b.annotation for b in self.blocks if b.annotation is not None
        }
        saved_collapse: dict[str, bool] = {b.id: b.collapsed for b in self.blocks}

        seen: set[str] = set()
        for nb in new_blocks:
            if nb.id in seen:
                raise EngineError("error.duplicate_fields")
            seen.add(nb.id)
            if preserve_annotations and nb.id in saved_annotations and nb.annotation is None:
                nb.annotation = saved_annotations[nb.id]
            if preserve_collapse and nb.id in saved_collapse:
                nb.collapsed = saved_collapse[nb.id]

        self.blocks = list(new_blocks)
        self.revision += 1
        return self.revision

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "revision": self.revision,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workbook:
        if not isinstance(data, dict):
            raise EngineError("error.operation_options")
        wb_id = data.get("id")
        if not isinstance(wb_id, str) or not wb_id:
            raise EngineError("error.field_id")
        title = data.get("title", "")
        revision = int(data.get("revision", 1))
        blocks = [Block.from_dict(b) for b in data.get("blocks", [])]
        return cls(id=wb_id, title=str(title), revision=revision, blocks=blocks)


class WorkbookStore:
    """In-memory session registry of active results workbooks."""

    def __init__(self) -> None:
        self._workbooks: dict[str, Workbook] = {}

    def create(
        self,
        title: str,
        blocks: list[dict[str, Any]] | None = None,
        id: str | None = None,
    ) -> dict[str, Any]:
        wb_id = id or f"wb-{uuid.uuid4().hex[:8]}"
        parsed_blocks = [Block.from_dict(b) for b in (blocks or [])]
        wb = Workbook(id=wb_id, title=title, blocks=parsed_blocks)
        self._workbooks[wb.id] = wb
        return wb.to_dict()

    def get(self, workbook_id: str) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        return self._workbooks[workbook_id].to_dict()

    def add_block(
        self,
        workbook_id: str,
        block: dict[str, Any],
        index: int | None = None,
    ) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        wb = self._workbooks[workbook_id]
        new_block = Block.from_dict(block)
        wb.add_block(new_block, index=index)
        return wb.to_dict()

    def remove_block(self, workbook_id: str, block_id: str) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        wb = self._workbooks[workbook_id]
        wb.remove_block(block_id)
        return wb.to_dict()

    def reorder_blocks(self, workbook_id: str, order: list[str]) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        wb = self._workbooks[workbook_id]
        wb.reorder_blocks(order)
        return wb.to_dict()

    def toggle_collapse(
        self,
        workbook_id: str,
        block_id: str,
        collapsed: bool | None = None,
    ) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        wb = self._workbooks[workbook_id]
        wb.toggle_collapse(block_id, collapsed=collapsed)
        return wb.to_dict()

    def set_annotation(
        self,
        workbook_id: str,
        block_id: str,
        annotation: str | None = None,
    ) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        wb = self._workbooks[workbook_id]
        wb.set_annotation(block_id, annotation)
        return wb.to_dict()

    def rerun_update(
        self,
        workbook_id: str,
        new_blocks: list[dict[str, Any]],
        preserve_annotations: bool = True,
        preserve_collapse: bool = True,
    ) -> dict[str, Any]:
        if workbook_id not in self._workbooks:
            raise EngineError("error.unknown_field")
        wb = self._workbooks[workbook_id]
        parsed_blocks = [Block.from_dict(b) for b in new_blocks]
        wb.rerun_update(
            parsed_blocks,
            preserve_annotations=preserve_annotations,
            preserve_collapse=preserve_collapse,
        )
        return wb.to_dict()
