from __future__ import annotations

import re


ALLOWED_HEAD_KEYS = {"atlas", "operations", "risk", "finance", "learning"}


def safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "section"


def normalize_head_key(name: str) -> str:
    key = name.strip().lower()
    if key in ALLOWED_HEAD_KEYS:
        return key
    if key in {"risk", "risk-&-compliance", "risk-and-compliance", "risk-compliance"}:
        return "risk"
    if key.startswith("risk"):
        return "risk"
    slug = safe_slug(key)
    if slug in ALLOWED_HEAD_KEYS:
        return slug
    return slug


def split_head_sections(markdown: str) -> dict[str, str]:
    lines = markdown.splitlines()
    atlas_section = _extract_section(lines, "## Atlas Synthesis")
    head_section = _extract_section(lines, "## Department Head Drafts (AI)")
    heads = _split_by_headings(head_section)
    result: dict[str, str] = {}
    if atlas_section:
        result["atlas"] = atlas_section.strip()
    for head_name, content in heads.items():
        key = normalize_head_key(head_name)
        result[key] = content.strip()
    return result


def _extract_section(lines: list[str], heading: str) -> str:
    try:
        start = lines.index(heading)
    except ValueError:
        return ""
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## ") and lines[idx] != heading:
            end = idx
            break
    return "\n".join(lines[start + 1 : end]).strip()


def _split_by_headings(section: str) -> dict[str, str]:
    if not section:
        return {}
    lines = section.splitlines()
    current_head = None
    chunks: dict[str, list[str]] = {}
    for line in lines:
        if line.startswith("### "):
            current_head = line.replace("### ", "").strip()
            chunks[current_head] = []
            continue
        if current_head is None:
            continue
        chunks[current_head].append(line)
    return {head: "\n".join(body).strip() for head, body in chunks.items()}
