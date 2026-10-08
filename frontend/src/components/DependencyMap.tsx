// D:\CoffeeOverflow\Agnitia\frontend\src\components\DependencyMap.tsx - Root-Cause Waterfall Flow (Database -> UI)
import React, { useMemo } from 'react';
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

const nodeTypes = {
  serviceNode: ServiceNode
};

// Causal Waterfall Layout:
// Tier 1 (Top / Root Sources): PostgreSQL & Redis
// Tier 2 (Backend Services): Auth & Payment
// Tier 3 (Edge Routing): API Gateway
// Tier 4 (Bottom / End User): Web Storefront
const VERTICAL_POSITIONS: Record<string, { x: number; y: number }> = {
  "redis": { x: 50, y: 30 },
  "postgres": { x: 410, y: 30 },
  "auth-service": { x: 50, y: 230 },
  "payment-service": { x: 410, y: 230 },
  "api-gateway": { x: 230, y: 430 },
  "web-ui": { x: 230, y: 630 }
};

interface DependencyMapProps {
  services: Record<string, any>;
  activeScenario?: string | null;
}

export default function DependencyMap({ services, activeScenario }: DependencyMapProps) {
  const nodes = useMemo<Node[]>(() => {
    return Object.values(services).map((srv: any) => ({
      id: srv.id,
      type: 'serviceNode',
      position: VERTICAL_POSITIONS[srv.id] || { x: 200, y: 200 },
      data: srv as Record<string, any>
    }));
  }, [services]);

  const edges = useMemo<Edge[]>(() => {
    // Causal Cascade Flow: Failures & data flow downward from Database/Cache -> Services -> Gateway -> UI
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

      let strokeColor = '#94a3b8'; // slate-400
      let strokeWidth = 1.8;
      let isAnimated = false;

      if (isRootImpact) {
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
          transition: 'stroke 0.3s ease, stroke-width 0.3s ease'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 12,
          height: 12
        }
      };
    });
  }, [services]);

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-stone-200/90 bg-[#faf8f5] shadow-sm">
      {/* Header Overlay */}
      <div className="absolute top-3.5 left-4 z-10 pointer-events-none flex items-center gap-2.5">
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

      {/* Legend Overlay */}
      <div className="absolute bottom-3.5 left-4 z-10 pointer-events-none bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-stone-200 shadow-xs flex items-center gap-3.5 text-[10px] font-mono text-stone-600">
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
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-sky-500" />
          <span>Recovering</span>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
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
