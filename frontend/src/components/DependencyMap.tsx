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

      const isRootImpact = srcStatus === 'root_cause' || tgtStatus === 'root_cause';
      const isVictimImpact = srcStatus === 'impacted' || tgtStatus === 'impacted';

      const isWhatIfEdge =
        !!whatIfNode &&
        ((edge.source === whatIfNode && whatIfDownstream.has(edge.target)) ||
          (whatIfDownstream.has(edge.source) && whatIfDownstream.has(edge.target)));

      let strokeColor = '#94a3b8'; // slate-400
      let strokeWidth = 2.0;
      let isAnimated = false;

      if (isWhatIfEdge) {
        strokeColor = '#0284c7'; // sky-600
        strokeWidth = 2.8;
        isAnimated = true;
      } else if (isRootImpact) {
        strokeColor = '#e11d48'; // rose-600
        strokeWidth = 2.8;
        isAnimated = true;
      } else if (isVictimImpact) {
        strokeColor = '#d97706'; // amber-600
        strokeWidth = 2.2;
        isAnimated = true;
      } else if (srcStatus === 'healthy' && tgtStatus === 'healthy') {
        strokeColor = '#10b981'; // emerald-500
        strokeWidth = 1.8;
      }

      return {
        ...edge,
        type: 'straight', // Clean Euclidean vectors with 0 bends
        animated: isAnimated,
        style: {
          stroke: strokeColor,
          strokeWidth,
          opacity: whatIfNode && !isWhatIfEdge && edge.source !== whatIfNode ? 0.25 : 1,
          transition: 'stroke 0.3s ease, stroke-width 0.3s ease, opacity 0.3s ease'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 14,
          height: 14
        }
      };
    });
  }, [services, whatIfNode, whatIfDownstream, rawPresetEdges]);

  const totalOtherNodes = Math.max(currentPreset.nodeCount - 1, 1);
  const whatIfPercentage = Math.round((whatIfDownstream.size / totalOtherNodes) * 100);

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-stone-200/90 bg-[#faf8f5] shadow-sm min-h-[720px]">
      {/* Top Header Overlay */}
      <div className="absolute top-3.5 left-4 z-10 pointer-events-auto flex items-center gap-2.5 flex-wrap">
        <div className="bg-white/95 backdrop-blur-sm px-3.5 py-1.5 rounded-lg border border-stone-200 shadow-xs flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-[11px] font-bold text-stone-900 tracking-wider font-mono uppercase">
            {currentPreset.name}
          </span>
          <span className="text-[9px] font-bold text-stone-700 bg-stone-100 px-2 py-0.5 rounded border border-stone-200 font-mono">
            {currentPreset.nodeCount} NODES • {currentPreset.tierCount} TIERS
          </span>
        </div>

        {/* Quick Preset Selector Toggle */}
        <div className="bg-white/95 backdrop-blur-sm p-1 rounded-lg border border-stone-200 shadow-xs flex items-center gap-1 font-mono text-[10px]">
          <button
            onClick={() => setActivePreset('k8s-core')}
            className={`px-2 py-1 rounded font-bold transition-all ${
              activePresetId === 'k8s-core'
                ? 'bg-stone-900 text-white shadow-2xs'
                : 'text-stone-600 hover:bg-stone-100'
            }`}
          >
            K8s Core (6)
          </button>
          <button
            onClick={() => setActivePreset('amazon-scale')}
            className={`px-2 py-1 rounded font-bold transition-all flex items-center gap-1 ${
              activePresetId === 'amazon-scale'
                ? 'bg-amber-600 text-white shadow-2xs'
                : 'text-stone-600 hover:bg-stone-100'
            }`}
          >
            <Sparkles size={11} />
            Amazon (20)
          </button>
          {onOpenCatalog && (
            <button
              onClick={onOpenCatalog}
              title="Open full microservices catalog"
              className="px-2 py-1 rounded text-stone-500 hover:text-stone-800 hover:bg-stone-100 border-l border-stone-200 ml-1 flex items-center gap-1"
            >
              <Layers size={11} />
              <span>Catalog</span>
            </button>
          )}
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
          <span>Healthy</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-rose-500" />
          <span>Root Cause</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span>Cascading Victim</span>
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
        fitViewOptions={{ padding: 0.12 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.25}
        maxZoom={1.5}
      >
        <Background color="#e2ded7" gap={24} size={1.2} />
        <Controls className="!bg-white !border-stone-200 !fill-stone-600 !shadow-xs" />
      </ReactFlow>
    </div>
  );
}
