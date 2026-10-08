// D:\CoffeeOverflow\Agnitia\frontend\src\App.tsx - Clean SRE Mission Control
import React, { useEffect } from 'react';
import { useAgnitiaStore } from './store';
import { connectWebSocket } from './ws';
import DependencyMap from './components/DependencyMap';
import AlertFunnel from './components/AlertFunnel';
import IncidentCard from './components/IncidentCard';
import AgentStrip from './components/AgentStrip';
import ChaosPanel from './components/ChaosPanel';
import ReasoningPanel from './components/extras/ReasoningPanel';
import { Shield, AlertTriangle } from 'lucide-react';
import TimerDemo from './components/extras/dev/TimerDemo';
import ReasoningDemo from './components/extras/dev/ReasoningDemo';

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
    <div className="min-h-screen bg-[#f7f5f0] text-stone-900 flex flex-col p-3 md:p-4 gap-2.5 select-none font-sans">
      {/* Top Header */}
      <header className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 shadow-2xs flex items-center justify-between font-mono">
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
            <p className="text-[10px] text-stone-500">
              Topological Root Cause Analysis & Automated Safe Recovery
            </p>
          </div>
        </div>

        {/* Telemetry Status Badges */}
        <div className="flex items-center gap-2 text-xs">
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

      {/* Early Predictive Warning Banner */}
      {prediction && (
        <div className="bg-sky-50 border border-sky-200 rounded-xl p-2.5 px-4 flex items-center justify-between font-mono text-xs text-sky-900 animate-fadeIn shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-sky-700 animate-bounce" />
            <span className="font-bold">PREDICTIVE WARNING:</span>
            <span>{prediction.message}</span>
          </div>
          <div className="bg-sky-100 px-2.5 py-1 rounded border border-sky-300 font-bold text-[11px]">
            COUNTDOWN: {prediction.seconds}s
          </div>
        </div>
      )}

      {/* 5-Stage Pipeline Progress Strip */}
      <AgentStrip agentSteps={agentSteps} incident={incident} />

      {/* Main Grid: Left 58% Vertical Map, Right 42% Incident Column */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-2.5 min-h-[580px]">
        {/* Left: Vertical Architecture Map */}
        <section className="lg:col-span-7 flex flex-col h-[740px] lg:h-full min-h-[700px]">
          <DependencyMap services={services} activeScenario={activeScenario} />
        </section>

        {/* Right: Alert Stream, Incident Dossier & Log */}
        <section className="lg:col-span-5 flex flex-col gap-2.5 overflow-y-auto max-h-[760px] custom-scrollbar pr-1">
          <AlertFunnel alerts={alerts} incident={incident} />
          <IncidentCard incident={incident} stepStatus={stepStatus} />
          <ReasoningPanel steps={agentSteps} isSimulating={isSimulating} />
        </section>
      </main>

      {/* Bottom Chaos Action Bar */}
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
