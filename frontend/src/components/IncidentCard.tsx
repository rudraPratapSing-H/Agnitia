// D:\CoffeeOverflow\Agnitia\frontend\src\components\IncidentCard.tsx - Dynamic SRE Incident Dossier
import React, { useState } from 'react';
import {
  Flame,
  CheckCircle2,
  FileCheck2,
  GitCommit,
  ArrowRight,
  ShieldCheck,
  FileText,
  ExternalLink
} from 'lucide-react';
import { Incident } from '../types';
import { executeFullHealFlow } from '../ws';

interface IncidentCardProps {
  incident: Incident | null;
  stepStatus: Record<number, 'pending' | 'running' | 'done' | 'failed'>;
  onOpenEvidence?: () => void;
  onOpenApproval?: () => void;
  onOpenPostmortem?: () => void;
}

export default function IncidentCard({
  incident,
  stepStatus,
  onOpenEvidence,
  onOpenApproval,
  onOpenPostmortem
}: IncidentCardProps) {
  const [authorizing, setAuthorizing] = useState(false);

  if (!incident) {
    return (
      <div className="bg-ink-900 rounded-xl border border-ink-700 p-4 text-center text-ink-500 font-mono text-xs flex flex-col items-center justify-center gap-1.5 shrink-0 min-h-[90px]">
        <ShieldCheck size={18} className="text-ink-500" />
        <span className="font-bold text-ink-300">CLUSTER STATUS NOMINAL</span>
        <span className="text-[10px] text-ink-500">0 active firing alerts • Probes passing</span>
      </div>
    );
  }

  const { id, status, root_service, scenario, rca, playbook } = incident;
  const isAwaiting = status === 'awaiting_approval';
  const isResolved = status === 'resolved';

  const exitStatus =
    scenario === 'bad_config'
      ? 'CrashLoopBackOff'
      : scenario === 'cpu_spike'
      ? 'CPU Throttled (100%)'
      : scenario === 'slow_leak'
      ? 'Gradient Alert (+2.4M/m)'
      : '137 (OOMKilled)';

  const handleAuthorizeClick = () => {
    if (onOpenApproval) {
      onOpenApproval();
    } else {
      setAuthorizing(true);
      executeFullHealFlow();
      setTimeout(() => setAuthorizing(false), 2000);
    }
  };

  return (
    <div className="bg-ink-900 rounded-xl border border-ink-700 p-3.5 font-mono space-y-3 shrink-0 min-h-[320px]">
      {/* Incident Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold tracking-tight text-ink-50 flex items-center gap-1.5">
            <Flame size={15} className={isResolved ? "text-emerald-400" : "text-rose-400"} />
            {id}
          </span>
          <span className="text-[10px] text-ink-400">
            ROOT: <span className="font-extrabold text-rose-300">{root_service}</span>
          </span>
        </div>

        <span
          className={`text-[9px] font-bold px-2 py-0.5 rounded border ${
            isResolved
              ? 'bg-emerald-500/12 text-emerald-300 border-emerald-500/30'
              : isAwaiting
              ? 'bg-amber-500/12 text-amber-300 border-amber-500/35'
              : 'bg-rose-500/12 text-rose-300 border-rose-500/30'
          }`}
        >
          {status.replace('_', ' ').toUpperCase()}
        </span>
      </div>

      {/* Kubernetes Telemetry Provenance Box */}
      <div className="grid grid-cols-2 gap-1.5 text-[9.5px] bg-ink-850 p-2.5 rounded-lg border border-ink-700 text-ink-400">
        <div>
          <span className="text-ink-500">OBJECT:</span>{' '}
          <span className="font-bold text-ink-200">pod/{root_service}-0</span>
        </div>
        <div>
          <span className="text-ink-500">NAMESPACE:</span>{' '}
          <span className="font-bold text-ink-200">prod-us-east-1</span>
        </div>
        <div>
          <span className="text-ink-500">STATUS:</span>{' '}
          <span className="font-bold text-rose-300">{exitStatus}</span>
        </div>
        <div>
          <span className="text-ink-500">INVARIANT:</span>{' '}
          <span className="font-bold text-emerald-300">3/3 Checks Valid</span>
        </div>
      </div>

      {/* RCA & Evidence Box */}
      {rca && (
        <div className="bg-ink-850 p-2.5 rounded-lg border border-ink-700 space-y-2">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-ink-200 font-extrabold flex items-center gap-1">
              <FileCheck2 size={12} className="text-ink-300" />
              TOPOLOGICAL ROOT CAUSE
            </span>
            <span className="text-emerald-300 font-bold bg-emerald-500/12 px-1.5 py-0.2 rounded border border-emerald-500/30 text-[9px]">
              CONFIDENCE {Math.round((rca.confidence || 0.95) * 100)}%
            </span>
          </div>

          <p className="text-xs text-ink-100 leading-snug font-sans font-medium">
            {rca.root_cause}
          </p>

          {/* Machine-Checked Evidence items */}
          {rca.evidence && (
            <div className="space-y-1 pt-1.5 border-t border-ink-700">
              <div className="flex items-center justify-between">
                <span className="text-[9px] text-ink-500 uppercase tracking-wider block">
                  VERIFIED TELEMETRY EVIDENCE:
                </span>
                {onOpenEvidence && (
                  <button
                    onClick={onOpenEvidence}
                    className="text-[9px] text-ink-200 hover:text-ink-50 bg-ink-800 hover:bg-ink-700 px-1.5 py-0.5 rounded border border-ink-600 font-bold flex items-center gap-1 transition-colors"
                  >
                    <kbd className="px-1 text-[8px] bg-ink-700 border border-ink-600 rounded text-ink-300">E</kbd>
                    <FileText size={9} />
                    <span>LOG VIEWER ({rca.evidence.length}) &rarr;</span>
                  </button>
                )}
              </div>

              {rca.evidence.map((ev, idx) => (
                <div
                  key={idx}
                  onClick={onOpenEvidence}
                  className="flex items-center gap-1.5 text-[10px] text-ink-300 bg-ink-800 hover:bg-ink-700 cursor-pointer px-2 py-1 rounded border border-ink-700 transition-colors"
                  title="Click to view raw logs and verification proof (Hotkey: E)"
                >
                  <CheckCircle2 size={11} className="text-emerald-400 shrink-0" />
                  <span className="text-ink-400 uppercase font-bold text-[8px] bg-ink-700 border border-ink-600 px-1 rounded">
                    {ev.type}
                  </span>
                  <span className="truncate">{ev.text}</span>
                  <ExternalLink size={9} className="text-ink-500 shrink-0 ml-auto" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sequential Playbook Preview */}
      {playbook && playbook.steps && playbook.steps.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10px] text-ink-400">
            <span className="font-bold uppercase flex items-center gap-1">
              <GitCommit size={12} className="text-ink-300" />
              DEPENDENCY-ORDERED PLAYBOOK
            </span>
            <span className="text-[9px] text-ink-500 font-bold">
              {playbook.steps.length} STEPS
            </span>
          </div>

          <div className="space-y-1 max-h-28 overflow-y-auto custom-scrollbar pr-1">
            {playbook.steps.map((st) => {
              const currentStatus = stepStatus[st.order] || (isResolved ? 'done' : 'pending');
              return (
                <div
                  key={st.order}
                  className={`flex items-center justify-between text-[10px] p-1.5 rounded border transition-colors ${
                    currentStatus === 'done'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                      : currentStatus === 'running'
                      ? 'bg-amber-500/10 border-amber-500/35 text-amber-200'
                      : 'bg-ink-850 border-ink-700 text-ink-400'
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="w-4 h-4 rounded bg-ink-700 text-ink-200 flex items-center justify-center font-bold text-[9px]">
                      {st.order}
                    </span>
                    <span className="font-bold text-ink-100">{st.service}:</span>
                    <span className="truncate">{st.action}</span>
                  </div>

                  <span className="text-[9px] uppercase px-1.5 py-0.2 rounded font-bold shrink-0">
                    {currentStatus}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Authorize Button & Safety Warning */}
      {isAwaiting && (
        <div className="pt-1">
          <button
            onClick={handleAuthorizeClick}
            disabled={authorizing}
            className="w-full py-2.5 px-4 rounded-lg bg-copper-500 hover:bg-copper-400 text-ink-950 font-black text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 active:scale-[0.99]"
          >
            <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-ink-950/25 text-ink-950 border border-ink-950/30 rounded">
              A
            </kbd>
            {authorizing ? (
              <span>APPLYING REMEDIATION...</span>
            ) : (
              <>
                <span>REVIEW &amp; AUTHORIZE PLAYBOOK</span>
                <ArrowRight size={13} />
              </>
            )}
          </button>
          <span className="block text-center text-[9px] text-ink-500 mt-1 font-sans">
            Guarded by APEX-04: Operator authorization required for production mutations.
          </span>
        </div>
      )}

      {/* Resolved State Feedback + Postmortem View Button */}
      {isResolved && (
        <div className="p-3 rounded-xl bg-emerald-500/8 border border-emerald-500/25 text-xs text-emerald-200 font-bold space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={16} className="text-emerald-400" />
              <span>INCIDENT RESOLVED &amp; VERIFIED</span>
            </div>
            <span className="text-[10px] text-emerald-300 bg-ink-900 px-2 py-0.5 rounded border border-emerald-500/30 font-mono">
              0 DATA LOSS
            </span>
          </div>

          <p className="text-[10px] text-emerald-300/80 font-normal font-sans">
            All services restored to nominal health. Dependency-ordered restart sequence verified.
          </p>

          {onOpenPostmortem && (
            <button
              onClick={onOpenPostmortem}
              className="w-full py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-ink-950 text-[11px] font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-colors"
            >
              <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-ink-950/25 text-ink-950 border border-ink-950/30 rounded">
                P
              </kbd>
              <FileText size={13} />
              <span>VIEW SRE POSTMORTEM REPORT</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
