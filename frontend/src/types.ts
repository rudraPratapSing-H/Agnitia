// D:\CoffeeOverflow\Agnitia\frontend\src\types.ts - Type Definitions mirroring CONTRACT.md

export type ServiceTier = 'data' | 'backend' | 'edge' | 'frontend';
export type ServiceStatus = 'healthy' | 'root_cause' | 'impacted' | 'recovering';
export type AlertSeverity = 'info' | 'warning' | 'error' | 'critical';
export type IncidentStatus = 'detected' | 'analyzing' | 'awaiting_approval' | 'healing' | 'resolved';
export type ActionRisk = 'low' | 'medium' | 'high';
export type AgentStage = 'triage' | 'diagnose' | 'plan' | 'execute' | 'verify';

export interface ServiceMetrics {
  mem_mb: number;
  mem_limit_mb: number;
  cpu_pct: number;
  restarts: number;
}

export interface ServiceNode {
  id: string;
  label: string;
  tier: ServiceTier;
  depends_on: string[];
  status: ServiceStatus;
  metrics: ServiceMetrics;
}

export interface Alert {
  id: string;
  ts: string;
  service: string;
  severity: AlertSeverity;
  message: string;
  incident_id?: string;
}

export interface EvidenceItem {
  type: 'k8s_event' | 'log' | 'metric';
  source: string;
  line?: number | null;
  text: string;
  verified: boolean;
}

export interface RCA {
  root_cause: string;
  category: string;
  confidence: number;
  evidence: EvidenceItem[];
  similar_incident?: {
    id: string;
    similarity: number;
  };
}

export interface PlaybookStep {
  order: number;
  service: string;
  action: string;
  params: Record<string, any>;
  risk: ActionRisk;
  requires_approval: boolean;
  verify: string;
}

export interface Playbook {
  diff: string;
  steps: PlaybookStep[];
}

export interface TimelineItem {
  t_s: number;
  event: string;
}

export interface Incident {
  id: string;
  status: IncidentStatus;
  scenario: string;
  root_service: string;
  impacted_services: string[];
  raw_alert_count: number;
  started_at: string;
  resolved_at: string | null;
  rca?: RCA;
  playbook?: Playbook;
  timeline?: TimelineItem[];
}

export interface AgentStep {
  id?: string | number;
  agent: AgentStage | string;
  text: string;
  status?: 'pending' | 'running' | 'done' | 'failed';
  ts?: string;
}

export interface MetricPoint {
  service: string;
  t_s?: number;
  mem_mb: number;
  mem_limit_mb?: number;
  cpu_pct: number;
}

export interface Prediction {
  service: string;
  seconds: number;
  message?: string;
  trend?: string;
}

export interface WsEvent {
  type: 'alert' | 'service_update' | 'incident_update' | 'agent_step' | 'playbook_step' | 'metric_point' | 'prediction' | 'reset';
  ts?: string;
  payload: any;
}
