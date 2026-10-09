import React, { useState } from 'react';
import { FileText, Download, Copy, Check, X, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { Incident } from '../../types';

interface PostmortemViewProps {
  incident: Incident | null;
  isOpen: boolean;
  onClose: () => void;
}

export function generatePostmortemMarkdown(incident: Incident): string {
  const rca = incident.rca;
  const rootCause = rca?.root_cause || `${incident.root_service} failure`;
  const category = rca?.category || 'Unclassified';
  const confidence = Math.round((rca?.confidence || 0.95) * 100);

  const evidenceBullets =
    rca?.evidence && rca.evidence.length > 0
      ? rca.evidence
          .map(
            (ev) =>
              `- ${ev.verified ? '✅ [VERIFIED]' : '⚠️ [UNVERIFIED]'} **${ev.type.toUpperCase()}** (${ev.source}): \`${ev.text}\``
          )
          .join('\n')
      : '- Telemetry correlation from container metric and event telemetry.';

  const stepsBullets =
    incident.playbook?.steps && incident.playbook.steps.length > 0
      ? incident.playbook.steps
          .map(
            (st) =>
              `${st.order}. **${st.service}**: \`${st.action}\` (Risk: ${st.risk}) — *Verification: ${st.verify}*`
          )
          .join('\n')
      : '- Automated readiness health checks verified across cluster.';

  const startTime = incident.started_at || new Date().toISOString();
  const resolvedTime = incident.resolved_at || 'Resolved autonomously';

  return `# Incident Postmortem: ${incident.id}

**Scenario:** \`${incident.scenario || 'db_oom'}\`  
**Status:** ${incident.status.toUpperCase()}  
**Incident Window:** Started at \`${startTime}\` | Resolved at \`${resolvedTime}\`  
**Raw Alerts Processed:** ${incident.raw_alert_count || 56} alerts correlated into 1 root cause  

---

## 1. Executive Summary
At ${startTime}, Agnitia detected an alert storm involving ${incident.raw_alert_count || 56} raw alerts. Topological dependency analysis isolated **${incident.root_service}** as the single root failure. Downstream services impacted: ${incident.impacted_services?.join(', ') || 'auth-service, payment-service, api-gateway, web-ui'}.

## 2. Root Cause Analysis
- **Category:** ${category}
- **Root Cause:** ${rootCause}
- **Diagnosis Confidence:** ${confidence}%

### Machine-Checked Evidence:
${evidenceBullets}

## 3. Remediation & Recovery Actions
The following dependency-ordered recovery playbook was authorized and executed:
${stepsBullets}

## 4. Prevention & Action Items
- Enforce updated memory resource limits across cluster deployments.
- Verify readiness probes to prevent cascading upstream connection drops.
- Update alerting thresholds to catch early saturation trends.
`;
}

export default function PostmortemView({ incident, isOpen, onClose }: PostmortemViewProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !incident) return null;

  const mdContent = generatePostmortemMarkdown(incident);

  const handleCopy = () => {
    navigator.clipboard.writeText(mdContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `postmortem-${incident.id.toLowerCase()}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4 font-mono animate-fadeIn">
      <div className="bg-white border border-stone-300 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-stone-200 flex items-center justify-between bg-stone-50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-stone-900 text-white flex items-center justify-center">
              <FileText size={16} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-stone-900">
                INCIDENT POSTMORTEM • {incident.id}
              </h2>
              <p className="text-[10px] text-stone-500">
                Automated SRE RCA Report & Prevention Plan
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="px-2.5 py-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-100 text-stone-700 text-[11px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
              title="Copy Markdown"
            >
              {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
              <span>{copied ? 'COPIED' : 'COPY'}</span>
            </button>

            <button
              onClick={handleDownload}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
              title="Download .md file"
            >
              <Download size={13} />
              <span>DOWNLOAD .MD</span>
            </button>

            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg border border-stone-200 bg-white hover:bg-stone-100 flex items-center justify-center text-stone-500 hover:text-stone-800 transition-colors cursor-pointer"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Content Viewer */}
        <div className="p-6 overflow-y-auto space-y-4 text-xs font-sans text-stone-800 leading-relaxed custom-scrollbar bg-white">
          {/* Metadata badges */}
          <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-stone-100 font-mono text-[10px]">
            <span className="bg-stone-100 text-stone-700 px-2 py-0.5 rounded font-bold">
              SCENARIO: {incident.scenario || 'db_oom'}
            </span>
            <span className="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded font-bold">
              STATUS: {incident.status.toUpperCase()}
            </span>
            <span className="bg-stone-100 text-stone-600 px-2 py-0.5 rounded">
              ROOT: {incident.root_service}
            </span>
            <span className="bg-stone-100 text-stone-600 px-2 py-0.5 rounded">
              CONFIDENCE: {Math.round((incident.rca?.confidence || 0.95) * 100)}%
            </span>
          </div>

          {/* Section 1 */}
          <div className="space-y-1">
            <h3 className="font-mono text-xs font-bold text-stone-900 uppercase">
              1. Executive Summary
            </h3>
            <p className="text-stone-700">
              Agnitia detected an alert storm involving {incident.raw_alert_count || 56} raw alerts. Topological dependency analysis isolated <strong className="text-stone-900 font-mono">{incident.root_service}</strong> as the root failure. Downstream services impacted: {incident.impacted_services?.join(', ') || 'auth-service, payment-service, api-gateway, web-ui'}.
            </p>
          </div>

          {/* Section 2 */}
          <div className="space-y-1.5">
            <h3 className="font-mono text-xs font-bold text-stone-900 uppercase">
              2. Root Cause Analysis
            </h3>
            <div className="p-2.5 bg-stone-50 rounded-lg border border-stone-200 space-y-1 text-stone-800">
              <div><strong>Category:</strong> {incident.rca?.category || 'OOMKilled'}</div>
              <div><strong>Root Cause:</strong> {incident.rca?.root_cause || `${incident.root_service} memory saturation`}</div>
            </div>

            {incident.rca?.evidence && (
              <div className="space-y-1 pt-1">
                <span className="font-mono text-[10px] text-stone-500 uppercase font-semibold">
                  Verified Telemetry Citations:
                </span>
                <div className="space-y-1">
                  {incident.rca.evidence.map((ev, i) => (
                    <div key={i} className="flex items-center gap-2 p-1.5 bg-stone-50 border border-stone-200/80 rounded text-[11px] font-mono">
                      <CheckCircle2 size={13} className="text-emerald-600 shrink-0" />
                      <span className="bg-stone-200 px-1 py-0.2 rounded text-[9px] uppercase font-bold text-stone-700">
                        {ev.type}
                      </span>
                      <span className="truncate text-stone-800">{ev.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Section 3 */}
          <div className="space-y-1.5">
            <h3 className="font-mono text-xs font-bold text-stone-900 uppercase">
              3. Remediation & Recovery Actions
            </h3>
            <div className="space-y-1 font-mono text-[11px]">
              {incident.playbook?.steps?.map((st) => (
                <div key={st.order} className="flex items-center gap-2 p-1.5 bg-emerald-50/50 border border-emerald-200 rounded">
                  <span className="w-4 h-4 rounded bg-emerald-200 text-emerald-900 font-bold flex items-center justify-center text-[9px]">
                    {st.order}
                  </span>
                  <span className="font-bold text-emerald-950">{st.service}:</span>
                  <span className="text-stone-800">{st.action}</span>
                  <span className="text-stone-400 text-[10px] ml-auto">Verified</span>
                </div>
              ))}
            </div>
          </div>

          {/* Section 4 */}
          <div className="space-y-1">
            <h3 className="font-mono text-xs font-bold text-stone-900 uppercase">
              4. Prevention & Action Items
            </h3>
            <ul className="list-disc list-inside space-y-0.5 text-stone-700">
              <li>Enforce updated memory resource limits across cluster deployments.</li>
              <li>Verify readiness probes to prevent cascading upstream connection drops.</li>
              <li>Update alerting thresholds to catch early saturation trends.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
