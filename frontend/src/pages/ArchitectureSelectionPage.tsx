// frontend/src/pages/ArchitectureSelectionPage.tsx - Dedicated Architecture Selection Page
import React from 'react';
import { Shield, Server, Sparkles, ArrowRight, Layers, Cpu, Network, CheckCircle2 } from 'lucide-react';
import { PresetId, PRESETS } from '../presets';
import { playClickTone, playSuccessChime } from '../lib/sounds';

interface ArchitectureSelectionPageProps {
  currentPresetId: PresetId;
  onSelectArchitecture: (presetId: PresetId) => void;
}

export default function ArchitectureSelectionPage({
  currentPresetId,
  onSelectArchitecture
}: ArchitectureSelectionPageProps) {
  const handleSelect = (id: PresetId) => {
    playClickTone();
    playSuccessChime();
    onSelectArchitecture(id);
  };

  return (
    <div className="min-h-screen bg-transparent text-ink-100 flex flex-col justify-between p-4 md:p-8 font-sans select-none">
      {/* Top Brand Bar */}
      <header className="max-w-5xl mx-auto w-full flex items-center justify-between pb-6 border-b border-ink-700 font-mono">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-copper-500 text-ink-950 flex items-center justify-center">
            <Shield size={18} />
          </div>
          <div>
            <span className="text-sm font-black tracking-tight text-ink-50 flex items-center gap-2">
              AGNITIA
              <span className="text-[10px] font-bold text-ink-300 bg-ink-800 px-2 py-0.5 rounded border border-ink-600">
                SRE CONTROL PLANE
              </span>
            </span>
          </div>
        </div>

        <div className="text-[11px] text-ink-500 hidden sm:block">
          Topological Root Cause Analysis &amp; Autonomous Self-Healing
        </div>
      </header>

      {/* Main Center Section */}
      <main className="max-w-5xl mx-auto w-full my-auto py-8 flex flex-col items-center">
        {/* Title & Subtitle */}
        <div className="text-center max-w-2xl mb-10">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-copper-500/10 border border-copper-500/30 text-[10px] font-mono font-bold text-copper-300 uppercase tracking-wider mb-3">
            <Layers size={12} />
            <span>TOPOLOGY BLUEPRINTS</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-ink-50 tracking-tight font-mono">
            SELECT ARCHITECTURE TOPOLOGY
          </h1>
          <p className="text-xs md:text-sm text-ink-400 mt-2 leading-relaxed">
            Choose an infrastructure environment to launch autonomous telemetry correlation,
            blast-radius prediction, and chaos self-healing simulations.
          </p>
        </div>

        {/* The Two Architecture Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full">
          {/* Card 1: Standard K8s Microservices */}
          <div
            onClick={() => handleSelect('k8s-core')}
            className={`group rounded-2xl border p-6 md:p-7 cursor-pointer transition-all duration-200 flex flex-col justify-between hover:-translate-y-1 bg-ink-900 ${
              currentPresetId === 'k8s-core'
                ? 'border-copper-400 shadow-lg shadow-copper-950/40 ring-1 ring-copper-400/30'
                : 'border-ink-700 hover:border-ink-500'
            }`}
          >
            <div>
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="w-12 h-12 rounded-xl bg-ink-800 text-ink-200 flex items-center justify-center border border-ink-600 group-hover:bg-copper-500 group-hover:text-ink-950 transition-colors">
                  <Server size={22} />
                </div>
                <span className="text-[10px] font-mono font-bold text-ink-300 bg-ink-800 px-2.5 py-1 rounded-md border border-ink-600">
                  CORE REFERENCE
                </span>
              </div>

              {/* Title & Tagline */}
              <h2 className="text-lg font-black text-ink-50 font-mono mt-4 tracking-tight">
                Standard K8s Microservices
              </h2>
              <p className="text-xs text-ink-500 font-sans mt-0.5">
                6 Containerized Pods • 4 Causal Tiers
              </p>

              {/* Description */}
              <p className="text-xs text-ink-400 font-sans mt-3.5 leading-relaxed">
                Reference enterprise Kubernetes architecture with PostgreSQL, Redis cache,
                Auth &amp; Payment microservices behind an API Gateway and Web UI.
              </p>

              {/* Specs Pills */}
              <div className="grid grid-cols-3 gap-2 mt-5 pt-4 border-t border-ink-700 font-mono text-[10px]">
                <div className="bg-ink-850 p-2 rounded-lg border border-ink-700">
                  <span className="text-ink-500 block text-[9px]">PODS</span>
                  <span className="font-bold text-ink-100 text-xs">6 Nodes</span>
                </div>
                <div className="bg-ink-850 p-2 rounded-lg border border-ink-700">
                  <span className="text-ink-500 block text-[9px]">TIERS</span>
                  <span className="font-bold text-ink-100 text-xs">4 Levels</span>
                </div>
                <div className="bg-ink-850 p-2 rounded-lg border border-ink-700">
                  <span className="text-ink-500 block text-[9px]">THROUGHPUT</span>
                  <span className="font-bold text-ink-100 text-xs">1,250 req/s</span>
                </div>
              </div>
            </div>

            {/* Launch CTA */}
            <div className="mt-6 pt-4 border-t border-ink-700 flex items-center justify-between">
              <span className="text-[11px] font-mono text-ink-500">
                Infra: Vanilla K8s v1.28
              </span>
              <button
                type="button"
                className="bg-copper-500 group-hover:bg-copper-400 text-ink-950 px-4 py-2 rounded-lg text-xs font-bold font-mono tracking-wider flex items-center gap-2 transition-colors"
              >
                <span>SIMULATE THIS</span>
                <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>
          </div>

          {/* Card 2: Amazon Hyperscale Architecture */}
          <div
            onClick={() => handleSelect('amazon-scale')}
            className={`group rounded-2xl border p-6 md:p-7 cursor-pointer transition-all duration-200 flex flex-col justify-between hover:-translate-y-1 bg-ink-900 ${
              currentPresetId === 'amazon-scale'
                ? 'border-amber-500 shadow-lg shadow-amber-950/40 ring-1 ring-amber-500/25'
                : 'border-ink-700 hover:border-amber-500/50'
            }`}
          >
            <div>
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-300 flex items-center justify-center border border-amber-500/30 group-hover:bg-amber-500 group-hover:text-ink-950 transition-colors">
                  <Sparkles size={22} />
                </div>
                <span className="text-[10px] font-mono font-bold text-amber-300 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/30 flex items-center gap-1">
                  <span>AWS HYPERSCALE</span>
                </span>
              </div>

              {/* Title & Tagline */}
              <h2 className="text-lg font-black text-ink-50 font-mono mt-4 tracking-tight flex items-center gap-2">
                Amazon Hyperscale Architecture
              </h2>
              <p className="text-xs text-ink-500 font-sans mt-0.5">
                20 Distributed Microservices • 6 Causal Tiers
              </p>

              {/* Description */}
              <p className="text-xs text-ink-400 font-sans mt-3.5 leading-relaxed">
                Production-grade AWS e-commerce topology featuring Multi-AZ Aurora DBs,
                DynamoDB, OpenSearch, SQS message bus, domain orchestrators, and CloudFront edge CDN.
              </p>

              {/* Specs Pills */}
              <div className="grid grid-cols-3 gap-2 mt-5 pt-4 border-t border-ink-700 font-mono text-[10px]">
                <div className="bg-amber-500/8 p-2 rounded-lg border border-amber-500/20">
                  <span className="text-ink-500 block text-[9px]">PODS</span>
                  <span className="font-bold text-amber-200 text-xs">20 Nodes</span>
                </div>
                <div className="bg-amber-500/8 p-2 rounded-lg border border-amber-500/20">
                  <span className="text-ink-500 block text-[9px]">TIERS</span>
                  <span className="font-bold text-amber-200 text-xs">6 Levels</span>
                </div>
                <div className="bg-amber-500/8 p-2 rounded-lg border border-amber-500/20">
                  <span className="text-ink-500 block text-[9px]">THROUGHPUT</span>
                  <span className="font-bold text-amber-200 text-xs">84,500 req/s</span>
                </div>
              </div>
            </div>

            {/* Launch CTA */}
            <div className="mt-6 pt-4 border-t border-ink-700 flex items-center justify-between">
              <span className="text-[11px] font-mono text-ink-500">
                Infra: AWS EKS + Managed Cloud
              </span>
              <button
                type="button"
                className="bg-amber-500 hover:bg-amber-400 text-ink-950 px-4 py-2 rounded-lg text-xs font-bold font-mono tracking-wider flex items-center gap-2 transition-colors"
              >
                <span>SIMULATE THIS</span>
                <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-5xl mx-auto w-full pt-4 border-t border-ink-700 flex items-center justify-between text-[11px] text-ink-500 font-mono">
        <span>Agnitia AIOps Platform</span>
        <span>Click an architecture to launch immediate simulation</span>
      </footer>
    </div>
  );
}
