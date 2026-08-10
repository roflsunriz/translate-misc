from __future__ import annotations

import re
from dataclasses import dataclass

from translation_pipeline.errors import PipelineError


@dataclass(frozen=True)
class MarkdownChunk:
    text: str
    translate: bool


_FENCE = re.compile(r"^\s*(```|~~~)")
_NON_TRANSLATABLE = re.compile(r"^\s*(?:---+|\*\*\*+|___+)\s*$")


def chunk_markdown(markdown: str, max_characters: int) -> list[MarkdownChunk]:
    blocks = _blocks(markdown)
    chunks: list[MarkdownChunk] = []
    pending: list[str] = []
    pending_length = 0

    def flush() -> None:
        nonlocal pending, pending_length
        if pending:
            chunks.append(MarkdownChunk("\n\n".join(pending).strip(), True))
            pending = []
            pending_length = 0

    for block, translatable in blocks:
        if not translatable:
            flush()
            chunks.append(MarkdownChunk(block, False))
            continue
        for piece in _split_large_block(block, max_characters):
            added = len(piece) + (2 if pending else 0)
            if pending and pending_length + added > max_characters:
                flush()
            pending.append(piece)
            pending_length += len(piece) + (2 if len(pending) > 1 else 0)
    flush()
    return chunks


def protect_literals(markdown: str) -> tuple[str, dict[str, str]]:
    values: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"[[[LITERAL_{len(values):04d}]]]"
        values[token] = match.group(0)
        return token

    protected = re.sub(r"`[^`\n]+`|https?://[^\s)>\]]+", replace, markdown)
    return protected, values


def restore_literals(markdown: str, values: dict[str, str]) -> str:
    result = markdown
    for token, value in values.items():
        if token not in result:
            raise PipelineError(
                "LLMがURLまたはインラインコードの保護記号を変更したため、"
                "壊れた下書きの保存を中止しました。"
            )
        result = result.replace(token, value)
    return result


def _blocks(markdown: str) -> list[tuple[str, bool]]:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result: list[tuple[str, bool]] = []
    current: list[str] = []
    fence_marker: str | None = None

    def flush(translatable: bool = True) -> None:
        nonlocal current
        text = "\n".join(current).strip()
        if text:
            result.append((text, translatable and not bool(_NON_TRANSLATABLE.match(text))))
        current = []

    for line in lines:
        fence = _FENCE.match(line)
        if fence_marker is not None:
            current.append(line)
            if fence and fence.group(1) == fence_marker:
                flush(False)
                fence_marker = None
            continue
        if fence:
            flush()
            fence_marker = fence.group(1)
            current.append(line)
        elif not line.strip():
            flush()
        else:
            current.append(line)
    flush(fence_marker is None)
    return result


def _split_large_block(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    lines = block.splitlines()
    if len(lines) > 1:
        return _pack_parts(lines, limit, "\n")
    sentences = re.split(r"(?<=[.!?。！？])\s+", block)
    if len(sentences) > 1:
        return _pack_parts(sentences, limit, " ")
    return [block[index : index + limit] for index in range(0, len(block), limit)]


def _pack_parts(parts: list[str], limit: int, separator: str) -> list[str]:
    result: list[str] = []
    current = ""
    for part in parts:
        if len(part) > limit:
            if current:
                result.append(current)
                current = ""
            result.extend(part[index : index + limit] for index in range(0, len(part), limit))
            continue
        candidate = part if not current else current + separator + part
        if current and len(candidate) > limit:
            result.append(current)
            current = part
        else:
            current = candidate
    if current:
        result.append(current)
    return result
