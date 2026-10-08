// D:\CoffeeOverflow\Agnitia\frontend\src\components\ApprovalModal.tsx - Human-in-the-Loop Gate
import React from 'react';
import {
  X,
  ShieldAlert,
  GitCommit,
  CheckCircle2,
  ArrowRight,
  AlertTriangle,
  Lock,
  Layers
} from 'lucide-react';
import { Incident } from '../types';

interface ApprovalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthorize: () => void;
  incident: Incident | null;
  authorizing?: boolean;
}

export default function ApprovalModal({
  isOpen,
  onClose,
  onAuthorize,
  incident,
  authorizing = false
}: ApprovalModalProps) {
  if (!isOpen || !incident) return null;

  const { id, playbook } = incident;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 backdrop-blur-xs p-4 animate-fadeIn font-mono">
      <div className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-stone-300 overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-4 border-b border-stone-200 bg-stone-50/80 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center border border-amber-200">
              <ShieldAlert size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-extrabold text-stone-900 tracking-tight">
                  AUTHORIZATION GATE
                </h2>
                <span className="bg-amber-100 text-amber-900 text-[10px] font-bold px-1.5 py-0.5 rounded border border-amber-300">
                  HUMAN APPROVAL REQUIRED
                </span>
              </div>
              <p className="text-[10px] text-stone-500 font-sans">
                Agnitia Policy APEX-04: Production spec mutation requires operator authorization
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg hover:bg-stone-200 text-stone-400 hover:text-stone-700 flex items-center justify-center transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="p-4 space-y-4 overflow-y-auto custom-scrollbar flex-1">
          
          {/* Target Resource */}
          <div className="bg-stone-50 rounded-xl p-3 border border-stone-200 text-xs space-y-1">
            <div className="flex items-center justify-between text-stone-500 text-[10px]">
              <span>TARGET WORKLOAD:</span>
              <span className="bg-stone-200 px-1.5 py-0.5 rounded text-stone-700 font-bold">KUBERNETES</span>
            </div>
            <div className="font-bold text-stone-900">
              apps/v1/Deployment: postgres-cluster (default)
            </div>
            <div className="text-[10px] text-stone-500 font-sans">
              Action: Patch pod memory limit to resolve OOM crashloop and restore downstream connectivity.
            </div>
          </div>

          {/* Kubernetes Spec Diff */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-stone-800 flex items-center gap-1.5">
                <GitCommit size={14} className="text-stone-600" />
                PROPOSED CONFIG DIFF (64Mi &rarr; 256Mi)
              </span>
              <span className="text-[9px] text-stone-500 font-mono">
                ALLOW-LISTED MUTATION
              </span>
            </div>

            <div className="bg-stone-950 text-stone-200 rounded-lg p-3 text-[11px] font-mono border border-stone-800 overflow-x-auto shadow-inner">
              <div className="text-stone-500 text-[10px] pb-1 border-b border-stone-800 mb-1.5">
                @@ spec.template.spec.containers[0].resources @@
              </div>
              <div className="text-rose-400 bg-rose-950/40 px-1.5 py-0.5 rounded my-0.5">
                - limits.memory: &quot;64Mi&quot;
              </div>
              <div className="text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded my-0.5 font-bold">
                + limits.memory: &quot;256Mi&quot;
              </div>
              <div className="text-rose-400 bg-rose-950/40 px-1.5 py-0.5 rounded my-0.5">
                - requests.memory: &quot;32Mi&quot;
              </div>
              <div className="text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded my-0.5 font-bold">
                + requests.memory: &quot;128Mi&quot;
              </div>
            </div>
          </div>

          {/* Sequential Execution Order */}
          {playbook?.steps && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-stone-800 flex items-center gap-1.5">
                  <Layers size={14} className="text-stone-600" />
                  TOPOLOGICAL EXECUTION SEQUENCE
                </span>
                <span className="text-[9px] text-stone-500">
                  {playbook.steps.length} ORDERED STEPS
                </span>
              </div>

              <div className="space-y-1">
                {playbook.steps.map((st) => (
                  <div
                    key={st.order}
                    className="flex items-center justify-between text-[10px] p-2 rounded-lg bg-stone-50 border border-stone-200/80"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className="w-4 h-4 rounded bg-stone-200 text-stone-800 font-bold flex items-center justify-center text-[9px]">
                        {st.order}
                      </span>
                      <span className="font-bold text-stone-900">{st.service}:</span>
                      <span className="truncate text-stone-600 font-mono">{st.action}</span>
                    </div>

                    <span
                      className={`text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase ${
                        st.risk === 'high'
                          ? 'bg-rose-50 text-rose-800 border-rose-200'
                          : 'bg-stone-100 text-stone-600 border-stone-200'
                      }`}
                    >
                      {st.risk} RISK
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Safety & Audit Guarantee */}
          <div className="bg-stone-50 rounded-xl p-2.5 border border-stone-200 flex items-center gap-2 text-[10px] text-stone-600">
            <Lock size={13} className="text-stone-500 shrink-0" />
            <span>
              All recovery actions are constrained to the APEX allow-list. Full audit log persisted with 1-click rollback snapshot.
            </span>
          </div>

        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-stone-200 bg-stone-50/80 flex items-center justify-end gap-2.5 shrink-0">
          <button
            onClick={onClose}
            disabled={authorizing}
            className="px-3.5 py-2 rounded-lg border border-stone-300 hover:bg-stone-100 text-stone-700 text-xs font-bold uppercase transition-colors"
          >
            ABORT / HOLD
          </button>

          <button
            onClick={onAuthorize}
            disabled={authorizing}
            className="px-4 py-2 rounded-lg bg-stone-900 hover:bg-stone-800 text-white text-xs font-extrabold uppercase tracking-wider flex items-center gap-2 transition-all shadow-sm active:scale-[0.99]"
          >
            {authorizing ? (
              <span>APPLYING REMEDIATION...</span>
            ) : (
              <>
                <span>AUTHORIZE & EXECUTE PLAYBOOK</span>
                <ArrowRight size={13} />
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}
