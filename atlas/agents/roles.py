from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    name: str
    purpose: str
    prompt_template: str


AGENT_CONFIGS = [
    AgentConfig(
        name="Operations",
        purpose="Draft operational adjustments for the next week.",
        prompt_template=(
            "You are the Head of Operations.\n"
            "Daily brief:\n{daily_brief}\n\n"
            "Tasks summary:\n{tasks_summary}\n\n"
            "Alerts summary:\n{alerts_summary}\n\n"
            "Draft 3 operational adjustments in bullet form."
        ),
    ),
    AgentConfig(
        name="Risk & Compliance",
        purpose="Draft risk mitigations for the next week.",
        prompt_template=(
            "You are the Risk & Compliance Officer.\n"
            "Daily brief:\n{daily_brief}\n\n"
            "Tasks summary:\n{tasks_summary}\n\n"
            "Alerts summary:\n{alerts_summary}\n\n"
            "Draft 3 risk mitigations in bullet form."
        ),
    ),
    AgentConfig(
        name="Finance",
        purpose="Draft financial discipline reminders and checks.",
        prompt_template=(
            "You are the CFO of Life.\n"
            "Daily brief:\n{daily_brief}\n\n"
            "Tasks summary:\n{tasks_summary}\n\n"
            "Alerts summary:\n{alerts_summary}\n\n"
            "Draft 3 finance checks in bullet form."
        ),
    ),
    AgentConfig(
        name="Learning",
        purpose="Draft post-mortem insights and system fixes.",
        prompt_template=(
            "You are the Director of Learning.\n"
            "Daily brief:\n{daily_brief}\n\n"
            "Tasks summary:\n{tasks_summary}\n\n"
            "Alerts summary:\n{alerts_summary}\n\n"
            "Draft 3 learning insights in bullet form."
        ),
    ),
]
