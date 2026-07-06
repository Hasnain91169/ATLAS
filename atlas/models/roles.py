from pydantic import BaseModel, ConfigDict, Field


class RoleBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    title: str
    domain: str
    responsibilities: list[str] = Field(default_factory=list)


class AtlasRole(RoleBase):
    name: str = "Atlas"
    title: str = "Chief of Staff"
    domain: str = "Central command, prioritization, and escalation control."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Prioritize execution and filter requests.",
            "Run daily planning loops.",
            "Escalate risk and enforce approvals.",
        ]
    )


class StrategyDirector(RoleBase):
    name: str = "Director of Trajectory"
    title: str = "Head of Strategy & Long-Term Planning"
    domain: str = "1–3–5 year strategy and opportunity cost analysis."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Define long-range objectives.",
            "Assess opportunity costs and trade-offs.",
        ]
    )


class OperationsDirector(RoleBase):
    name: str = "COO"
    title: str = "Head of Operations"
    domain: str = "Routines, systems, and daily execution."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Maintain daily routines and systems.",
            "Coordinate execution logistics.",
        ]
    )


class HealthDirector(RoleBase):
    name: str = "Director of Vitality"
    title: str = "Head of Health & Physical Performance"
    domain: str = "Sleep, training, and energy management."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Monitor health metrics and recovery.",
            "Recommend training and nutrition adjustments.",
        ]
    )


class FaithDirector(RoleBase):
    name: str = "Director of Alignment"
    title: str = "Head of Faith & Inner Discipline"
    domain: str = "Prayer windows and moral alignment checks."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Protect prayer windows.",
            "Flag alignment risks.",
        ]
    )


class RelationshipsDirector(RoleBase):
    name: str = "Director of Human Systems"
    title: str = "Head of Relationships & Social Capital"
    domain: str = "Family, boundaries, and network health."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Maintain relationship cadence.",
            "Detect social debt or leakage.",
        ]
    )


class WealthDirector(RoleBase):
    name: str = "CFO of Life"
    title: str = "Head of Wealth & Asset Building"
    domain: str = "Income streams, spending, and risk exposure."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Track financial discipline.",
            "Flag unpriced risk.",
        ]
    )


class RiskComplianceOfficer(RoleBase):
    name: str = "Internal Auditor"
    title: str = "Risk & Compliance Officer"
    domain: str = "Overcommitment, burnout, and compliance risk."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Monitor risk thresholds.",
            "Issue execution pauses when needed.",
        ]
    )


class LearningDirector(RoleBase):
    name: str = "Director of Learning"
    title: str = "Quality Control / Post-Mortem Analyst"
    domain: str = "Weekly review, failure analysis, and system fixes."
    responsibilities: list[str] = Field(
        default_factory=lambda: [
            "Run post-mortems.",
            "Propose systemic improvements.",
        ]
    )


class DepartmentHead(RoleBase):
    pass


class SpecialistRole(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    focus: str
