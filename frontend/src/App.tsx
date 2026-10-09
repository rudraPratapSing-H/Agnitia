// frontend/src/App.tsx - SRE Mission Control & Multi-Architecture Control Plane
import React, { useEffect, useState } from 'react';
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
import CostTicker from './components/extras/CostTicker';
import ArchitectureCatalog from './components/ArchitectureCatalog';
import { PRESETS } from './presets';
import { Shield, Volume2, VolumeX, Keyboard, Layers, Activity, Sparkles } from 'lucide-react';
import { setMuted as setAudioMuted, playAlertSiren, playSuccessChime, playClickTone } from './lib/sounds';

export default function App() {
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

  const [activeView, setActiveView] = useState<'mission-control' | 'catalog'>('mission-control');
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [isApprovalOpen, setIsApprovalOpen] = useState(false);
  const [isPostmortemOpen, setIsPostmortemOpen] = useState(false);
  const [isAuthorizing, setIsAuthorizing] = useState(false);

  const currentPreset = PRESETS[activePresetId] || PRESETS['k8s-core'];

  useEffect(() => {
    connectWebSocket();
  }, []);

  // Audio cues on state changes
  useEffect(() => {
    if (incident && incident.status === 'awaiting_approval') {
      playAlertSiren();

      // If Autonomy Level 3 is active, auto-heal after 1.5s countdown
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

  // Global Keyboard Shortcuts (Hotkeys for stage demo)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Do not capture if active in input or textarea
      const targetTag = (e.target as HTMLElement)?.tagName;
      if (targetTag === 'INPUT' || targetTag === 'TEXTAREA') return;

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
      } else if (e.key === 'c' || e.key === 'C') {
        playClickTone();
        setActiveView((prev) => (prev === 'mission-control' ? 'catalog' : 'mission-control'));
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
      } else if (e.key === 'm' || e.key === 'M') {
        toggleSound();
      } else if (e.key === 'Escape') {
        setIsEvidenceOpen(false);
        setIsApprovalOpen(false);
        setIsPostmortemOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [incident, isApprovalOpen, soundMuted]);

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
              <span className="text-[10px] font-bold text-stone-600 bg-stone-100 px-2 py-0.5 rounded border border-stone-200">
                SRE CONTROL PLANE
              </span>
            </h1>
            <p className="text-[10px] text-stone-500 font-sans">
              Topological Root Cause Analysis & Autonomous Self-Healing
            </p>
          </div>
        </div>

        {/* View Switcher: Mission Control vs Architecture Catalog */}
        <div className="bg-stone-100 p-1 rounded-lg border border-stone-200 flex items-center gap-1 text-[11px] font-mono">
          <button
            onClick={() => {
              playClickTone();
              setActiveView('mission-control');
            }}
            className={`px-3 py-1.5 rounded-md font-bold transition-all flex items-center gap-1.5 ${
              activeView === 'mission-control'
                ? 'bg-white text-stone-900 shadow-2xs'
                : 'text-stone-600 hover:text-stone-900'
            }`}
          >
            <Activity size={13} />
            <span>MISSION CONTROL</span>
          </button>
          <button
            onClick={() => {
              playClickTone();
              setActiveView('catalog');
            }}
            className={`px-3 py-1.5 rounded-md font-bold transition-all flex items-center gap-1.5 ${
              activeView === 'catalog'
                ? 'bg-white text-stone-900 shadow-2xs'
                : 'text-stone-600 hover:text-stone-900'
            }`}
          >
            <Layers size={13} />
            <span>ARCHITECTURE PRESETS</span>
            <span className="text-[9px] bg-stone-200/80 text-stone-700 px-1 rounded font-bold">2</span>
          </button>
        </div>

        {/* Global Hotkeys Legend */}
        <div className="hidden 2xl:flex items-center gap-2 text-[9px] font-mono text-stone-500 bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg">
          <span className="font-extrabold text-stone-400 flex items-center gap-1">
            <Keyboard size={11} />
            HOTKEYS:
          </span>
          <span>
            <kbd className="px-1 py-0.2 bg-white border border-stone-300 rounded font-bold text-stone-800">1..4</kbd> Inject
          </span>
          <span>
            <kbd className="px-1 py-0.2 bg-white border border-stone-300 rounded font-bold text-stone-800">C</kbd> Presets
          </span>
          <span>
            <kbd className="px-1 py-0.2 bg-white border border-stone-300 rounded font-bold text-stone-800">A</kbd> Authorize
          </span>
          <span>
            <kbd className="px-1 py-0.2 bg-white border border-stone-300 rounded font-bold text-stone-800">R</kbd> Reset
          </span>
        </div>

        {/* Header Telemetry Badges with Preset Indicator */}
        <div className="flex items-center gap-2 text-xs flex-wrap">
          {/* Active Preset Pill */}
          <div className="bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5 font-mono">
            <span className="text-stone-400 text-[10px]">TOPOLOGY:</span>
            <button
              onClick={() => {
                playClickTone();
                setActivePreset(activePresetId === 'k8s-core' ? 'amazon-scale' : 'k8s-core');
              }}
              title="Click to toggle architecture preset"
              className="text-[10px] font-bold text-stone-900 hover:text-amber-700 flex items-center gap-1"
            >
              {activePresetId === 'amazon-scale' ? <Sparkles size={11} className="text-amber-600" /> : null}
              <span>{currentPreset.shortName}</span>
              <span className="text-[8px] text-stone-400 underline ml-0.5">toggle</span>
            </button>
          </div>

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
            title={soundMuted ? 'Audio muted (M)' : 'Audio alerts enabled (M)'}
          >
            {soundMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
            <span className="text-[9px] font-bold">{soundMuted ? 'MUTED' : 'AUDIO'}</span>
          </button>

          <div className="bg-stone-50 border border-stone-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-emerald-500' : 'bg-stone-400'
              }`}
            />
            <span className="text-stone-500 text-[10px]">TELEMETRY:</span>
            <span className="font-bold text-[10px] text-stone-700 font-mono">
              {wsConnected ? 'LIVE WS' : 'STANDALONE'}
            </span>
          </div>
        </div>
      </header>

      {/* Early Predictive Capacity Alert Banner */}
      {prediction && <PredictionBanner prediction={prediction} />}

      {/* Active View Content */}
      {activeView === 'catalog' ? (
        <ArchitectureCatalog
          activePresetId={activePresetId}
          onSelectPreset={() => setActiveView('mission-control')}
          onReturnToMissionControl={() => setActiveView('mission-control')}
        />
      ) : (
        <>
          {/* 5-Stage Pipeline Progress Strip */}
          <AgentStrip agentSteps={agentSteps} incident={incident} alerts={alerts} />

          {/* Main Grid: Left 58% Vertical Map, Right 42% Incident Column */}
          <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-2.5 min-h-[580px]">
            {/* Left: Vertical Architecture Map with What-If Mode */}
            <section className="lg:col-span-7 h-[740px] min-h-[720px] relative">
              <DependencyMap
                services={services}
                activePresetId={activePresetId}
                activeScenario={activeScenario}
                whatIfNode={whatIfNode}
                onSelectWhatIf={setWhatIfNode}
                onOpenCatalog={() => setActiveView('catalog')}
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
        </>
      )}

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
