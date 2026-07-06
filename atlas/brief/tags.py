def derive_tags(meeting_minutes: int, focus_minutes: int) -> list[str]:
    tags: list[str] = []
    if meeting_minutes >= 180:
        tags.append("meeting-heavy")
    if focus_minutes >= 180:
        tags.append("deep-work")
    if not tags:
        tags.append("balanced")
    return tags
