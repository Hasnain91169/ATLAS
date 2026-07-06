from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from atlas.llm.base import LLMClient
from atlas.org.protocol import HeadReport, HeadSynthesis, WorkerLLMOutput, WorkerResult, WorkerTask


@dataclass(frozen=True)
class Worker:
    name: str
    title: str
    instructions: str
    expected_output: str
    role_identity: str

    def build_task(self, context: dict[str, Any]) -> WorkerTask:
        return WorkerTask(
            id=f"{self.name.lower()}-task",
            title=self.title,
            instructions=self.instructions,
            inputs=self._inputs(context),
            expected_output=self.expected_output,
        )

    def _inputs(self, context: dict[str, Any]) -> dict[str, Any]:
        return context

    def run(
        self,
        context: dict[str, Any],
        enable_llm: bool,
        llm: LLMClient | None,
        head_name: str,
    ) -> WorkerResult:
        task = self.build_task(context)
        assumptions, missing_inputs = self._assumptions(context)

        if enable_llm:
            if llm is None:
                return WorkerResult(
                    task_id=task.id,
                    output="LLM output invalid JSON",
                    llm_output=None,
                    confidence=0.2,
                    assumptions=assumptions,
                    uncertainties=["LLM client unavailable."],
                    missing_inputs=missing_inputs,
                )
            prompt = self._build_prompt(task, head_name)
            try:
                raw = llm.complete(prompt)
                parsed = json.loads(raw)
                llm_output = WorkerLLMOutput.model_validate(parsed)
                llm_output, uncertainties = self._post_validate_actions(
                    llm_output, task
                )
                return WorkerResult(
                    task_id=task.id,
                    output=llm_output.summary,
                    llm_output=llm_output,
                    confidence=llm_output.confidence,
                    assumptions=assumptions,
                    uncertainties=llm_output.uncertainties + uncertainties,
                    missing_inputs=llm_output.missing_inputs,
                )
            except Exception as exc:
                return WorkerResult(
                    task_id=task.id,
                    output="LLM output invalid JSON",
                    llm_output=None,
                    confidence=0.2,
                    assumptions=assumptions,
                    uncertainties=[str(exc)[:200]],
                    missing_inputs=missing_inputs,
                )

        output = self._deterministic_output(task, context)
        confidence = 0.7 if not missing_inputs else 0.4
        uncertainties = []
        if missing_inputs:
            uncertainties.append(f"Missing inputs: {', '.join(missing_inputs)}")
        return WorkerResult(
            task_id=task.id,
            output=output,
            confidence=confidence,
            assumptions=assumptions,
            uncertainties=uncertainties,
            missing_inputs=missing_inputs,
        )

    def _deterministic_output(self, task: WorkerTask, context: dict[str, Any]) -> str:
        return "No findings."

    def _assumptions(self, context: dict[str, Any]) -> tuple[list[str], list[str]]:
        missing = []
        if not context.get("daily_brief_markdown"):
            missing.append("daily_brief_markdown")
        return ["Inputs are current for this week."], missing

    def _build_prompt(self, task: WorkerTask, head_name: str) -> str:
        schema = (
            "{"
            '"summary":"string",'
            '"findings":["string"],'
            '"risks":["string"],'
            '"recommendations":["string"],'
            '"proposed_actions":[{"action_type":"task_complete","payload":{"list_id":"...","task_id":"...","note":"..."},"reason":"..."}],'
            '"confidence":0.0,'
            '"uncertainties":["string"],'
            '"missing_inputs":["string"]'
            "}"
        )
        system = (
            f"You are {self.role_identity}, an independent specialist reporting to {head_name}.\n"
            "You do not execute actions and you do not send messages. You only analyze and propose.\n"
            "You may only propose task_complete actions using task_id and list_id that appear in the provided context JSON.\n"
            "Output JSON only matching the schema. No markdown."
        )
        user = (
            f"Task: {task.title}\n"
            f"Instructions: {task.instructions}\n"
            f"Expected output: {task.expected_output}\n"
            f"Context:\n{json.dumps(task.inputs, ensure_ascii=True, indent=2)}\n\n"
            f"Return JSON only in this schema:\n{schema}"
        )
        return f"SYSTEM:\n{system}\n\nUSER:\n{user}"

    def _post_validate_actions(
        self, llm_output: WorkerLLMOutput, task: WorkerTask
    ) -> tuple[WorkerLLMOutput, list[str]]:
        uncertainties: list[str] = []
        tasks = task.inputs.get("tasks") if isinstance(task.inputs, dict) else None
        tasks = tasks if isinstance(tasks, list) else []
        allowed_pairs: set[tuple[str, str]] = set()
        missing_task_ids = not tasks
        missing_list_ids = not tasks
        for item in tasks:
            task_id = item.get("id")
            list_id = item.get("list_id")
            if not task_id:
                missing_task_ids = True
                continue
            if not list_id:
                missing_list_ids = True
                continue
            allowed_pairs.add((list_id, task_id))

        filtered_actions: list[dict] = []
        dropped_due_to_ids = False
        for action in llm_output.proposed_actions:
            action_type = action.get("action_type")
            payload = action.get("payload")
            if action_type != "task_complete":
                filtered_actions.append(action)
                continue
            if not isinstance(payload, dict):
                uncertainties.append("Dropped task_complete: missing payload.")
                dropped_due_to_ids = True
                continue
            task_id = payload.get("task_id")
            list_id = payload.get("list_id")
            if not task_id or not list_id:
                uncertainties.append("Dropped task_complete: missing task_id or list_id.")
                dropped_due_to_ids = True
                continue
            if (list_id, task_id) not in allowed_pairs:
                uncertainties.append(
                    f"Dropped task_complete: pair not in context ({list_id}, {task_id})."
                )
                dropped_due_to_ids = True
                continue
            filtered_actions.append(action)

        updated = llm_output.model_copy(update={"proposed_actions": filtered_actions})

        if dropped_due_to_ids and not filtered_actions:
            missing_inputs = list(updated.missing_inputs)
            if missing_task_ids and "tasks[].id" not in missing_inputs:
                missing_inputs.append("tasks[].id")
            if missing_list_ids and "tasks[].list_id" not in missing_inputs:
                missing_inputs.append("tasks[].list_id")
            updated = updated.model_copy(update={"missing_inputs": missing_inputs})
            request_action = {
                "action_type": "request_more_info",
                "payload": {
                    "question": "Which task should I mark complete? Provide task_id and list_id.",
                    "needed_fields": ["list_id", "task_id"],
                    "context_hint": "Run atlas tasks sync or use atlas tasks list to view IDs.",
                },
                "reason": "Missing task identifiers in context.",
            }
            updated = updated.model_copy(
                update={"proposed_actions": [request_action]}
            )

        return updated, uncertainties


class TaskAnalystWorker(Worker):
    def __init__(self) -> None:
        super().__init__(
            name="TaskAnalyst",
            title="Review task list and suggest next actions.",
            instructions="Review tasks and suggest which to complete or defer.",
            expected_output="Short list of task recommendations.",
            role_identity="TaskAnalystWorker",
        )

    def _inputs(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"tasks": context.get("tasks", [])}

    def _deterministic_output(self, task: WorkerTask, context: dict[str, Any]) -> str:
        tasks = context.get("tasks", [])
        if not tasks:
            return "No tasks available to review."
        lines = ["Focus on these tasks:"]
        for item in tasks[:3]:
            due = item.get("due") or "No due date"
            lines.append(f"- {item.get('title')} (due: {due})")
        return "\n".join(lines)

    def _assumptions(self, context: dict[str, Any]) -> tuple[list[str], list[str]]:
        missing = [] if context.get("tasks") else ["tasks"]
        return ["Task list reflects current priorities."], missing


class RiskScannerWorker(Worker):
    def __init__(self) -> None:
        super().__init__(
            name="RiskScanner",
            title="Scan alerts for escalations.",
            instructions="Summarize the most critical alerts and mitigations.",
            expected_output="Alert summary with mitigations.",
            role_identity="RiskScannerWorker",
        )

    def _inputs(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"alerts": context.get("alerts", [])}

    def _deterministic_output(self, task: WorkerTask, context: dict[str, Any]) -> str:
        alerts = context.get("alerts", [])
        if not alerts:
            return "No active alerts detected."
        lines = ["Recent alerts:"]
        for alert in alerts[:3]:
            lines.append(f"- [{alert.get('severity')}] {alert.get('title')}")
        return "\n".join(lines)

    def _assumptions(self, context: dict[str, Any]) -> tuple[list[str], list[str]]:
        missing = [] if context.get("alerts") else ["alerts"]
        return ["Alerts are up to date."], missing


class OpsPlannerWorker(Worker):
    def __init__(self) -> None:
        super().__init__(
            name="OpsPlanner",
            title="Adjust execution plan based on daily brief.",
            instructions="Extract schedule pressure points and propose adjustments.",
            expected_output="Short operations adjustment list.",
            role_identity="OpsPlannerWorker",
        )

    def _inputs(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"daily_brief_markdown": context.get("daily_brief_markdown", "")}

    def _deterministic_output(self, task: WorkerTask, context: dict[str, Any]) -> str:
        brief = context.get("daily_brief_markdown") or ""
        if not brief:
            return "No daily brief available; cannot adjust schedule."
        return "Protect two focus blocks and buffer transitions between meetings."


class FinanceCheckerWorker(Worker):
    def __init__(self) -> None:
        super().__init__(
            name="FinanceChecker",
            title="Flag finance-related tasks.",
            instructions="Scan tasks for finance obligations and checks.",
            expected_output="Finance-related task check list.",
            role_identity="FinanceCheckerWorker",
        )

    def _inputs(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"tasks": context.get("tasks", [])}

    def _deterministic_output(self, task: WorkerTask, context: dict[str, Any]) -> str:
        tasks = context.get("tasks", [])
        keywords = ("budget", "invoice", "tax", "payment")
        matches = [t for t in tasks if any(k in t.get("title", "").lower() for k in keywords)]
        if not matches:
            return "No finance-related tasks found."
        lines = ["Finance check tasks:"]
        for item in matches[:3]:
            lines.append(f"- {item.get('title')}")
        return "\n".join(lines)

    def _assumptions(self, context: dict[str, Any]) -> tuple[list[str], list[str]]:
        missing = [] if context.get("tasks") else ["tasks"]
        return ["Task titles reflect finance obligations."], missing


class LearningSynthWorker(Worker):
    def __init__(self) -> None:
        super().__init__(
            name="LearningSynth",
            title="Extract lessons and system tweaks.",
            instructions="Identify recurring issues and propose fixes.",
            expected_output="Short list of lessons and fixes.",
            role_identity="LearningSynthWorker",
        )

    def _inputs(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"daily_brief_markdown": context.get("daily_brief_markdown", "")}

    def _deterministic_output(self, task: WorkerTask, context: dict[str, Any]) -> str:
        brief = context.get("daily_brief_markdown") or ""
        if not brief:
            return "No brief available to learn from."
        return "Codify a weekly review checklist and reduce meeting load."


@dataclass(frozen=True)
class DepartmentHead:
    name: str
    workers: list[Worker]

    def run(
        self, context: dict[str, Any], enable_llm: bool, llm: LLMClient | None
    ) -> HeadReport:
        results: list[WorkerResult] = []
        worker_trace: list[dict] = []
        for worker in self.workers:
            task = worker.build_task(context)
            result = worker.run(context, enable_llm, llm, self.name)
            results.append(result)
            parsed_output = (
                result.llm_output.model_dump()
                if result.llm_output is not None
                else None
            )
            worker_trace.append(
                {
                    "task": task.model_dump(),
                    "result": result.model_dump(),
                    "parsed_output": parsed_output,
                }
            )

        summary, key_risks, recommendations, proposed_actions, confidence, uncertainties = (
            self._merge_worker_outputs(results)
        )
        if enable_llm and llm:
            synthesis = self._llm_synthesis(results, llm)
            if synthesis:
                summary = synthesis.domain_summary
                key_risks = synthesis.key_risks[:3]
                recommendations = synthesis.recommendations_for_atlas[:5]
                confidence = synthesis.confidence
                uncertainties = synthesis.uncertainties[:5]

        return HeadReport(
            head_name=self.name,
            domain_summary=summary,
            key_risks=key_risks,
            recommendations_for_atlas=recommendations,
            proposed_actions=proposed_actions,
            worker_trace=worker_trace,
            confidence=confidence,
            uncertainties=uncertainties,
        )

    def _merge_worker_outputs(
        self, results: list[WorkerResult]
    ) -> tuple[str, list[str], list[str], list[dict], float, list[str]]:
        summary = f"{self.name} synthesized {len(results)} worker outputs."
        risks: list[str] = []
        recommendations: list[str] = []
        actions: list[dict] = []
        uncertainties: list[str] = []
        for result in results:
            if result.llm_output:
                risks.extend(result.llm_output.risks)
                recommendations.extend(result.llm_output.recommendations)
                actions.extend(result.llm_output.proposed_actions)
                uncertainties.extend(result.llm_output.uncertainties)
            else:
                if result.output:
                    recommendations.append(result.output)
            if result.missing_inputs:
                uncertainties.append(f"Missing inputs: {', '.join(result.missing_inputs)}")
            uncertainties.extend(result.uncertainties)

        key_risks = _limit_unique(risks, 3)
        recommendations = _limit_unique(recommendations, 5)
        proposed_actions = actions[:2]
        confidence = min((result.confidence for result in results), default=0.5)
        uncertainties = _limit_unique(uncertainties, 5)
        return summary, key_risks, recommendations, proposed_actions, confidence, uncertainties

    def _llm_synthesis(
        self, results: list[WorkerResult], llm: LLMClient
    ) -> HeadSynthesis | None:
        worker_payloads = [
            result.llm_output.model_dump()
            for result in results
            if result.llm_output is not None
        ]
        if not worker_payloads:
            return None
        schema = (
            "{"
            '"domain_summary":"string",'
            '"key_risks":["string"],'
            '"recommendations_for_atlas":["string"],'
            '"proposed_actions":[{"action_type":"task_complete","payload":{"list_id":"...","task_id":"...","note":"..."},"reason":"..."}],'
            '"confidence":0.0,'
            '"uncertainties":["string"]'
            "}"
        )
        prompt = (
            f"SYSTEM:\nYou are the {self.name} department head. "
            "Synthesize worker outputs into a concise JSON report. "
            "Output JSON only, no markdown.\n\n"
            f"USER:\nWorker outputs:\n{json.dumps(worker_payloads, ensure_ascii=True, indent=2)}\n\n"
            f"Return JSON only in this schema:\n{schema}"
        )
        try:
            raw = llm.complete(prompt)
            parsed = json.loads(raw)
            return HeadSynthesis.model_validate(parsed)
        except Exception:
            return None


def _limit_unique(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        results.append(item)
        if len(results) >= limit:
            break
    return results


class OperationsHead(DepartmentHead):
    def __init__(self) -> None:
        super().__init__(
            name="Operations",
            workers=[OpsPlannerWorker(), TaskAnalystWorker()],
        )


class RiskComplianceHead(DepartmentHead):
    def __init__(self) -> None:
        super().__init__(
            name="Risk & Compliance",
            workers=[RiskScannerWorker()],
        )


class FinanceHead(DepartmentHead):
    def __init__(self) -> None:
        super().__init__(
            name="Finance",
            workers=[FinanceCheckerWorker()],
        )


class LearningHead(DepartmentHead):
    def __init__(self) -> None:
        super().__init__(
            name="Learning",
            workers=[LearningSynthWorker()],
        )
