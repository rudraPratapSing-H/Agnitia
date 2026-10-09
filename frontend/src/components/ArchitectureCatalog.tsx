// frontend/src/components/ArchitectureCatalog.tsx - Enterprise Architecture Presets & Microservices Registry
import React, { useState } from 'react';
import {
  Shield,
  Layers,
  Database,
  Server,
  Globe,
  Radio,
  CheckCircle2,
  Cpu,
  HardDrive,
  ArrowRight,
  Flame,
  Search,
  Filter,
  Sparkles,
  ExternalLink,
  Info
} from 'lucide-react';
import { PresetId, PRESETS, ArchitecturePreset } from '../presets';
import { setActivePreset } from '../store';
import { playClickTone, playSuccessChime } from '../lib/sounds';

interface ArchitectureCatalogProps {
  activePresetId: PresetId;
  onSelectPreset?: (id: PresetId) => void;
  onReturnToMissionControl: () => void;
}

const TIER_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  data: Database,
  backend: Server,
  edge: Shield,
  frontend: Globe,
  queue: Radio
};

export default function ArchitectureCatalog({
  activePresetId,
  onSelectPreset,
  onReturnToMissionControl
}: ArchitectureCatalogProps) {
  const [selectedPresetId, setSelectedPresetId] = useState<PresetId>(activePresetId);
  const [searchQuery, setSearchQuery] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('all');

  const preset = PRESETS[selectedPresetId];
  const servicesList = Object.values(preset.initialServices);

  const filteredServices = servicesList.filter((s) => {
    const matchesSearch =
      s.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (preset.serviceMeta[s.id]?.role || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTier = tierFilter === 'all' || s.tier === tierFilter;
    return matchesSearch && matchesTier;
  });

  const handleActivate = (id: PresetId) => {
    playClickTone();
    playSuccessChime();
    setActivePreset(id);
    setSelectedPresetId(id);
    if (onSelectPreset) {
      onSelectPreset(id);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-4 font-sans max-w-7xl mx-auto w-full pb-8">
      {/* Top Banner */}
      <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs flex flex-wrap items-center justify-between gap-4 font-mono">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-stone-900 text-white flex items-center justify-center shadow-xs">
            <Layers size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-black tracking-tight text-stone-900 uppercase">
                Architecture Presets & Service Catalog
              </h2>
              <span className="text-[10px] font-bold text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                MULTI-TOPOLOGY ENGINE
              </span>
            </div>
            <p className="text-xs text-stone-500 font-sans mt-0.5">
              Select and simulate between standard Kubernetes microservices and production Amazon hyperscale architecture.
            </p>
          </div>
        </div>

        <button
          onClick={onReturnToMissionControl}
          className="bg-stone-900 hover:bg-black text-white px-4 py-2 rounded-lg text-xs font-bold font-mono tracking-wider flex items-center gap-2 shadow-xs transition-transform active:scale-95"
        >
          <span>OPEN SRE MISSION CONTROL</span>
          <ArrowRight size={14} />
        </button>
      </div>

      {/* Preset Selector Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(Object.keys(PRESETS) as PresetId[]).map((id) => {
          const p = PRESETS[id];
          const isActive = activePresetId === id;
          const isSelected = selectedPresetId === id;

          return (
            <div
              key={id}
              onClick={() => setSelectedPresetId(id)}
              className={`rounded-xl border p-5 cursor-pointer transition-all ${
                isSelected
                  ? 'border-stone-900 bg-white ring-2 ring-stone-900/10 shadow-md'
                  : 'border-stone-200 bg-white/80 hover:bg-white hover:border-stone-300 shadow-2xs'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${
                      id === 'amazon-scale'
                        ? 'bg-amber-100 text-amber-900 border border-amber-200'
                        : 'bg-stone-100 text-stone-900 border border-stone-200'
                    }`}
                  >
                    {id === 'amazon-scale' ? <Sparkles size={16} /> : <Server size={16} />}
                  </div>
                  <div>
                    <h3 className="text-sm font-black text-stone-900 flex items-center gap-2 font-mono">
                      {p.name}
                      {isActive && (
                        <span className="text-[9px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded border border-emerald-300 flex items-center gap-1">
                          <CheckCircle2 size={10} />
                          LIVE CLUSTER
                        </span>
                      )}
                    </h3>
                    <p className="text-[11px] text-stone-500 font-sans">{p.tagline}</p>
                  </div>
                </div>

                <span className="text-[10px] font-mono font-bold text-stone-600 bg-stone-100 px-2 py-0.5 rounded border border-stone-200">
                  {p.badge}
                </span>
              </div>

              <p className="text-xs text-stone-600 font-sans mt-3 line-clamp-2">{p.description}</p>

              {/* Architecture Specs Matrix */}
              <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-stone-100 font-mono text-[10px]">
                <div className="bg-stone-50 p-2 rounded-lg border border-stone-100">
                  <span className="text-stone-400 block text-[9px]">SERVICES</span>
                  <span className="font-bold text-stone-800 text-xs">{p.nodeCount} Pods</span>
                </div>
                <div className="bg-stone-50 p-2 rounded-lg border border-stone-100">
                  <span className="text-stone-400 block text-[9px]">TIERS</span>
                  <span className="font-bold text-stone-800 text-xs">{p.tierCount} Levels</span>
                </div>
                <div className="bg-stone-50 p-2 rounded-lg border border-stone-100">
                  <span className="text-stone-400 block text-[9px]">THROUGHPUT</span>
                  <span className="font-bold text-stone-800 text-xs">{p.avgThroughput}</span>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 pt-2">
                <span className="text-[11px] text-stone-400 font-mono">Infra: {p.clusterType}</span>
                {isActive ? (
                  <button
                    disabled
                    className="bg-emerald-50 text-emerald-800 border border-emerald-300 px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono flex items-center gap-1.5 cursor-default"
                  >
                    <CheckCircle2 size={13} />
                    <span>ACTIVE</span>
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleActivate(id);
                    }}
                    className="bg-stone-900 hover:bg-black text-white px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono flex items-center gap-1.5 transition-colors shadow-2xs"
                  >
                    <span>ACTIVATE THIS PRESET</span>
                    <ArrowRight size={13} />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Preset Microservices Inventory */}
      <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-stone-200">
          <div>
            <h3 className="text-sm font-black text-stone-900 font-mono flex items-center gap-2">
              <span>{preset.name.toUpperCase()} SERVICE REGISTRY</span>
              <span className="text-[10px] font-bold text-stone-500 bg-stone-100 px-2 py-0.5 rounded border border-stone-200">
                {filteredServices.length} of {servicesList.length} SERVICES
              </span>
            </h3>
            <p className="text-xs text-stone-500 font-sans mt-0.5">
              Review memory limits, CPU baseline allocations, upstream dependencies, and downstream blast radius.
            </p>
          </div>

          {/* Search & Tier Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-2.5 text-stone-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search microservices..."
                className="pl-8 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg text-stone-800 placeholder-stone-400 focus:outline-none focus:border-stone-400 font-sans w-48"
              />
            </div>

            <div className="flex items-center bg-stone-50 p-1 rounded-lg border border-stone-200 text-[10px] font-mono">
              {[
                { id: 'all', label: 'All' },
                { id: 'data', label: 'Data' },
                { id: 'backend', label: 'Backend' },
                { id: 'edge', label: 'Edge' },
                { id: 'frontend', label: 'Frontend' }
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTierFilter(t.id)}
                  className={`px-2 py-1 rounded font-bold transition-colors ${
                    tierFilter === t.id
                      ? 'bg-stone-900 text-white shadow-2xs'
                      : 'text-stone-600 hover:bg-stone-200/60'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Microservices Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 mt-4">
          {filteredServices.map((srv) => {
            const meta = preset.serviceMeta[srv.id] || {
              role: 'Domain microservice component',
              resilience: 'Standard multi-pod deployment',
              avgThroughput: '1,000 req/s',
              p99Latency: '10 ms'
            };

            const Icon = TIER_ICONS[srv.tier] || Server;
            const downstream = preset.downstreamGraph[srv.id] || [];

            return (
              <div
                key={srv.id}
                className="border border-stone-200 rounded-xl p-3.5 bg-stone-50/50 hover:bg-white hover:border-stone-300 transition-all flex flex-col justify-between shadow-2xs"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-stone-100 text-stone-700 border border-stone-200 flex items-center justify-center">
                        <Icon size={14} />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-stone-900 font-mono">{srv.label}</h4>
                        <span className="text-[10px] text-stone-400 font-mono">id: {srv.id}</span>
                      </div>
                    </div>

                    <span className="text-[9px] font-mono font-bold uppercase px-2 py-0.5 rounded border bg-white border-stone-200 text-stone-600">
                      {srv.tier}
                    </span>
                  </div>

                  <p className="text-[11px] text-stone-600 font-sans mt-2.5 leading-snug">
                    {meta.role}
                  </p>
                </div>

                <div className="mt-3.5 pt-3 border-t border-stone-200/70 font-mono text-[10px] flex flex-col gap-2">
                  {/* Metrics Specs */}
                  <div className="grid grid-cols-2 gap-1.5 text-stone-600">
                    <div className="flex items-center gap-1">
                      <HardDrive size={11} className="text-stone-400" />
                      <span>MEM LIMIT:</span>
                      <strong className="text-stone-900">{srv.metrics.mem_limit_mb} MiB</strong>
                    </div>
                    <div className="flex items-center gap-1">
                      <Cpu size={11} className="text-stone-400" />
                      <span>CPU BASE:</span>
                      <strong className="text-stone-900">{srv.metrics.cpu_pct}%</strong>
                    </div>
                  </div>

                  {/* Upstream & Downstream Dependencies */}
                  <div className="flex flex-col gap-1 text-[9px] pt-1">
                    <div className="flex items-center gap-1 text-stone-500">
                      <span>Depends on:</span>
                      {srv.depends_on.length > 0 ? (
                        <div className="flex items-center gap-1 flex-wrap">
                          {srv.depends_on.map((dep) => (
                            <span
                              key={dep}
                              className="px-1 py-0.2 rounded bg-stone-100 border border-stone-200 text-stone-700 font-bold"
                            >
                              {dep}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="italic text-stone-400">None (Root source)</span>
                      )}
                    </div>

                    <div className="flex items-center gap-1 text-amber-700">
                      <span>Blast radius:</span>
                      {downstream.length > 0 ? (
                        <div className="flex items-center gap-1 flex-wrap">
                          {downstream.map((v) => (
                            <span
                              key={v}
                              className="px-1 py-0.2 rounded bg-amber-50 border border-amber-200 text-amber-800 font-bold"
                            >
                              {v}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-stone-400 italic">Edge terminal (0 victims)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
