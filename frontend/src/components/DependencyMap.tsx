// frontend/src/components/DependencyMap.tsx - Dynamic Multi-Architecture Topological Dependency Tree
import React, { useMemo, useCallback, useState, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  Node,
  Edge
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import ServiceNode from './ServiceNode';
import { X, Layers, Sparkles, Maximize2, Minimize2 } from 'lucide-react';
import { PresetId, PRESETS } from '../presets';
import { setActivePreset } from '../store';

const nodeTypes = {
  serviceNode: ServiceNode
};

function getReachableDownstream(startNode: string, downstreamGraph: Record<string, string[]>): Set<string> {
  const visited = new Set<string>();
  const queue = [startNode];

  while (queue.length > 0) {
    const current = queue.shift()!;
    const neighbors = downstreamGraph[current] || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push(neighbor);
      }
    }
  }

  return visited;
}

interface DependencyMapProps {
  services: Record<string, any>;
  activePresetId?: PresetId;
  activeScenario?: string | null;
  whatIfNode?: string | null;
  onSelectWhatIf?: (nodeId: string | null) => void;
  onOpenCatalog?: () => void;
  mlPrediction?: { service: string; probability: number; threshold: number; seconds_to_limit: number | null } | null;
}

export default function DependencyMap({
  services,
  activePresetId = 'k8s-core',
  activeScenario,
  whatIfNode,
  onSelectWhatIf,
  onOpenCatalog,
  mlPrediction
}: DependencyMapProps) {
  const currentPreset = PRESETS[activePresetId] || PRESETS['k8s-core'];
  const downstreamGraph = currentPreset.downstreamGraph;
  const positions = currentPreset.layoutPositions;
  const rawPresetEdges = currentPreset.rawEdges;

  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => {
      const next = !prev;
      if (next) {
        try {
          if (document.documentElement.requestFullscreen) {
            document.documentElement.requestFullscreen().catch(() => {});
          }
        } catch (e) {}
      } else {
        try {
          if (document.fullscreenElement && document.exitFullscreen) {
            document.exitFullscreen().catch(() => {});
          }
        } catch (e) {}
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const handleFsChange = () => {
      if (!document.fullscreenElement && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, [isFullscreen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        toggleFullscreen();
      } else if (e.key === 'Escape' && isFullscreen) {
        e.preventDefault();
        toggleFullscreen();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, toggleFullscreen]);

  const whatIfDownstream = useMemo(() => {
    if (!whatIfNode) return new Set<string>();
    return getReachableDownstream(whatIfNode, downstreamGraph);
  }, [whatIfNode, downstreamGraph]);

  const onNodeClick = useCallback(
    (_: any, node: Node) => {
      if (onSelectWhatIf) {
        if (whatIfNode === node.id) {
          onSelectWhatIf(null);
        } else {
          onSelectWhatIf(node.id);
        }
      }
    },
    [whatIfNode, onSelectWhatIf]
  );

  const nodes = useMemo<Node[]>(() => {
    return Object.values(services).map((srv: any) => {
      const isWhatIfOrigin = whatIfNode === srv.id;
      const isWhatIfImpacted = whatIfDownstream.has(srv.id);
      const isDimmed = !!whatIfNode && !isWhatIfOrigin && !isWhatIfImpacted;

      return {
        id: srv.id,
        type: 'serviceNode',
        position: positions[srv.id] || { x: 260, y: 260 },
        data: {
          ...srv,
          _whatIfOrigin: isWhatIfOrigin,
          _whatIfImpacted: isWhatIfImpacted,
          _isDimmed: isDimmed,
          _mlPrediction: mlPrediction && mlPrediction.service === srv.id ? mlPrediction : null
        } as Record<string, any>,
        style: isDimmed ? { opacity: 0.28, transition: 'opacity 0.25s ease' } : { transition: 'opacity 0.25s ease' }
      };
    });
  }, [services, whatIfNode, whatIfDownstream, positions, mlPrediction]);

  const edges = useMemo<Edge[]>(() => {
    return rawPresetEdges.map((edge) => {
      const srcStatus = services[edge.source]?.status;
      const tgtStatus = services[edge.target]?.status;

      const isWhatIfEdge =
        !!whatIfNode &&
        ((edge.source === whatIfNode && whatIfDownstream.has(edge.target)) ||
          (whatIfDownstream.has(edge.source) && whatIfDownstream.has(edge.target)));

      const isSourceRoot = srcStatus === 'root_cause';
      const isSourceImpacted = srcStatus === 'impacted';
      const isTargetFailed = tgtStatus === 'root_cause' || tgtStatus === 'impacted';

      // High-visibility base styling, tuned for a dark canvas
      let strokeColor = '#2fae7a'; // muted emerald for crystal-clear healthy flow
      let strokeWidth = 2.6;
      let isAnimated = true;
      let edgeClass = 'edge-healthy';
      let markerSize = 16;
      let displayLabel = (edge as any).label || 'DEPENDENCY';
      let labelTextColor = '#c2c3c8';
      let labelBgColor = '#121418';
      let labelBorderColor = '#2a2d34';

      if (isWhatIfEdge) {
        strokeColor = '#38bdf8'; // electric cyan
        strokeWidth = 4.0;
        isAnimated = true;
        edgeClass = 'edge-what-if';
        markerSize = 20;
        displayLabel = '⚡ BLAST RADIUS';
        labelTextColor = '#7dd3fc';
        labelBgColor = '#0c1a22';
        labelBorderColor = '#38bdf8';
      } else if (isSourceRoot) {
        // High-energy Crimson failure shockwave bursting from root cause
        strokeColor = '#f43f5e'; // intense crimson
        strokeWidth = 5.2;
        isAnimated = true;
        edgeClass = 'edge-root-cascade';
        markerSize = 24;
        displayLabel = '💥 BLAST WAVE (SATURATED)';
        labelTextColor = '#fda4af';
        labelBgColor = '#1f0a0e';
        labelBorderColor = '#f43f5e';
      } else if (isSourceImpacted) {
        // Glowing Amber cascading degradation propagating downstream
        strokeColor = '#f59e0b'; // amber-500
        strokeWidth = 3.8;
        isAnimated = true;
        edgeClass = 'edge-impact-cascade';
        markerSize = 20;
        displayLabel = '⚠️ CASCADE DEGRADED';
        labelTextColor = '#fcd34d';
        labelBgColor = '#1f1506';
        labelBorderColor = '#f59e0b';
      } else if (isTargetFailed) {
        // Upstream link under backpressure from degraded target
        strokeColor = '#fb923c'; // orange-400
        strokeWidth = 3.2;
        isAnimated = true;
        edgeClass = 'edge-impact-cascade';
        markerSize = 18;
        displayLabel = '⚠️ BACKPRESSURE';
        labelTextColor = '#fdba74';
        labelBgColor = '#1f1105';
        labelBorderColor = '#fb923c';
      } else if (srcStatus === 'healthy' && tgtStatus === 'healthy') {
        strokeColor = '#34d399'; // emerald-400
        strokeWidth = 2.6;
        isAnimated = true;
        edgeClass = 'edge-healthy';
        markerSize = 16;
      }

      const isDimmed = whatIfNode && !isWhatIfEdge && edge.source !== whatIfNode;

      return {
        ...edge,
        type: 'bezier', // Smooth sweeping Bezier curves
        pathOptions: {
          curvature: 0.28
        },
        animated: isAnimated,
        className: edgeClass,
        label: displayLabel,
        labelStyle: {
          fill: labelTextColor,
          fontWeight: 700,
          fontSize: 8.5,
          fontFamily: 'monospace'
        },
        labelBgStyle: {
          fill: labelBgColor,
          fillOpacity: 0.96,
          stroke: labelBorderColor,
          strokeWidth: 1.2,
          rx: 5,
          ry: 5
        },
        labelBgPadding: [6, 2] as [number, number],
        style: {
          stroke: strokeColor,
          strokeWidth,
          opacity: isDimmed ? 0.2 : 1,
          transition: 'stroke 0.35s ease, stroke-width 0.35s ease, opacity 0.3s ease'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: markerSize,
          height: markerSize
        }
      };
    });
  }, [services, whatIfNode, whatIfDownstream, rawPresetEdges]);

  const totalOtherNodes = Math.max(currentPreset.nodeCount - 1, 1);
  const whatIfPercentage = Math.round((whatIfDownstream.size / totalOtherNodes) * 100);

  return (
    <div
      className={
        isFullscreen
          ? 'fixed inset-0 z-40 w-screen h-screen bg-ink-950 flex flex-col p-3 overflow-hidden shadow-2xl transition-all duration-200'
          : 'w-full h-full relative rounded-xl overflow-hidden border border-ink-700 bg-ink-900 shadow-inner min-h-[720px] transition-all duration-200'
      }
    >
      {/* Top Header Overlay */}
      <div className="absolute top-3.5 left-4 z-10 pointer-events-none flex items-center gap-2.5 flex-wrap">
        <div className="bg-ink-850/95 backdrop-blur-sm px-3.5 py-1.5 rounded-lg border border-ink-600 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-[11px] font-bold text-ink-50 tracking-wider font-mono uppercase">
            {currentPreset.name}
          </span>
          <span className="text-[9px] font-bold text-ink-300 bg-ink-700 px-2 py-0.5 rounded border border-ink-600 font-mono">
            {currentPreset.nodeCount} NODES • {currentPreset.tierCount} TIERS
          </span>
        </div>

        {isFullscreen && (
          <div className="bg-ink-850/95 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-ink-600 text-[10px] font-mono text-ink-100 font-bold flex items-center gap-2 animate-fadeIn">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>FULLSCREEN TOPOLOGY MODE</span>
            <span className="text-[9px] text-ink-400 border-l border-ink-600 pl-2">
              EXPANDED POD READABILITY
            </span>
          </div>
        )}

        {activeScenario && (
          <div className="bg-rose-500/12 px-2.5 py-1 rounded-lg border border-rose-500/35 text-[10px] font-mono text-rose-300 font-semibold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
            CASCADE ACTIVE
          </div>
        )}
      </div>

      {/* Top-Right Corner: Fullscreen Toggle Button */}
      <div className="absolute top-3.5 right-4 z-30 flex items-center gap-2">
        <button
          onClick={toggleFullscreen}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg border font-mono text-xs font-bold transition-all duration-150 active:scale-95 cursor-pointer ${
            isFullscreen
              ? 'bg-rose-500/15 hover:bg-rose-500/22 text-rose-300 border-rose-500/40 ring-2 ring-rose-500/25'
              : 'bg-ink-850/95 backdrop-blur-sm hover:bg-ink-700 text-ink-200 border-ink-600 hover:border-ink-500'
          }`}
          title={isFullscreen ? 'Exit Fullscreen (ESC or F)' : 'Make Graph Fullscreen so pod details become readable (F)'}
        >
          {isFullscreen ? (
            <>
              <Minimize2 size={14} className="text-rose-400 shrink-0" />
              <span>EXIT FULLSCREEN</span>
              <kbd className="text-[9px] font-sans font-bold bg-rose-500/25 px-1.5 py-0.5 rounded text-rose-200 border border-rose-500/40">
                ESC
              </kbd>
            </>
          ) : (
            <>
              <Maximize2 size={14} className="text-ink-300 shrink-0" />
              <span>FULLSCREEN</span>
              <kbd className="text-[9px] font-sans font-bold bg-ink-700 px-1.5 py-0.5 rounded text-ink-300 border border-ink-600">
                F
              </kbd>
            </>
          )}
        </button>
      </div>

      {/* Floating What-If Analysis HUD */}
      {whatIfNode && (
        <div className="absolute top-14 left-4 right-4 z-20 bg-sky-950/90 backdrop-blur-sm border-2 border-sky-500/50 rounded-xl p-2.5 px-3.5 flex items-center justify-between shadow-lg font-mono text-xs text-sky-100 animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-sky-500 text-ink-950 flex items-center justify-center font-bold text-[10px]">
              ?
            </div>
            <div>
              <span className="font-bold text-sky-200 block text-[11px]">
                WHAT-IF SIMULATION: IF <code className="bg-ink-900 px-1.5 py-0.5 rounded border border-sky-500/40 font-bold text-sky-200 uppercase">{whatIfNode}</code> FAILS
              </span>
              <span className="text-[10px] text-sky-400 font-sans">
                Hypothetical Blast Radius: <strong>{whatIfDownstream.size}</strong> downstream services impacted ({whatIfPercentage}% of dependent topology).
              </span>
            </div>
          </div>

          <button
            onClick={() => onSelectWhatIf && onSelectWhatIf(null)}
            className="text-[10px] font-bold text-sky-200 bg-ink-900 hover:bg-sky-500/15 px-2.5 py-1 rounded-md border border-sky-500/40 flex items-center gap-1 transition-colors"
          >
            <X size={12} />
            <span>EXIT WHAT-IF</span>
          </button>
        </div>
      )}

      {/* Legend & What-If Prompt */}
      <div className="absolute bottom-3.5 left-4 z-10 pointer-events-none bg-ink-850/95 backdrop-blur-sm px-3.5 py-2 rounded-lg border border-ink-600 flex items-center gap-3.5 text-[10px] font-mono text-ink-300 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span>Nominal Flow</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.8)]" />
          <span>Root Failure Wave</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.8)]" />
          <span>Cascading Wave</span>
        </div>
        <div className="flex items-center gap-1.5 text-ink-500 pl-1 border-l border-ink-700">
          <span>Click any node for What-If blast radius</span>
        </div>
      </div>

      <ReactFlow
        key={`${activePresetId}-${isFullscreen ? 'fullscreen' : 'windowed'}`}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: isFullscreen ? 0.08 : 0.14 }}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
        minZoom={0.2}
        maxZoom={2.4}
      >
        <Background color="#cbd5e1" gap={isFullscreen ? 28 : 24} size={1.2} />
        <Controls className="!bg-ink-850 !border-ink-600 !fill-ink-300 !shadow-lg" />
      </ReactFlow>
    </div>
  );
}
