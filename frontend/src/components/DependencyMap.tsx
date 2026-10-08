// D:\CoffeeOverflow\Agnitia\frontend\src\components\DependencyMap.tsx - Vertical Causal DAG + Interactive What-If Mode
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
import { X, HelpCircle, AlertTriangle } from 'lucide-react';

const nodeTypes = {
  serviceNode: ServiceNode
};

// Causal Waterfall Layout:
// Tier 1 (Top / Root Sources): PostgreSQL & Redis
// Tier 2 (Backend Services): Auth & Payment
// Tier 3 (Edge Routing): API Gateway
// Tier 4 (Bottom / End User): Web Storefront
const VERTICAL_POSITIONS: Record<string, { x: number; y: number }> = {
  'redis': { x: 50, y: 30 },
  'postgres': { x: 410, y: 30 },
  'auth-service': { x: 50, y: 230 },
  'payment-service': { x: 410, y: 230 },
  'api-gateway': { x: 230, y: 430 },
  'web-ui': { x: 230, y: 630 }
};

// Adjacency mapping for downstream blast radius calculation
const DOWNSTREAM_GRAPH: Record<string, string[]> = {
  'postgres': ['auth-service', 'payment-service'],
  'redis': ['auth-service'],
  'auth-service': ['api-gateway'],
  'payment-service': ['api-gateway'],
  'api-gateway': ['web-ui'],
  'web-ui': []
};

// Calculates full reachable blast radius for a given root node
function getReachableDownstream(startNode: string): Set<string> {
  const visited = new Set<string>();
  const queue = [startNode];

  while (queue.length > 0) {
    const current = queue.shift()!;
    const neighbors = DOWNSTREAM_GRAPH[current] || [];
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
  activeScenario?: string | null;
  whatIfNode?: string | null;
  onSelectWhatIf?: (nodeId: string | null) => void;
}

export default function DependencyMap({
  services,
  activeScenario,
  whatIfNode,
  onSelectWhatIf
}: DependencyMapProps) {
  // Downstream set when what-if is active
  const whatIfDownstream = useMemo(() => {
    if (!whatIfNode) return new Set<string>();
    return getReachableDownstream(whatIfNode);
  }, [whatIfNode]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    if (onSelectWhatIf) {
      if (whatIfNode === node.id) {
        onSelectWhatIf(null); // Deselect on repeat click
      } else {
        onSelectWhatIf(node.id);
      }
    }
  }, [whatIfNode, onSelectWhatIf]);

  const nodes = useMemo<Node[]>(() => {
    return Object.values(services).map((srv: any) => {
      const isWhatIfOrigin = whatIfNode === srv.id;
      const isWhatIfImpacted = whatIfDownstream.has(srv.id);
      const isDimmed = !!whatIfNode && !isWhatIfOrigin && !isWhatIfImpacted;

      return {
        id: srv.id,
        type: 'serviceNode',
        position: VERTICAL_POSITIONS[srv.id] || { x: 200, y: 200 },
        data: {
          ...srv,
          _whatIfOrigin: isWhatIfOrigin,
          _whatIfImpacted: isWhatIfImpacted,
          _isDimmed: isDimmed
        } as Record<string, any>,
        style: isDimmed ? { opacity: 0.38, transition: 'opacity 0.25s ease' } : { transition: 'opacity 0.25s ease' }
      };
    });
  }, [services, whatIfNode, whatIfDownstream]);

  const edges = useMemo<Edge[]>(() => {
    const rawEdges = [
      { id: 'e-redis-auth', source: 'redis', target: 'auth-service' },
      { id: 'e-pg-auth', source: 'postgres', target: 'auth-service' },
      { id: 'e-pg-pay', source: 'postgres', target: 'payment-service' },
      { id: 'e-auth-gw', source: 'auth-service', target: 'api-gateway' },
      { id: 'e-pay-gw', source: 'payment-service', target: 'api-gateway' },
      { id: 'e-gw-web', source: 'api-gateway', target: 'web-ui' }
    ];

    return rawEdges.map((edge) => {
      const srcStatus = services[edge.source]?.status;
      const tgtStatus = services[edge.target]?.status;

      const isRootImpact = srcStatus === 'root_cause' || tgtStatus === 'root_cause';
      const isVictimImpact = srcStatus === 'impacted' || tgtStatus === 'impacted';

      // What-If path highlighting
      const isWhatIfEdge = !!whatIfNode && (
        (edge.source === whatIfNode && whatIfDownstream.has(edge.target)) ||
        (whatIfDownstream.has(edge.source) && whatIfDownstream.has(edge.target))
      );

      let strokeColor = '#94a3b8'; // slate-400
      let strokeWidth = 1.8;
      let isAnimated = false;

      if (isWhatIfEdge) {
        strokeColor = '#0284c7'; // sky-600
        strokeWidth = 2.6;
        isAnimated = true;
      } else if (isRootImpact) {
        strokeColor = '#e11d48'; // rose-600
        strokeWidth = 2.5;
        isAnimated = true;
      } else if (isVictimImpact) {
        strokeColor = '#d97706'; // amber-600
        strokeWidth = 2;
        isAnimated = true;
      } else if (srcStatus === 'healthy' && tgtStatus === 'healthy') {
        strokeColor = '#10b981'; // emerald-500
        strokeWidth = 1.6;
      }

      return {
        ...edge,
        type: 'smoothstep',
        animated: isAnimated,
        pathOptions: {
          borderRadius: 14
        },
        style: {
          stroke: strokeColor,
          strokeWidth,
          opacity: (whatIfNode && !isWhatIfEdge && edge.source !== whatIfNode) ? 0.35 : 1,
          transition: 'stroke 0.3s ease, stroke-width 0.3s ease, opacity 0.3s ease'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 12,
          height: 12
        }
      };
    });
  }, [services, whatIfNode, whatIfDownstream]);

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-stone-200/90 bg-[#faf8f5] shadow-sm">
      {/* Top Header Overlay */}
      <div className="absolute top-3.5 left-4 z-10 pointer-events-none flex items-center gap-2.5 flex-wrap">
        <div className="bg-white/95 backdrop-blur-sm px-3.5 py-1.5 rounded-lg border border-stone-200 shadow-xs flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-[11px] font-bold text-stone-800 tracking-wider font-mono uppercase">
            Causal Blast Radius Flow
          </span>
          <span className="text-[10px] text-stone-400 font-mono">
            Root (Top) &rarr; Consumers (Bottom)
          </span>
        </div>

        {activeScenario && (
          <div className="bg-rose-50 px-2.5 py-1 rounded-lg border border-rose-200 text-[10px] font-mono text-rose-800 font-semibold flex items-center gap-1.5 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
            DOWNSTREAM CASCADE ACTIVE
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
                Hypothetical Blast Radius: <strong>{whatIfDownstream.size}</strong> downstream services impacted ({Math.round((whatIfDownstream.size / 5) * 100)}% cluster traffic impact).
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
      <div className="absolute bottom-3.5 left-4 z-10 pointer-events-none bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-stone-200 shadow-xs flex items-center gap-3.5 text-[10px] font-mono text-stone-600 flex-wrap">
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
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.4}
        maxZoom={1.5}
      >
        <Background color="#e2ded7" gap={22} size={1.2} />
        <Controls className="!bg-white !border-stone-200 !fill-stone-600 !shadow-xs" />
      </ReactFlow>
    </div>
  );
}
