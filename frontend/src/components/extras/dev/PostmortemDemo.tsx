import React, { useState } from 'react';
import PostmortemView from '../PostmortemView';
import { Incident } from '../../../types';

export const isPostmortemDemoMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(window.location.search);
  return params.get('demo') === 'postmortem';
};

const MOCK_INCIDENT: Incident = {
  id: 'INC-104',
  status: 'resolved',
  scenario: 'db_oom',
  root_service: 'postgres',
  impacted_services: ['auth-service', 'payment-service', 'api-gateway', 'web-ui'],
  raw_alert_count: 56,
  started_at: new Date(Date.now() - 38_000).toISOString(),
  resolved_at: new Date().toISOString(),
  rca: {
    root_cause: 'Container terminated with exit code 137 (OOMKilled) after saturating its 64Mi cgroup memory limit.',
    category: 'OOMKilled',
    confidence: 0.97,
    evidence: [
      { type: 'log', source: 'postgres-0', line: 42, text: 'FATAL: out of memory', verified: true },
      { type: 'k8s_event', source: 'postgres-0', text: 'Reason: OOMKilled, Exit Code: 137', verified: true },
    ],
  },
  playbook: {
    diff: 'resources.limits.memory: 64Mi -> 256Mi',
    steps: [
      { order: 1, service: 'postgres', action: 'patch_memory_limit', params: { from: '64Mi', to: '256Mi' }, risk: 'high', requires_approval: true, verify: 'port 5432 accepting connections' },
    ],
  },
};

export const PostmortemDemo: React.FC = () => {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="min-h-screen bg-[#f7f5f0] flex flex-col items-center justify-center gap-4 p-8 font-mono">
      <p className="text-stone-500 text-xs">
        PostmortemView dev demo (task 3.11) — renders the generated report for a mock resolved
        incident and lets you download it as .md.
      </p>
      <button
        onClick={() => setIsOpen(true)}
        className="px-3 py-1.5 rounded-lg border border-stone-300 hover:bg-stone-100 text-stone-700 text-xs font-bold uppercase"
      >
        Open Postmortem
      </button>
      <PostmortemView isOpen={isOpen} onClose={() => setIsOpen(false)} incident={MOCK_INCIDENT} />
    </div>
  );
};

export default PostmortemDemo;
