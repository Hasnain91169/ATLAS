from atlas.agents.context import build_agent_context
from atlas.models.tasks import Task, TaskList
from atlas.risk.alerts import build_alert
from atlas.storage.sqlite import (
    connect,
    init_db,
    insert_alerts,
    insert_daily_brief,
    upsert_task_lists,
    upsert_tasks,
)


def test_build_agent_context(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        brief_id = insert_daily_brief(conn, "2025-01-01", "Daily Brief Body", ["tag"])
        upsert_task_lists(conn, [TaskList(id="list-1", title="Primary")])
        upsert_tasks(
            conn,
            "list-1",
            [
                Task(
                    id="task-1",
                    title="Finish report",
                    status="needsAction",
                    due="2025-01-02T09:00:00Z",
                )
            ],
        )
        alert = build_alert(
            severity="HIGH",
            category="burnout",
            title="Burnout risk",
            triggers=["Meeting-heavy day"],
            threshold="Meeting minutes > 300",
            mitigation="Protect focus blocks",
            payload={"meeting_minutes": 360},
        )
        insert_alerts(conn, "daily_brief", brief_id, [alert])

        context = build_agent_context(conn)
    finally:
        conn.close()

    assert "Daily Brief Body" in context["daily_brief_markdown"]
    assert "Finish report" in context["tasks_summary"]
    assert "Burnout risk" in context["alerts_summary"]
