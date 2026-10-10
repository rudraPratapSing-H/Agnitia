// D:\CoffeeOverflow\Agnitia\frontend\src\components\ApprovalModal.tsx - Dynamic SRE Authorization Gate
import React, { useState } from 'react';
import {
  X,
  ShieldAlert,
  GitCommit,
  CheckCircle2,
  ArrowRight,
  Lock,
  Layers,
  Terminal,
  Copy,
  Check
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
  const [copiedCmd, setCopiedCmd] = useState(false);

  if (!isOpen || !incident) return null;

  const { id, root_service, scenario, playbook } = incident;

  // Dynamic scenario metadata
  let targetWorkload = 'apps/v1/Deployment: postgres (namespace: default, cluster: prod-us-east-1)';
  let actionDesc = 'Patch container memory limit from 64Mi to 256Mi to eliminate Linux kernel OOM killer eviction loop (cgroup memory.max).';
  let diffFile = 'k8s/postgres-deployment.yaml';
  let diffHeader = '@@ spec.template.spec.containers[0].resources @@';
  let diffOld = '- limits.memory: "64Mi"';
  let diffNew = '+ limits.memory: "256Mi"';
  let diffOldSub = '- requests.memory: "32Mi"';
  let diffNewSub = '+ requests.memory: "128Mi"';
  let kubectlCmd = "kubectl patch deployment postgres -n default --type='strategic' -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"postgres\",\"resources\":{\"limits\":{\"memory\":\"256Mi\"},\"requests\":{\"memory\":\"128Mi\"}}}]}}}}'";

  if (root_service === 'aurora-orders-db' && scenario === 'db_oom') {
    targetWorkload = 'apps/v1/StatefulSet: aurora-orders-db (namespace: retail, cluster: aws-eks-prod)';
    actionDesc = 'Patch container memory limit from 4096Mi to 8192Mi to eliminate shared_buffers allocation failure and OOM loop.';
    diffFile = 'aws/aurora-statefulset.yaml';
    diffHeader = '@@ spec.template.spec.containers[0].resources @@';
    diffOld = '- limits.memory: "4096Mi"';
    diffNew = '+ limits.memory: "8192Mi"';
    diffOldSub = '- requests.memory: "2048Mi"';
    diffNewSub = '+ requests.memory: "4096Mi"';
    kubectlCmd = "kubectl patch statefulset aurora-orders-db -n retail -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"aurora\",\"resources\":{\"limits\":{\"memory\":\"8192Mi\"},\"requests\":{\"memory\":\"4096Mi\"}}}]}}}}'";
  } else if (scenario === 'bad_config' || root_service === 'payment-service') {
    targetWorkload = 'apps/v1/Deployment: payment-service (namespace: default, cluster: prod-us-east-1)';
    actionDesc = 'Rollback broken deployment revision to stable revision to restore missing API keys and secrets.';
    diffFile = 'k8s/payment-service-deployment.yaml';
    diffHeader = '@@ spec.template.spec.containers[0].image @@';
    diffOld = '- image: "payment-service:v2.4.1" # missing secret tokens';
    diffNew = '+ image: "payment-service:v2.4.0" # validated stable revision';
    diffOldSub = '';
    diffNewSub = '';
    kubectlCmd = 'kubectl rollout undo deployment/payment-service -n default';
  } else if (scenario === 'cpu_spike' || root_service === 'auth-service') {
    targetWorkload = 'apps/v1/Deployment: auth-service (namespace: default, cluster: prod-us-east-1)';
    actionDesc = 'Scale deployment replicas from 2 to 6 to relieve 100% CPU thread pool saturation and restore P99 latency.';
    diffFile = 'k8s/auth-service-hpa.yaml';
    diffHeader = '@@ spec.replicas @@';
    diffOld = '- replicas: 2';
    diffNew = '+ replicas: 6';
    diffOldSub = '';
    diffNewSub = '';
    kubectlCmd = 'kubectl scale deployment auth-service --replicas=6 -n default';
  } else if (scenario === 'slow_leak') {
    if (root_service === 'aurora-orders-db') {
      targetWorkload = 'apps/v1/StatefulSet: aurora-orders-db (namespace: retail, cluster: aws-eks-prod)';
      actionDesc = 'Pre-emptively expand container memory limit from 4096Mi to 8192Mi based on buffer pool gradient forecast.';
      diffFile = 'aws/aurora-statefulset.yaml';
      diffHeader = '@@ spec.template.spec.containers[0].resources.limits @@';
      diffOld = '- limits.memory: "4096Mi"';
      diffNew = '+ limits.memory: "8192Mi"';
      diffOldSub = '';
      diffNewSub = '';
      kubectlCmd = "kubectl patch statefulset aurora-orders-db -n retail -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"aurora\",\"resources\":{\"limits\":{\"memory\":\"8192Mi\"}}}]}}}}'";
    } else {
      targetWorkload = 'apps/v1/Deployment: postgres (namespace: default, cluster: prod-us-east-1)';
      actionDesc = 'Pre-emptively expand container memory limit from 64Mi to 128Mi based on linear memory gradient forecast.';
      diffFile = 'k8s/postgres-deployment.yaml';
      diffHeader = '@@ spec.template.spec.containers[0].resources.limits @@';
      diffOld = '- limits.memory: "64Mi"';
      diffNew = '+ limits.memory: "128Mi"';
      diffOldSub = '';
      diffNewSub = '';
      kubectlCmd = "kubectl patch deployment postgres -n default -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"postgres\",\"resources\":{\"limits\":{\"memory\":\"128Mi\"}}}]}}}}'";
    }
  }

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(kubectlCmd);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 1500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/65 backdrop-blur-xs p-4 animate-fadeIn font-mono">
      <div className="w-full max-w-2xl bg-ink-900 rounded-2xl shadow-2xl border border-ink-700 overflow-hidden flex flex-col max-h-[92vh]">

        {/* Header */}
        <div className="p-4 border-b border-ink-700 bg-ink-850 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/15 text-amber-300 flex items-center justify-center border border-amber-500/35 shrink-0">
              <ShieldAlert size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-extrabold text-ink-50 tracking-tight">
                  SRE AUTHORIZATION GATE
                </h2>
                <span className="bg-amber-500/15 text-amber-200 text-[9px] font-bold px-1.5 py-0.5 rounded border border-amber-500/35">
                  OPERATOR APPROVAL REQUIRED
                </span>
              </div>
              <p className="text-[10px] text-ink-500 font-sans">
                OpsOracle Policy APEX-04: Mutation of production specs requires operator authorization
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg hover:bg-ink-800 text-ink-500 hover:text-ink-200 flex items-center justify-center transition-colors"
            title="Close (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="p-4 space-y-3.5 overflow-y-auto custom-scrollbar flex-1">

          {/* Workload Target & Dry-run Banner */}
          <div className="bg-ink-850 rounded-xl p-3 border border-ink-700 space-y-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-ink-500 font-bold">TARGET WORKLOAD:</span>
              <span className="bg-emerald-500/12 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded font-bold flex items-center gap-1">
                <CheckCircle2 size={11} className="text-emerald-400" />
                DRY-RUN VALIDATED (0 ERRORS)
              </span>
            </div>
            <div className="font-bold text-xs text-ink-50">
              {targetWorkload}
            </div>
            <div className="text-[10px] text-ink-400 font-sans leading-relaxed">
              {actionDesc}
            </div>
          </div>

          {/* Unified GitOps YAML Diff */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-ink-200 flex items-center gap-1.5">
                <GitCommit size={14} className="text-ink-300" />
                DECLARATIVE GITOPS DIFF
              </span>
              <span className="text-[9px] text-ink-500 font-mono">
                {diffFile}
              </span>
            </div>

            <div className="bg-ink-950 text-ink-300 rounded-lg p-3 text-[11px] font-mono border border-ink-700 overflow-x-auto">
              <div className="text-ink-500 text-[10px] pb-1 border-b border-ink-700 mb-1.5">
                {diffHeader}
              </div>
              <div className="text-rose-400 bg-rose-500/12 px-1.5 py-0.5 rounded my-0.5">
                {diffOld}
              </div>
              <div className="text-emerald-400 bg-emerald-500/12 px-1.5 py-0.5 rounded my-0.5 font-bold">
                {diffNew}
              </div>
              {diffOldSub && (
                <div className="text-rose-400 bg-rose-500/12 px-1.5 py-0.5 rounded my-0.5">
                  {diffOldSub}
                </div>
              )}
              {diffNewSub && (
                <div className="text-emerald-400 bg-emerald-500/12 px-1.5 py-0.5 rounded my-0.5 font-bold">
                  {diffNewSub}
                </div>
              )}
            </div>
          </div>

          {/* Equivalent Kubectl Command with Copy */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-ink-400 font-bold flex items-center gap-1">
                <Terminal size={11} />
                EQUIVALENT KUBECTL COMMAND:
              </span>
              <button
                onClick={handleCopyCmd}
                className="text-[9px] text-ink-300 hover:text-ink-50 flex items-center gap-1 bg-ink-800 hover:bg-ink-700 px-1.5 py-0.5 rounded border border-ink-600 transition-colors"
              >
                {copiedCmd ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
                <span>{copiedCmd ? 'COPIED' : 'COPY'}</span>
              </button>
            </div>
            <pre className="p-2 bg-ink-850 text-ink-200 rounded border border-ink-700 text-[9.5px] overflow-x-auto whitespace-pre-wrap leading-tight font-mono select-all">
              {kubectlCmd}
            </pre>
          </div>

          {/* Sequential Execution Order */}
          {playbook?.steps && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-ink-200 flex items-center gap-1.5">
                  <Layers size={14} className="text-ink-300" />
                  TOPOLOGICAL RESTART SEQUENCE
                </span>
                <span className="text-[9px] text-ink-500 font-bold">
                  {playbook.steps.length} STAGES
                </span>
              </div>

              <div className="space-y-1">
                {playbook.steps.map((st) => (
                  <div
                    key={st.order}
                    className="flex items-center justify-between text-[10px] p-2 rounded-lg bg-ink-850 border border-ink-700"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className="w-4 h-4 rounded bg-ink-700 text-ink-200 font-bold flex items-center justify-center text-[9px]">
                        {st.order}
                      </span>
                      <span className="font-bold text-ink-100">{st.service}:</span>
                      <span className="truncate text-ink-400 font-mono">{st.action}</span>
                    </div>

                    <span
                      className={`text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase ${
                        st.risk === 'high'
                          ? 'bg-rose-500/12 text-rose-300 border-rose-500/30'
                          : 'bg-ink-800 text-ink-400 border-ink-600'
                      }`}
                    >
                      {st.risk} RISK
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Audit & Rollback Guarantee */}
          <div className="bg-ink-850 rounded-xl p-2.5 border border-ink-700 flex items-center gap-2 text-[10px] text-ink-400 font-sans">
            <Lock size={13} className="text-ink-400 shrink-0" />
            <span>
              All remediation steps are bounded by APEX safety invariants. An immutable audit snapshot is archived in cluster configmap before execution.
            </span>
          </div>

        </div>

        {/* Footer Actions */}
        <div className="p-3.5 border-t border-ink-700 bg-ink-850 flex items-center justify-between gap-2.5 shrink-0">
          <div className="text-[10px] text-ink-500 font-mono">
            Press <kbd className="px-1 py-0.2 bg-ink-800 border border-ink-600 rounded font-bold text-ink-300">A</kbd> to authorize • <kbd className="px-1 py-0.2 bg-ink-800 border border-ink-600 rounded font-bold text-ink-300">Esc</kbd> to hold
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={authorizing}
              className="px-3.5 py-2 rounded-lg border border-ink-600 hover:bg-ink-800 text-ink-200 text-xs font-bold uppercase transition-colors"
            >
              ABORT / HOLD
            </button>

            <button
              onClick={onAuthorize}
              disabled={authorizing}
              className="px-4 py-2 rounded-lg bg-copper-500 hover:bg-copper-400 text-ink-950 text-xs font-black uppercase tracking-wider flex items-center gap-2 transition-all active:scale-[0.99]"
            >
              <kbd className="px-1.5 py-0.2 text-[9px] bg-ink-950/25 text-ink-950 border border-ink-950/30 rounded font-mono">
                A
              </kbd>
              {authorizing ? (
                <span>APPLYING REMEDIATION...</span>
              ) : (
                <>
                  <span>AUTHORIZE &amp; APPLY</span>
                  <ArrowRight size={13} />
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
