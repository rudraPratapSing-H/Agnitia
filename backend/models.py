"""Pydantic v2 models mirroring CONTRACT.md exactly"""

from typing import Literal, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

# Literal enum types
NodeStatus = Literal["healthy", "root_cause", "impacted", "recovering"]
Tier = Literal["data", "backend", "edge", "frontend"]
Severity = Literal["info", "warning", "error", "critical"]
Risk = Literal["low", "high"]
EvidenceType = Literal["log", "k8s_event", "metric"]
IncidentStatus = Literal["detected", "analyzing", "awaiting_approval", "healing", "resolved"]
WsEventType = Literal[
    "alert",
    "service_update",
    "incident_update",
    "agent_step",
    "playbook_step",
    "metric_point",
    "prediction",
    "reset",
]


class ServiceMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mem_mb: float = 0.0
    mem_limit_mb: float = 64.0
    cpu_pct: float = 0.0
    restarts: int = 0


Metrics = ServiceMetrics


class ServiceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    tier: Tier
    depends_on: list[str] = Field(default_factory=list)
    status: NodeStatus = "healthy"
    metrics: ServiceMetrics


class Alert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    ts: str
    service: str
    severity: Severity
    message: str
    incident_id: Optional[str] = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: EvidenceType
    source: str
    text: str
    line: Optional[int] = None
    verified: bool = False


EvidenceItem = Evidence


class SimilarIncident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    similarity: float


class RCA(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root_cause: str
    category: str
    confidence: float
    evidence: list[Evidence] = Field(default_factory=list)
    similar_incident: Optional[SimilarIncident] = None
    warning: Optional[str] = None


class PlaybookStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: int
    service: str
    action: str
    params: Optional[dict[str, Any]] = None
    risk: Risk = "low"
    requires_approval: bool = False
    verify: Optional[str] = None


class Playbook(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diff: Optional[str] = None
    steps: list[PlaybookStep] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t_s: float
    event: str


TimelineItem = TimelineEntry


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    status: IncidentStatus = "detected"
    scenario: str
    root_service: str
    impacted_services: list[str] = Field(default_factory=list)
    raw_alert_count: int = 0
    started_at: str
    resolved_at: Optional[str] = None
    rca: Optional[RCA] = None
    playbook: Optional[Playbook] = None
    timeline: list[TimelineEntry] = Field(default_factory=list)


class WsEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: WsEventType
    ts: str
    payload: dict[str, Any]


# Supporting types for ClusterAdapter interfaces
class LogLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line: int
    t_s: float
    text: str
    service: Optional[str] = None


class MetricPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t_s: float
    mem_mb: float
    cpu_pct: float
    service: Optional[str] = None


class K8sEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t_s: float
    service: str
    text: str


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    message: str = ""
    step_order: Optional[int] = None
    service: Optional[str] = None
    action: Optional[str] = None
    success: Optional[bool] = None

    def model_post_init(self, __context: Any) -> None:
        if self.success is None:
            self.success = self.ok
        elif self.ok and not self.success:
            self.ok = self.success


# Scenario file format models
class ScenarioAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[str] = None
    t_s: float
    service: str
    severity: Severity
    message: str


class ScenarioFix(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    action: str
    from_val: Optional[str] = Field(default=None, alias="from")
    to_val: Optional[str] = Field(default=None, alias="to")


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    root_service: str
    duration_s: float
    metrics: dict[str, list[MetricPoint]]
    events: list[K8sEvent]
    logs: dict[str, list[LogLine]]
    alerts: list[ScenarioAlert]
    fix: ScenarioFix

