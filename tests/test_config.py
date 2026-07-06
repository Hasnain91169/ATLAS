from atlas.config import load_config


def test_load_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "timezone: UTC",
                "working_hours:",
                "  start: '09:00'",
                "  end: '17:00'",
                "goals:",
                "  - Build a daily brief",
                "  - Protect deep work",
                "  - Keep operations smooth",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.timezone == "UTC"
    assert config.working_hours.start.hour == 9
    assert len(config.goals) == 3
