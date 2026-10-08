"""Pydantic models mirroring CONTRACT.md"""

from typing import Literal, Any, Optional
from pydantic import BaseModel, Field

TierType = Literal["data", "backend", "edge", "frontend"]
ServiceStatus = Literal["healthy", "root_cause", "impacted", "recovering"]
SeverityType = Literal["info", "warning", "error", "critical"]
IncidentStatus = Literal["detected", "analyzing", "awaiting_approval", "healing", "resolved"]
RiskLevel = Literal["low", "medium", "high"]
EvidenceType = Literal["k8s_event", "log", "metric"]


class ServiceMetrics(BaseModel):
    mem_mb: float = 0.0
    mem_limit_mb: float = 64.0
    cpu_pct: float = 0.0
    restarts: int = 0


class ServiceNode(BaseModel):
    id: str
    label: str
    tier: TierType
    depends_on: list[str] = Field(default_factory=list)
    status: ServiceStatus = "healthy"
    metrics: ServiceMetrics = Field(default_factory=ServiceMetrics)


class Alert(BaseModel):
    id: str
    ts: str
    service: str
    severity: SeverityType
    message: str
    incident_id: Optional[str] = None


class EvidenceItem(BaseModel):
    type: EvidenceType
    source: str
    line: Optional[int] = None
    text: str
    verified: bool = True


class SimilarIncident(BaseModel):
    id: str
    similarity: float


class RCA(BaseModel):
    root_cause: str
    category: str
    confidence: float
    evidence: list[EvidenceItem] = Field(default_factory=list)
    similar_incident: Optional[SimilarIncident] = None


class PlaybookStep(BaseModel):
    order: int
    service: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    risk: RiskLevel = "low"
    requires_approval: bool = False
    verify: str


class Playbook(BaseModel):
    diff: Optional[str] = None
    steps: list[PlaybookStep] = Field(default_factory=list)


class TimelineItem(BaseModel):
    t_s: float
    event: str


class Incident(BaseModel):
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
    timeline: list[TimelineItem] = Field(default_factory=list)


class WsEvent(BaseModel):
    type: Literal[
        "alert",
        "service_update",
        "incident_update",
        "agent_step",
        "playbook_step",
        "metric_point",
        "prediction",
        "reset",
    ]
    ts: str
    payload: dict[str, Any]


class LogLine(BaseModel):
    line: int
    t_s: float
    text: str
    service: Optional[str] = None


class MetricPoint(BaseModel):
    t_s: float
    mem_mb: float
    cpu_pct: float
    service: Optional[str] = None


class K8sEvent(BaseModel):
    t_s: float
    service: str
    text: str


class ActionResult(BaseModel):
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

