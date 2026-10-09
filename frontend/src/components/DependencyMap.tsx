// frontend/src/components/DependencyMap.tsx - Dynamic Multi-Architecture Topological Dependency Tree
import React, { useMemo, useCallback } from 'react';
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
import { X, Layers, Sparkles } from 'lucide-react';
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
}

export default function DependencyMap({
  services,
  activePresetId = 'k8s-core',
  activeScenario,
  whatIfNode,
  onSelectWhatIf,
  onOpenCatalog
}: DependencyMapProps) {
  const currentPreset = PRESETS[activePresetId] || PRESETS['k8s-core'];
  const downstreamGraph = currentPreset.downstreamGraph;
  const positions = currentPreset.layoutPositions;
  const rawPresetEdges = currentPreset.rawEdges;

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
          _isDimmed: isDimmed
        } as Record<string, any>,
        style: isDimmed ? { opacity: 0.28, transition: 'opacity 0.25s ease' } : { transition: 'opacity 0.25s ease' }
      };
    });
  }, [services, whatIfNode, whatIfDownstream, positions]);

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

      // High-visibility base styling
      let strokeColor = '#047857'; // deep emerald for crystal-clear healthy flow
      let strokeWidth = 2.6;
      let isAnimated = true;
      let edgeClass = 'edge-healthy';
      let markerSize = 16;
      let displayLabel = (edge as any).label || 'DEPENDENCY';
      let labelTextColor = '#334155';
      let labelBgColor = '#ffffff';
      let labelBorderColor = '#cbd5e1';

      if (isWhatIfEdge) {
        strokeColor = '#0284c7'; // electric cyan
        strokeWidth = 4.0;
        isAnimated = true;
        edgeClass = 'edge-what-if';
        markerSize = 20;
        displayLabel = '⚡ BLAST RADIUS';
        labelTextColor = '#0369a1';
        labelBgColor = '#f0f9ff';
        labelBorderColor = '#38bdf8';
      } else if (isSourceRoot) {
        // High-energy Crimson failure shockwave bursting from root cause
        strokeColor = '#ef4444'; // intense crimson
        strokeWidth = 5.2;
        isAnimated = true;
        edgeClass = 'edge-root-cascade';
        markerSize = 24;
        displayLabel = '💥 BLAST WAVE (SATURATED)';
        labelTextColor = '#991b1b';
        labelBgColor = '#fef2f2';
        labelBorderColor = '#ef4444';
      } else if (isSourceImpacted) {
        // Glowing Amber cascading degradation propagating downstream
        strokeColor = '#f59e0b'; // amber-500
        strokeWidth = 3.8;
        isAnimated = true;
        edgeClass = 'edge-impact-cascade';
        markerSize = 20;
        displayLabel = '⚠️ CASCADE DEGRADED';
        labelTextColor = '#92400e';
        labelBgColor = '#fffbeb';
        labelBorderColor = '#f59e0b';
      } else if (isTargetFailed) {
        // Upstream link under backpressure from degraded target
        strokeColor = '#ea580c'; // orange-500
        strokeWidth = 3.2;
        isAnimated = true;
        edgeClass = 'edge-impact-cascade';
        markerSize = 18;
        displayLabel = '⚠️ BACKPRESSURE';
        labelTextColor = '#9a3412';
        labelBgColor = '#fff7ed';
        labelBorderColor = '#ea580c';
      } else if (srcStatus === 'healthy' && tgtStatus === 'healthy') {
        strokeColor = '#059669'; // emerald-600
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
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-stone-200/90 bg-[#faf8f5] shadow-sm min-h-[720px]">
      {/* Top Header Overlay */}
      <div className="absolute top-3.5 left-4 z-10 pointer-events-none flex items-center gap-2.5 flex-wrap">
        <div className="bg-white/95 backdrop-blur-sm px-3.5 py-1.5 rounded-lg border border-stone-200 shadow-xs flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-[11px] font-bold text-stone-900 tracking-wider font-mono uppercase">
            {currentPreset.name}
          </span>
          <span className="text-[9px] font-bold text-stone-700 bg-stone-100 px-2 py-0.5 rounded border border-stone-200 font-mono">
            {currentPreset.nodeCount} NODES • {currentPreset.tierCount} TIERS
          </span>
        </div>

        {activeScenario && (
          <div className="bg-rose-50 px-2.5 py-1 rounded-lg border border-rose-200 text-[10px] font-mono text-rose-800 font-semibold flex items-center gap-1.5 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
            CASCADE ACTIVE
          </div>
        )}
      </div>

      {/* Floating What-If Analysis HUD */}
      {whatIfNode && (
        <div className="absolute top-14 left-4 right-4 z-20 bg-sky-50/95 backdrop-blur-sm border-2 border-sky-300 rounded-xl p-2.5 px-3.5 flex items-center justify-between shadow-md font-mono text-xs text-sky-950 animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-sky-600 text-white flex items-center justify-center font-bold text-[10px] shadow-xs">
              ?
            </div>
            <div>
              <span className="font-bold text-sky-900 block text-[11px]">
                WHAT-IF SIMULATION: IF <code className="bg-white px-1.5 py-0.5 rounded border border-sky-300 font-bold text-sky-900 uppercase">{whatIfNode}</code> FAILS
              </span>
              <span className="text-[10px] text-sky-700 font-sans">
                Hypothetical Blast Radius: <strong>{whatIfDownstream.size}</strong> downstream services impacted ({whatIfPercentage}% of dependent topology).
              </span>
            </div>
          </div>

          <button
            onClick={() => onSelectWhatIf && onSelectWhatIf(null)}
            className="text-[10px] font-bold text-sky-800 bg-white hover:bg-sky-100 px-2.5 py-1 rounded-md border border-sky-300 flex items-center gap-1 transition-colors shadow-2xs"
          >
            <X size={12} />
            <span>EXIT WHAT-IF</span>
          </button>
        </div>
      )}

      {/* Legend & What-If Prompt */}
      <div className="absolute bottom-3.5 left-4 z-10 pointer-events-none bg-white/95 backdrop-blur-sm px-3.5 py-2 rounded-lg border border-stone-200 shadow-xs flex items-center gap-3.5 text-[10px] font-mono text-stone-600 flex-wrap">
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
        <div className="flex items-center gap-1.5 text-stone-400 pl-1 border-l border-stone-200">
          <span>Click any node for What-If blast radius</span>
        </div>
      </div>

      <ReactFlow
        key={activePresetId}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.14 }}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
        minZoom={0.2}
        maxZoom={1.6}
      >
        <Background color="#e2ded7" gap={24} size={1.2} />
        <Controls className="!bg-white !border-stone-200 !fill-stone-600 !shadow-xs" />
      </ReactFlow>
    </div>
  );
}
