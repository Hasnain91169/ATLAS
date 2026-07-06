from atlas.board_meeting.split import split_head_sections


def test_split_head_sections():
    markdown = """
# Board Meeting Report - 2025-01-01

## Atlas Synthesis
### What mattered
- Ops stable

## Department Head Drafts (AI)
### Operations
Summary: Ops summary
Key Risks:
- None

### Risk & Compliance
Summary: Risk summary
Key Risks:
- Alert

### Finance
Summary: Finance summary
Key Risks:
- None

### Learning
Summary: Learning summary
Key Risks:
- None
""".strip()

    sections = split_head_sections(markdown)
    assert "atlas" in sections
    assert "operations" in sections
    assert "risk" in sections
    assert "finance" in sections
    assert "learning" in sections
    assert "Ops stable" in sections["atlas"]
