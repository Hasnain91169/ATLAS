from atlas.actions.executor import execute_action
from atlas.tasks.stub import StubTasksAdapter


def test_executor_task_complete():
    adapter = StubTasksAdapter()
    execute_action(
        "task_complete",
        {"list_id": "list-1", "task_id": "task-1"},
        adapter,
    )
    assert adapter.completed == [("list-1", "task-1")]
