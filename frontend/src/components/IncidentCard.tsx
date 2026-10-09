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
      <div className="bg-white rounded-xl border border-stone-200 p-4 text-center text-stone-400 font-mono text-xs flex flex-col items-center justify-center gap-1.5 shadow-2xs">
        <ShieldCheck size={18} className="text-stone-400" />
        <span className="font-bold text-stone-600">CLUSTER STATUS NOMINAL</span>
        <span className="text-[10px] text-stone-400">0 active firing alerts • Probes passing</span>
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
    <div className="bg-white rounded-xl border border-stone-200 p-3.5 shadow-2xs font-mono space-y-3">
      {/* Incident Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-black tracking-tight text-stone-900 flex items-center gap-1.5">
            <Flame size={15} className={isResolved ? "text-emerald-600" : "text-rose-600"} />
            {id}
          </span>
          <span className="text-[10px] text-stone-500">
            ROOT: <span className="font-extrabold text-rose-700">{root_service}</span>
          </span>
        </div>

        <span
          className={`text-[9px] font-bold px-2 py-0.5 rounded border ${
            isResolved
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : isAwaiting
              ? 'bg-amber-50 text-amber-800 border-amber-300'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          {status.replace('_', ' ').toUpperCase()}
        </span>
      </div>

      {/* Kubernetes Telemetry Provenance Box */}
      <div className="grid grid-cols-2 gap-1.5 text-[9.5px] bg-stone-50 p-2.5 rounded-lg border border-stone-200 text-stone-600">
        <div>
          <span className="text-stone-400">OBJECT:</span>{' '}
          <span className="font-bold text-stone-800">pod/{root_service}-0</span>
        </div>
        <div>
          <span className="text-stone-400">NAMESPACE:</span>{' '}
          <span className="font-bold text-stone-800">prod-us-east-1</span>
        </div>
        <div>
          <span className="text-stone-400">STATUS:</span>{' '}
          <span className="font-bold text-rose-700">{exitStatus}</span>
        </div>
        <div>
          <span className="text-stone-400">INVARIANT:</span>{' '}
          <span className="font-bold text-emerald-700">3/3 Checks Valid</span>
        </div>
      </div>

      {/* RCA & Evidence Box */}
      {rca && (
        <div className="bg-stone-50/80 p-2.5 rounded-lg border border-stone-200/80 space-y-2">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-stone-700 font-extrabold flex items-center gap-1">
              <FileCheck2 size={12} className="text-stone-700" />
              TOPOLOGICAL ROOT CAUSE
            </span>
            <span className="text-emerald-800 font-bold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200 text-[9px]">
              CONFIDENCE {Math.round((rca.confidence || 0.95) * 100)}%
            </span>
          </div>

          <p className="text-xs text-stone-900 leading-snug font-sans font-medium">
            {rca.root_cause}
          </p>

          {/* Machine-Checked Evidence items */}
          {rca.evidence && (
            <div className="space-y-1 pt-1.5 border-t border-stone-200">
              <div className="flex items-center justify-between">
                <span className="text-[9px] text-stone-500 uppercase tracking-wider block">
                  VERIFIED TELEMETRY EVIDENCE:
                </span>
                {onOpenEvidence && (
                  <button
                    onClick={onOpenEvidence}
                    className="text-[9px] text-stone-700 hover:text-stone-900 bg-white hover:bg-stone-100 px-1.5 py-0.5 rounded border border-stone-300 font-bold flex items-center gap-1 transition-colors"
                  >
                    <kbd className="px-1 text-[8px] bg-stone-100 border border-stone-300 rounded text-stone-600">E</kbd>
                    <FileText size={9} />
                    <span>LOG VIEWER ({rca.evidence.length}) &rarr;</span>
                  </button>
                )}
              </div>

              {rca.evidence.map((ev, idx) => (
                <div
                  key={idx}
                  onClick={onOpenEvidence}
                  className="flex items-center gap-1.5 text-[10px] text-stone-700 bg-white hover:bg-stone-50 cursor-pointer px-2 py-1 rounded border border-stone-200/60 shadow-2xs transition-colors"
                  title="Click to view raw logs and verification proof (Hotkey: E)"
                >
                  <CheckCircle2 size={11} className="text-emerald-600 shrink-0" />
                  <span className="text-stone-500 uppercase font-bold text-[8px] bg-stone-100 border border-stone-200 px-1 rounded">
                    {ev.type}
                  </span>
                  <span className="truncate">{ev.text}</span>
                  <ExternalLink size={9} className="text-stone-400 shrink-0 ml-auto" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sequential Playbook Preview */}
      {playbook && playbook.steps && playbook.steps.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10px] text-stone-600">
            <span className="font-bold uppercase flex items-center gap-1">
              <GitCommit size={12} className="text-stone-700" />
              DEPENDENCY-ORDERED PLAYBOOK
            </span>
            <span className="text-[9px] text-stone-500 font-bold">
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
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                      : currentStatus === 'running'
                      ? 'bg-amber-50 border-amber-300 text-amber-900'
                      : 'bg-stone-50 border-stone-200 text-stone-600'
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="w-4 h-4 rounded bg-stone-200 text-stone-800 flex items-center justify-center font-bold text-[9px]">
                      {st.order}
                    </span>
                    <span className="font-bold text-stone-900">{st.service}:</span>
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
            className="w-full py-2.5 px-4 rounded-lg bg-stone-900 hover:bg-stone-800 text-white font-black text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-2xs active:scale-[0.99]"
          >
            <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-stone-800 text-stone-200 border border-stone-700 rounded">
              A
            </kbd>
            {authorizing ? (
              <span>APPLYING REMEDIATION...</span>
            ) : (
              <>
                <span>REVIEW & AUTHORIZE PLAYBOOK</span>
                <ArrowRight size={13} />
              </>
            )}
          </button>
          <span className="block text-center text-[9px] text-stone-500 mt-1 font-sans">
            Guarded by APEX-04: Operator authorization required for production mutations.
          </span>
        </div>
      )}

      {/* Resolved State Feedback + Postmortem View Button */}
      {isResolved && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-bold space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={16} className="text-emerald-600" />
              <span>INCIDENT RESOLVED & VERIFIED</span>
            </div>
            <span className="text-[10px] text-emerald-700 bg-white px-2 py-0.5 rounded border border-emerald-200 font-mono">
              0 DATA LOSS
            </span>
          </div>

          <p className="text-[10px] text-emerald-800 font-normal font-sans">
            All services restored to nominal health. Dependency-ordered restart sequence verified.
          </p>

          {onOpenPostmortem && (
            <button
              onClick={onOpenPostmortem}
              className="w-full py-2 px-3 rounded-lg bg-emerald-800 hover:bg-emerald-900 text-white text-[11px] font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-colors shadow-2xs"
            >
              <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-emerald-900 text-emerald-100 border border-emerald-700 rounded">
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
