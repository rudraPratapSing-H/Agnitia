// D:\CoffeeOverflow\Agnitia\frontend\src\App.tsx - Clean SRE Mission Control with Phase 3
import React, { useEffect, useState } from 'react';
import { useAgnitiaStore, setWhatIfNode, setSoundMuted, setAutonomyLevel } from './store';
import { connectWebSocket, executeFullHealFlow } from './ws';
import DependencyMap from './components/DependencyMap';
import AlertFunnel from './components/AlertFunnel';
import IncidentCard from './components/IncidentCard';
import AgentStrip from './components/AgentStrip';
import ChaosPanel from './components/ChaosPanel';
import EvidenceDrawer from './components/EvidenceDrawer';
import ApprovalModal from './components/ApprovalModal';
import PredictionBanner from './components/PredictionBanner';
import PostmortemView from './components/extras/PostmortemView';
import ReasoningPanel from './components/extras/ReasoningPanel';
import Stopwatch from './components/extras/Stopwatch';
import CostTicker from './components/extras/CostTicker';
import { Shield, Volume2, VolumeX } from 'lucide-react';
import { setMuted as setAudioMuted, playAlertSiren, playSuccessChime } from './lib/sounds';

export default function App() {
  const {
    services,
    alerts,
    incident,
    agentSteps,
    stepStatus,
    prediction,
    activeScenario,
    isSimulating,
    wsConnected,
    autonomyLevel,
    whatIfNode,
    soundMuted
  } = useAgnitiaStore();

  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [isApprovalOpen, setIsApprovalOpen] = useState(false);
  const [isPostmortemOpen, setIsPostmortemOpen] = useState(false);
  const [isAuthorizing, setIsAuthorizing] = useState(false);

  useEffect(() => {
    connectWebSocket();
  }, []);

  // Audio cues on state changes
  useEffect(() => {
    if (incident && incident.status === 'awaiting_approval') {
      playAlertSiren();

      // If Autonomy Level 3 is active, auto-heal after 1.5s countdown!
      if (autonomyLevel === 3) {
        const timer = setTimeout(() => {
          executeFullHealFlow();
        }, 1500);
        return () => clearTimeout(timer);
      }
    } else if (incident && incident.status === 'resolved') {
      playSuccessChime();
    }
  }, [incident?.status, autonomyLevel]);

  const toggleSound = () => {
    const next = !soundMuted;
    setSoundMuted(next);
    setAudioMuted(next);
  };

  const handleAuthorizePlaybook = () => {
    setIsAuthorizing(true);
    executeFullHealFlow();
    setTimeout(() => {
      setIsAuthorizing(false);
      setIsApprovalOpen(false);
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-[#f7f5f0] text-stone-900 flex flex-col p-3 md:p-4 gap-2.5 select-none font-sans">
      {/* Top Header */}
      <header className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 shadow-2xs flex flex-wrap items-center justify-between gap-2 font-mono">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-stone-900 text-white flex items-center justify-center shadow-xs">
            <Shield size={16} />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-tight text-stone-900 flex items-center gap-2">
              AGNITIA
              <span className="text-[10px] font-normal text-stone-600 bg-stone-100 px-2 py-0.5 rounded border border-stone-200">
                INFRA RELIABILITY ORCHESTRATOR
              </span>
            </h1>
            <p className="text-[10px] text-stone-500 font-sans">
              Topological Root Cause Analysis & Autonomous Safe Recovery
            </p>
          </div>
        </div>

        {/* Header Telemetry Badges with Stopwatch & Financial Impact */}
        <div className="flex items-center gap-2 text-xs flex-wrap">
          {/* MTTR Stopwatch */}
          <Stopwatch
            isActive={!!incident && incident.status !== 'resolved'}
            resolvedAt={incident?.resolved_at}
          />

          {/* Downtime Cost Ticker */}
          <CostTicker
            isActive={!!incident && incident.status !== 'resolved'}
            resolvedAt={incident?.resolved_at}
          />

          {/* Sound Toggle */}
          <button
            onClick={toggleSound}
            className={`p-1.5 rounded-lg border transition-colors flex items-center gap-1 ${
              soundMuted
                ? 'bg-stone-100 text-stone-400 border-stone-200'
                : 'bg-emerald-50 text-emerald-800 border-emerald-300'
            }`}
            title={soundMuted ? 'Audio muted' : 'Audio alerts enabled'}
          >
            {soundMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
            <span className="text-[9px] font-bold">{soundMuted ? 'MUTED' : 'AUDIO'}</span>
          </button>

          <div className="bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-stone-500 text-[10px]">CLUSTER:</span>
            <span className="text-stone-800 font-bold text-[10px]">LOCAL K8S</span>
          </div>

          <div className="bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-emerald-500' : 'bg-stone-400'
              }`}
            />
            <span className="text-stone-500 text-[10px]">STREAM:</span>
            <span className="font-bold text-[10px] text-stone-700">
              {wsConnected ? 'LIVE WS' : 'SIMULATOR'}
            </span>
          </div>
        </div>
      </header>

      {/* Early Predictive Capacity Alert Banner */}
      {prediction && (
        <PredictionBanner prediction={prediction} />
      )}

      {/* 5-Stage Pipeline Progress Strip */}
      <AgentStrip agentSteps={agentSteps} incident={incident} />

      {/* Main Grid: Left 58% Vertical Map, Right 42% Incident Column */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-2.5 min-h-[580px]">
        {/* Left: Vertical Architecture Map with What-If Mode */}
        <section className="lg:col-span-7 flex flex-col h-[740px] lg:h-full min-h-[700px]">
          <DependencyMap
            services={services}
            activeScenario={activeScenario}
            whatIfNode={whatIfNode}
            onSelectWhatIf={setWhatIfNode}
          />
        </section>

        {/* Right: Alert Stream, Incident Dossier & Log */}
        <section className="lg:col-span-5 flex flex-col gap-2.5 overflow-y-auto max-h-[760px] custom-scrollbar pr-1">
          <AlertFunnel alerts={alerts} incident={incident} />
          <IncidentCard
            incident={incident}
            stepStatus={stepStatus}
            onOpenEvidence={() => setIsEvidenceOpen(true)}
            onOpenApproval={() => setIsApprovalOpen(true)}
            onOpenPostmortem={() => setIsPostmortemOpen(true)}
          />
          <ReasoningPanel steps={agentSteps} isSimulating={isSimulating} />
        </section>
      </main>

      {/* Bottom Chaos Action Bar + Autonomy Control */}
      <footer className="mt-auto">
        <ChaosPanel
          activeScenario={activeScenario}
          isSimulating={isSimulating}
          wsConnected={wsConnected}
          autonomyLevel={autonomyLevel}
        />
      </footer>

      {/* Evidence Drawer Modal */}
      <EvidenceDrawer
        isOpen={isEvidenceOpen}
        onClose={() => setIsEvidenceOpen(false)}
        incident={incident}
      />

      {/* Human-in-the-Loop Approval Modal */}
      <ApprovalModal
        isOpen={isApprovalOpen}
        onClose={() => setIsApprovalOpen(false)}
        onAuthorize={handleAuthorizePlaybook}
        incident={incident}
        authorizing={isAuthorizing}
      />

      {/* Phase 3 Postmortem Report View */}
      <PostmortemView
        isOpen={isPostmortemOpen}
        onClose={() => setIsPostmortemOpen(false)}
        incident={incident}
      />
    </div>
  );
}
