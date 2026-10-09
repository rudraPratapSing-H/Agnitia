// frontend/src/App.tsx - SRE Mission Control: Multi-Page Architecture Selection & Simulation
import React, { useEffect, useState, useCallback } from 'react';
import { useAgnitiaStore, setWhatIfNode, setSoundMuted, resetStore, setActivePreset } from './store';
import { connectWebSocket, executeFullHealFlow, playScenario } from './ws';
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
import ArchitectureSelectionPage from './pages/ArchitectureSelectionPage';
import { PresetId, PRESETS } from './presets';
import { Shield, Volume2, VolumeX, Keyboard, ArrowLeft, Sparkles, Server } from 'lucide-react';
import { setMuted as setAudioMuted, playAlertSiren, playSuccessChime, playClickTone } from './lib/sounds';
import { setVoiceMuted, speakBriefing } from './lib/voice';
import TimerDemo from './components/extras/dev/TimerDemo';
import ReasoningDemo from './components/extras/dev/ReasoningDemo';
import PostmortemDemo from './components/extras/dev/PostmortemDemo';

type AppPage = 'selection' | 'simulation';

function getInitialPage(): AppPage {
  if (typeof window !== 'undefined' && window.location.pathname === '/simulation') {
    return 'simulation';
  }
  return 'selection';
}

export default function App() {
  const demoParam =
    typeof window !== 'undefined'
      ? new URLSearchParams(window.location.search).get('demo')
      : null;

  if (demoParam === 'timer') {
    return <TimerDemo />;
  }
  if (demoParam === 'reasoning') {
    return <ReasoningDemo />;
  }
  if (demoParam === 'postmortem') {
    return <PostmortemDemo />;
  }

  const {
    activePresetId,
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

  const [currentPage, setCurrentPage] = useState<AppPage>(getInitialPage);
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [isApprovalOpen, setIsApprovalOpen] = useState(false);
  const [isPostmortemOpen, setIsPostmortemOpen] = useState(false);
  const [isAuthorizing, setIsAuthorizing] = useState(false);

  const currentPreset = PRESETS[activePresetId] || PRESETS['k8s-core'];

  // Handle URL navigation with browser history
  const navigateTo = useCallback((page: AppPage) => {
    setCurrentPage(page);
    const targetPath = page === 'simulation' ? '/simulation' : '/';
    if (window.location.pathname !== targetPath) {
      window.history.pushState(null, '', targetPath);
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPage(window.location.pathname === '/simulation' ? 'simulation' : 'selection');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    connectWebSocket();
  }, []);

  // Audio cues on state changes -- keyed on incident id + status only, NOT autonomyLevel,
  // so moving the autonomy slider while an incident is awaiting approval doesn't replay the
  // siren/voice briefing (that was overlapping an in-flight TTS call with a new one).
  useEffect(() => {
    if (incident && incident.status === 'awaiting_approval') {
      playAlertSiren();

      const rootCause = incident.rca?.root_cause || `an issue in ${incident.root_service}`;
      speakBriefing(
        `Incident ${incident.id}. Root cause: ${rootCause}. ` +
        `${incident.impacted_services.length} services impacted. Awaiting your approval.`
      );
    } else if (incident && incident.status === 'resolved') {
      playSuccessChime();
    }
  }, [incident?.id, incident?.status]);

  // Autonomy Level 3 auto-heal countdown -- separate effect so it can react to the
  // slider changing mid-incident without re-triggering the announcement above.
  useEffect(() => {
    if (incident && incident.status === 'awaiting_approval' && autonomyLevel === 3) {
      const timer = setTimeout(() => {
        executeFullHealFlow();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [incident?.id, incident?.status, autonomyLevel]);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName;
      if (targetTag === 'INPUT' || targetTag === 'TEXTAREA') return;

      if (currentPage === 'simulation') {
        if (e.key === '1') {
          playClickTone();
          playScenario('db_oom');
        } else if (e.key === '2') {
          playClickTone();
          playScenario('bad_config');
        } else if (e.key === '3') {
          playClickTone();
          playScenario('cpu_spike');
        } else if (e.key === '4') {
          playClickTone();
          playScenario('slow_leak');
        } else if (e.key === 'r' || e.key === 'R') {
          playClickTone();
          resetStore();
        } else if (e.key === 'a' || e.key === 'A') {
          if (incident && incident.status === 'awaiting_approval') {
            if (!isApprovalOpen) {
              setIsApprovalOpen(true);
            } else {
              handleAuthorizePlaybook();
            }
          }
        } else if (e.key === 'e' || e.key === 'E') {
          if (incident) {
            setIsEvidenceOpen((prev) => !prev);
          }
        } else if (e.key === 'p' || e.key === 'P') {
          if (incident) {
            setIsPostmortemOpen((prev) => !prev);
          }
        }
      }

      if (e.key === 'm' || e.key === 'M') {
        toggleSound();
      } else if (e.key === 'Escape') {
        setIsEvidenceOpen(false);
        setIsApprovalOpen(false);
        setIsPostmortemOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [incident, isApprovalOpen, soundMuted, currentPage]);

  const toggleSound = () => {
    const next = !soundMuted;
    setSoundMuted(next);
    setAudioMuted(next);
    setVoiceMuted(next);
  };

  const handleAuthorizePlaybook = () => {
    setIsAuthorizing(true);
    executeFullHealFlow();
    setTimeout(() => {
      setIsAuthorizing(false);
      setIsApprovalOpen(false);
    }, 1200);
  };

  const handleSelectArchitecture = (presetId: PresetId) => {
    setActivePreset(presetId);
    navigateTo('simulation');
  };

  // ───────────────────────────────────────────────────────────────────────────
  // PAGE 1: DEDICATED ARCHITECTURE SELECTION PAGE
  // ───────────────────────────────────────────────────────────────────────────
  if (currentPage === 'selection') {
    return (
      <ArchitectureSelectionPage
        currentPresetId={activePresetId}
        onSelectArchitecture={handleSelectArchitecture}
      />
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // PAGE 2: SRE MISSION CONTROL SIMULATION PAGE
  // ───────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#f7f5f0] text-stone-900 flex flex-col p-3 md:p-4 gap-2.5 select-none font-sans">
      {/* Simulation Navbar */}
      <header className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 shadow-2xs flex flex-wrap items-center justify-between gap-2 font-mono">
        {/* Left: Switch Architecture Arrow Button + Brand */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => {
              playClickTone();
              navigateTo('selection');
            }}
            className="p-1.5 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 text-stone-700 hover:text-stone-950 transition-all shadow-2xs active:scale-95 cursor-pointer hover:border-stone-300"
            title="Switch Architecture"
            aria-label="Switch Architecture"
          >
            <ArrowLeft size={16} />
          </button>

          <div className="w-7 h-7 rounded-lg bg-stone-900 text-white flex items-center justify-center shadow-xs">
            <Shield size={16} />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-tight text-stone-900 flex items-center gap-2">
              AGNITIA
              <span className="text-[11px] font-bold text-stone-600 bg-stone-100 px-2 py-0.5 rounded border border-stone-200">
                SRE MISSION CONTROL
              </span>
            </h1>
            <p className="text-[11px] text-stone-500 font-sans">
              Topological Root Cause Analysis & Autonomous Self-Healing
            </p>
          </div>
        </div>

        {/* Right: Active Topology Badge + Telemetry Controls */}
        <div className="flex items-center gap-2 text-xs flex-wrap">
          {/* Active Topology Badge */}
          <div className="bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg text-[10px] font-mono text-stone-800 font-bold flex items-center gap-1.5">
            {activePresetId === 'amazon-scale' ? (
              <Sparkles size={12} className="text-amber-600" />
            ) : (
              <Server size={12} className="text-stone-600" />
            )}
            <span className="text-stone-400 font-normal">SIMULATING:</span>
            <span>{currentPreset.name}</span>
            <span className="text-[9px] bg-stone-200/80 px-1.5 py-0.2 rounded font-mono font-bold text-stone-700">
              {currentPreset.nodeCount} PODS
            </span>
          </div>

          {/* MTTR Stopwatch */}
          <Stopwatch
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
            title={soundMuted ? 'Audio muted (M)' : 'Audio alerts enabled (M)'}
          >
            {soundMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
            <span className="text-[11px] font-bold">{soundMuted ? 'MUTED' : 'AUDIO'}</span>
          </button>

          <div className="bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-emerald-500' : 'bg-stone-400'
              }`}
            />
            <span className="text-stone-500 text-[11px]">TELEMETRY:</span>
            <span className="font-bold text-[11px] text-stone-700">
              {wsConnected ? 'LIVE WS' : 'STANDALONE'}
            </span>
          </div>
        </div>
      </header>

      {/* Early Predictive Capacity Alert Banner */}
      {prediction && <PredictionBanner prediction={prediction} />}

      {/* Main Grid: Left 58% Vertical Topology Map, Right 42% Incident Dossier */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-2.5 min-h-[580px]">
        {/* Left: Vertical Architecture Map with What-If Mode */}
        <section className="lg:col-span-7 h-[740px] min-h-[720px] relative">
          <DependencyMap
            services={services}
            activePresetId={activePresetId}
            activeScenario={activeScenario}
            whatIfNode={whatIfNode}
            onSelectWhatIf={setWhatIfNode}
          />
        </section>

        {/* Right: Alert Stream, Incident Dossier & Log */}
        <section className="lg:col-span-5 h-[740px] max-h-[740px] flex flex-col gap-2.5 overflow-y-auto custom-scrollbar pr-1.5">
          <AlertFunnel alerts={alerts} incident={incident} />
          <AgentStrip
            agentSteps={agentSteps}
            incident={incident}
            alerts={alerts}
            onOpenEvidence={() => setIsEvidenceOpen(true)}
            onOpenApproval={() => setIsApprovalOpen(true)}
            onOpenPostmortem={() => setIsPostmortemOpen(true)}
          />
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
      <footer className="mt-auto shrink-0">
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
