from __future__ import annotations

from typing import Iterable


def chunk_text(text: str, max_chars: int = 2500) -> list[str]:
    """
    Chunk text into segments <= max_chars, preferring paragraph boundaries.
    Falls back to hard-splitting long paragraphs.
    """
    text = (text or "").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current).strip())
        current = []
        current_len = 0

    for p in paragraphs:
        if len(p) > max_chars:
            flush()
            chunks.extend(_hard_split(p, max_chars))
            continue

        add_len = len(p) + (2 if current else 0)
        if current_len + add_len <= max_chars:
            current.append(p)
            current_len += add_len
        else:
            flush()
            current.append(p)
            current_len = len(p)

    flush()
    return [c for c in chunks if c]


def _hard_split(text: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    i = 0
    while i < len(text):
        parts.append(text[i : i + max_chars].strip())
        i += max_chars
    return [p for p in parts if p]
