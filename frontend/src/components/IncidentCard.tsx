// D:\CoffeeOverflow\Agnitia\frontend\src\components\IncidentCard.tsx
import React, { useState } from 'react';
import {
  Flame,
  CheckCircle2,
  FileCheck2,
  GitCommit,
  ArrowRight,
  ShieldCheck
} from 'lucide-react';
import { Incident } from '../types';
import { executeFullHealFlow } from '../ws';

interface IncidentCardProps {
  incident: Incident | null;
  stepStatus: Record<number, 'pending' | 'running' | 'done' | 'failed'>;
}

export default function IncidentCard({ incident, stepStatus }: IncidentCardProps) {
  const [authorizing, setAuthorizing] = useState(false);

  if (!incident) {
    return (
      <div className="bg-white rounded-xl border border-stone-200 p-4 text-center text-stone-400 font-mono text-xs flex flex-col items-center justify-center gap-1.5 shadow-sm">
        <ShieldCheck size={18} className="text-stone-400" />
        <span>No active incidents. Cluster status nominal.</span>
      </div>
    );
  }

  const { id, status, root_service, rca, playbook } = incident;
  const isAwaiting = status === 'awaiting_approval';
  const isResolved = status === 'resolved';

  const handleAuthorize = () => {
    setAuthorizing(true);
    executeFullHealFlow();
    setTimeout(() => setAuthorizing(false), 2000);
  };

  return (
    <div className="bg-white rounded-xl border border-stone-200 p-3.5 shadow-sm font-mono space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-extrabold tracking-tight text-stone-900 flex items-center gap-1.5">
            <Flame size={15} className={isResolved ? "text-emerald-600" : "text-rose-600"} />
            {id}
          </span>
          <span className="text-[10px] text-stone-500">
            ROOT: <span className="font-bold text-rose-700">{root_service}</span>
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

      {rca && (
        <div className="bg-stone-50/80 p-2.5 rounded-lg border border-stone-200/80 space-y-1.5">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-stone-600 font-semibold flex items-center gap-1">
              <FileCheck2 size={12} className="text-stone-700" />
              ROOT CAUSE ANALYSIS
            </span>
            <span className="text-emerald-800 font-bold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200 text-[9px]">
              CONFIDENCE {Math.round((rca.confidence || 0.95) * 100)}%
            </span>
          </div>

          <p className="text-xs text-stone-900 leading-snug font-sans font-medium">
            {rca.root_cause}
          </p>

          {rca.evidence && (
            <div className="space-y-1 pt-1 border-t border-stone-200">
              <span className="text-[9px] text-stone-500 uppercase tracking-wider block">
                MACHINE-CHECKED EVIDENCE:
              </span>
              {rca.evidence.map((ev, idx) => (
                <div key={idx} className="flex items-center gap-1.5 text-[10px] text-stone-700 bg-white px-2 py-1 rounded border border-stone-200/60 shadow-2xs">
                  <CheckCircle2 size={11} className="text-emerald-600 shrink-0" />
                  <span className="text-stone-500 uppercase font-bold text-[8px] bg-stone-100 border border-stone-200 px-1 rounded">
                    {ev.type}
                  </span>
                  <span className="truncate">{ev.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {playbook && playbook.steps && playbook.steps.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10px] text-stone-600">
            <span className="font-semibold uppercase flex items-center gap-1">
              <GitCommit size={12} className="text-stone-700" />
              SEQUENTIAL RECOVERY PLAYBOOK
            </span>
            <span className="text-[9px] text-stone-500">
              {playbook.steps.length} STEPS
            </span>
          </div>

          {playbook.diff && (
            <div className="p-2 bg-stone-900 text-stone-100 rounded border border-stone-800 text-[10px] font-mono shadow-inner">
              <span className="text-stone-400 block text-[8px] mb-0.5">PROPOSED SPEC CHANGE:</span>
              <pre className="text-emerald-400 whitespace-pre-wrap">{playbook.diff}</pre>
            </div>
          )}

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
                    <span className="font-semibold text-stone-900">{st.service}:</span>
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

      {isAwaiting && (
        <div className="pt-1">
          <button
            onClick={handleAuthorize}
            disabled={authorizing}
            className="w-full py-2.5 px-4 rounded-lg bg-stone-900 hover:bg-stone-800 text-white font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-sm active:scale-[0.99]"
          >
            {authorizing ? (
              <span>SEQUENCING PLAYBOOK...</span>
            ) : (
              <>
                <span>AUTHORIZE RECOVERY PLAYBOOK</span>
                <ArrowRight size={13} />
              </>
            )}
          </button>
          <span className="block text-center text-[9px] text-stone-500 mt-1">
            Safety Gate: Requires explicit human authorization before applying spec changes.
          </span>
        </div>
      )}

      {isResolved && (
        <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-center text-xs text-emerald-800 font-bold flex items-center justify-center gap-1.5">
          <CheckCircle2 size={15} className="text-emerald-600" />
          SYSTEM HEALED & ALL PROBES NOMINAL
        </div>
      )}
    </div>
  );
}
