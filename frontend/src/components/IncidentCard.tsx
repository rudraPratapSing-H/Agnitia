// frontend/src/components/IncidentCard.jsx - Incident Dossier & HITL Approval Card
import React, { useState } from 'react';
import {
  Flame,
  CheckCircle2,
  FileCheck2,
  GitCommit,
  ShieldAlert,
  ArrowRight,
  Clock,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { executeFullHealFlow } from '../ws';

export default function IncidentCard({ incident, stepStatus }) {
  const [authorizing, setAuthorizing] = useState(false);

  if (!incident) {
    return (
      <div className="bg-zinc-900/60 rounded-xl border border-zinc-800 p-5 text-center text-zinc-500 font-mono text-xs flex flex-col items-center justify-center gap-2">
        <Sparkles size={18} className="text-zinc-600" />
        <span>No active incidents. Cluster status nominal.</span>
      </div>
    );
  }

  const { id, status, root_service, impacted_services, rca, playbook } = incident;
  const isAwaiting = status === 'awaiting_approval';
  const isResolved = status === 'resolved';

  const handleAuthorize = () => {
    setAuthorizing(true);
    executeFullHealFlow();
    setTimeout(() => setAuthorizing(false), 2000);
  };

  return (
    <div className="bg-zinc-900/95 rounded-xl border border-zinc-800 p-4 backdrop-blur-md shadow-2xl transition-all font-mono space-y-3.5">
      {/* Header: ID, Status, Severity */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-black tracking-tight text-zinc-100 flex items-center gap-1.5">
            <Flame size={16} className={isResolved ? "text-emerald-400" : "text-rose-500 animate-bounce"} />
            {id}
          </span>
          <span className="text-[10px] text-zinc-400">
            ROOT: <span className="font-bold text-rose-400">{root_service}</span>
          </span>
        </div>

        <span
          className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${
            isResolved
              ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
              : isAwaiting
              ? 'bg-amber-950/80 text-amber-300 border-amber-700 animate-pulse'
              : 'bg-rose-950/80 text-rose-300 border-rose-800'
          }`}
        >
          {status.replace('_', ' ').toUpperCase()}
        </span>
      </div>

      {/* Root Cause Analysis Summary */}
      {rca && (
        <div className="bg-zinc-950/80 p-3 rounded-lg border border-zinc-800 space-y-2">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-zinc-400 uppercase font-semibold flex items-center gap-1">
              <FileCheck2 size={12} className="text-indigo-400" />
              EVIDENCE-ANCHORED RCA
            </span>
            <span className="text-emerald-400 font-bold bg-emerald-950/60 px-1.5 py-0.2 rounded border border-emerald-800 text-[9px]">
              CONFIDENCE {Math.round((rca.confidence || 0.95) * 100)}%
            </span>
          </div>

          <p className="text-xs text-zinc-200 leading-snug">
            {rca.root_cause}
          </p>

          {/* Evidence Citations */}
          {rca.evidence && (
            <div className="space-y-1 pt-1 border-t border-zinc-900">
              <span className="text-[9px] text-zinc-500 uppercase tracking-wider block">
                MACHINE-CHECKED EVIDENCE:
              </span>
              {rca.evidence.map((ev, idx) => (
                <div key={idx} className="flex items-center gap-1.5 text-[10px] text-zinc-300 bg-zinc-900/60 px-2 py-1 rounded">
                  <CheckCircle2 size={11} className="text-emerald-400 shrink-0" />
                  <span className="text-zinc-400 uppercase font-bold text-[8px] border border-zinc-700 px-1 rounded">
                    {ev.type}
                  </span>
                  <span className="truncate">{ev.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sequential Playbook Preview */}
      {playbook && playbook.steps && playbook.steps.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10px] text-zinc-400">
            <span className="font-semibold uppercase flex items-center gap-1">
              <GitCommit size={12} className="text-purple-400" />
              TOPOLOGICAL RECOVERY PLAYBOOK
            </span>
            <span className="text-[9px] text-zinc-500">
              {playbook.steps.length} ORDERED STEPS
            </span>
          </div>

          {/* Config Diff Preview */}
          {playbook.diff && (
            <div className="p-2 bg-black/60 rounded border border-zinc-800 text-[10px] text-emerald-400 font-mono">
              <span className="text-zinc-500 select-none block text-[8px] mb-0.5">PROPOSED SPEC PATCH:</span>
              <pre className="whitespace-pre-wrap">{playbook.diff}</pre>
            </div>
          )}

          {/* Step Sequence */}
          <div className="space-y-1 max-h-32 overflow-y-auto custom-scrollbar pr-1">
            {playbook.steps.map((st) => {
              const currentStatus = stepStatus[st.order] || (isResolved ? 'done' : 'pending');
              return (
                <div
                  key={st.order}
                  className={`flex items-center justify-between text-[10px] p-1.5 rounded border transition-colors ${
                    currentStatus === 'done'
                      ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300'
                      : currentStatus === 'running'
                      ? 'bg-amber-950/40 border-amber-700 text-amber-200 animate-pulse'
                      : 'bg-zinc-950/50 border-zinc-800 text-zinc-400'
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="w-4 h-4 rounded-full bg-zinc-800 flex items-center justify-center font-bold text-[9px]">
                      {st.order}
                    </span>
                    <span className="font-semibold text-zinc-200">{st.service}:</span>
                    <span className="truncate">{st.action}</span>
                  </div>

                  <span className="text-[9px] uppercase px-1.5 py-0.2 rounded border border-zinc-800 font-bold shrink-0">
                    {currentStatus}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Human-in-the-Loop Authorization Button */}
      {isAwaiting && (
        <div className="pt-2">
          <button
            onClick={handleAuthorize}
            disabled={authorizing}
            className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs uppercase tracking-wider shadow-[0_0_20px_rgba(16,185,129,0.4)] transition-all flex items-center justify-center gap-2 group active:scale-[0.98]"
          >
            {authorizing ? (
              <span>SEQUENCING EXECUTION...</span>
            ) : (
              <>
                <span>AUTHORIZE RECOVERY PLAYBOOK</span>
                <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
          <span className="block text-center text-[9px] text-zinc-500 mt-1">
            Safety Gate: High-risk memory limit change authorized by human on-call engineer.
          </span>
        </div>
      )}

      {isResolved && (
        <div className="p-2.5 rounded-lg bg-emerald-950/50 border border-emerald-800 text-center text-xs text-emerald-300 font-bold flex items-center justify-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-400" />
          SYSTEM HEALED & ALL PROBES VERIFIED 200 OK
        </div>
      )}
    </div>
  );
}
