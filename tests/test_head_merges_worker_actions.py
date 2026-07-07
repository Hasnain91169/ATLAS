from atlas.org.protocol import WorkerLLMOutput, WorkerResult
from atlas.org.roles import OperationsHead


def test_head_merges_worker_actions(monkeypatch):
    head = OperationsHead()

    output = WorkerLLMOutput(
        summary="Worker summary",
        findings=[],
        risks=[],
        recommendations=["Do the next task"],
        proposed_actions=[
            {
                "action_type": "task_complete",
                "payload": {"list_id": "list-1", "task_id": "task-1"},
                "reason": "Quick win",
            },
            {
                "action_type": "task_complete",
                "payload": {"list_id": "list-1", "task_id": "task-2"},
                "reason": "Follow-up",
            },
            {
                "action_type": "task_complete",
                "payload": {"list_id": "list-1", "task_id": "task-3"},
                "reason": "Extra",
            },
        ],
        confidence=0.7,
        uncertainties=[],
        missing_inputs=[],
    )

    def fake_run(self, context, enable_llm, llm, head_name, tracer=None):
        return WorkerResult(
            task_id="task-1",
            output=output.summary,
            llm_output=output,
            confidence=output.confidence,
            assumptions=[],
            uncertainties=[],
            missing_inputs=[],
        )

    for worker in head.workers:
        monkeypatch.setattr(worker, "run", fake_run.__get__(worker, worker.__class__))

    report = head.run({}, enable_llm=True, llm=None)

    assert len(report.proposed_actions) == 2
