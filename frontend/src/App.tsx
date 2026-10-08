// frontend/src/App.jsx - Agnitia Mission Control Center
import React, { useEffect } from 'react';
import { useAgnitiaStore } from './store';
import { connectWebSocket } from './ws';
import DependencyMap from './components/DependencyMap';
import AlertFunnel from './components/AlertFunnel';
import IncidentCard from './components/IncidentCard';
import AgentStrip from './components/AgentStrip';
import ChaosPanel from './components/ChaosPanel';
import ReasoningPanel from './components/extras/ReasoningPanel';
import { Shield, Activity, Radio, AlertTriangle } from 'lucide-react';

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
    wsConnected
  } = useAgnitiaStore();

  useEffect(() => {
    connectWebSocket();
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col p-3 md:p-4 gap-3 select-none">
      {/* Top Navigation Bar */}
      <header className="bg-zinc-900/90 border border-zinc-800 rounded-xl px-4 py-2.5 backdrop-blur-md shadow-xl flex items-center justify-between font-mono">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-emerald-500 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.5)]">
            <Shield size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-black tracking-tight text-white flex items-center gap-2">
              AGNITIA
              <span className="text-[10px] font-normal text-zinc-400 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700">
                AUTONOMOUS SRE ORCHESTRATOR
              </span>
            </h1>
            <p className="text-[10px] text-zinc-500">
              Topological RCA & Self-Healing Platform · Phase 1
            </p>
          </div>
        </div>

        {/* System & Telemetry Health Badges */}
        <div className="flex items-center gap-3 text-xs">
          <div className="bg-zinc-950/80 border border-zinc-800 px-3 py-1 rounded-lg flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-zinc-400 text-[11px]">CLUSTER:</span>
            <span className="text-zinc-200 font-bold text-[11px]">KIND / SIMULATOR</span>
          </div>

          <div className="bg-zinc-950/80 border border-zinc-800 px-3 py-1 rounded-lg flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span className="text-zinc-400 text-[11px]">WS STREAM:</span>
            <span
              className={`font-bold text-[11px] ${
                wsConnected ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {wsConnected ? 'ONLINE' : 'STANDALONE SAFE'}
            </span>
          </div>
        </div>
      </header>

      {/* Predictive Warning Banner (Feature 16) */}
      {prediction && (
        <div className="bg-gradient-to-r from-cyan-950/90 to-zinc-900 border border-cyan-800/80 rounded-xl p-2.5 px-4 flex items-center justify-between font-mono text-xs text-cyan-300 animate-fadeIn">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-cyan-400 animate-bounce" />
            <span className="font-bold">PREDICTIVE EXHAUSTION DETECTED:</span>
            <span>{prediction.message}</span>
          </div>
          <div className="bg-cyan-950 px-2.5 py-1 rounded border border-cyan-700 font-bold text-[11px]">
            COUNTDOWN: {prediction.seconds}s
          </div>
        </div>
      )}

      {/* 5-Stage Agent Pipeline Status Strip */}
      <AgentStrip agentSteps={agentSteps} incident={incident} />

      {/* Main Mission Control Grid */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-[580px]">
        {/* Left 60%: React Flow Live Dependency Map */}
        <section className="lg:col-span-7 flex flex-col h-[580px] lg:h-full">
          <DependencyMap services={services} activeScenario={activeScenario} />
        </section>

        {/* Right 40%: Alert Funnel, Incident Dossier & Terminal Reasoning */}
        <section className="lg:col-span-5 flex flex-col gap-3 overflow-y-auto max-h-[750px] custom-scrollbar pr-1">
          {/* Alert Funnel with 98% Noise Reduction Collapse */}
          <AlertFunnel alerts={alerts} incident={incident} />

          {/* Active Incident Dossier & HITL Approval Card */}
          <IncidentCard incident={incident} stepStatus={stepStatus} />

          {/* Terminal AI Investigation Log Feed */}
          <ReasoningPanel steps={agentSteps} isSimulating={isSimulating} />
        </section>
      </main>

      {/* Bottom: Chaos Injection Control Bar */}
      <footer className="mt-auto">
        <ChaosPanel
          activeScenario={activeScenario}
          isSimulating={isSimulating}
          wsConnected={wsConnected}
        />
      </footer>
    </div>
  );
}
