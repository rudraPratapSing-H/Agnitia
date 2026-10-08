// frontend/src/components/DependencyMap.jsx - Interactive React Flow Topology Graph
import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import ServiceNode from './ServiceNode';

const nodeTypes = {
  serviceNode: ServiceNode
};

// Fixed Left-to-Right Topology layout coordinates
const NODE_POSITIONS = {
  postgres: { x: 40, y: 70 },
  redis: { x: 40, y: 290 },
  "auth-service": { x: 330, y: 90 },
  "payment-service": { x: 330, y: 280 },
  "api-gateway": { x: 620, y: 180 },
  "web-ui": { x: 910, y: 180 }
};

export default function DependencyMap({ services, activeScenario }) {
  // Convert services dictionary to React Flow nodes
  const nodes = useMemo(() => {
    return Object.values(services).map((srv: any) => ({
      id: srv.id,
      type: 'serviceNode',
      position: NODE_POSITIONS[srv.id] || { x: 100, y: 100 },
      data: srv as Record<string, any>
    }));
  }, [services]);

  // Generate dynamic edges with animated blast-radius styling
  const edges = useMemo(() => {
    const rawEdges = [
      { id: 'e-pg-auth', source: 'postgres', target: 'auth-service' },
      { id: 'e-pg-pay', source: 'postgres', target: 'payment-service' },
      { id: 'e-redis-auth', source: 'redis', target: 'auth-service' },
      { id: 'e-auth-gw', source: 'auth-service', target: 'api-gateway' },
      { id: 'e-pay-gw', source: 'payment-service', target: 'api-gateway' },
      { id: 'e-gw-web', source: 'api-gateway', target: 'web-ui' }
    ];

    return rawEdges.map((edge) => {
      const srcStatus = services[edge.source]?.status;
      const tgtStatus = services[edge.target]?.status;

      const isRootImpact = srcStatus === 'root_cause' || tgtStatus === 'root_cause';
      const isVictimImpact = srcStatus === 'impacted' || tgtStatus === 'impacted';

      let strokeColor = '#3f3f46'; // zinc-700
      let strokeWidth = 2;
      let isAnimated = false;

      if (isRootImpact) {
        strokeColor = '#ef4444'; // red-500
        strokeWidth = 3;
        isAnimated = true;
      } else if (isVictimImpact) {
        strokeColor = '#f59e0b'; // amber-500
        strokeWidth = 2.5;
        isAnimated = true;
      } else if (srcStatus === 'healthy' && tgtStatus === 'healthy') {
        strokeColor = '#10b981'; // emerald-500
        strokeWidth = 1.8;
      }

      return {
        ...edge,
        animated: isAnimated,
        style: {
          stroke: strokeColor,
          strokeWidth,
          transition: 'stroke 0.4s ease, stroke-width 0.4s ease'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 14,
          height: 14
        }
      };
    });
  }, [services]);

  return (
    <div className="w-full h-full relative rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-950/70 shadow-2xl">
      {/* Topology Header Overlay */}
      <div className="absolute top-3 left-4 z-10 pointer-events-none flex items-center gap-3">
        <div className="bg-zinc-900/90 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-zinc-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-xs font-semibold text-zinc-200 uppercase tracking-wider font-mono">
            LIVE TOPOLOGY (DAG)
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">
            {Object.keys(services).length} NODES · 6 EDGES
          </span>
        </div>

        {activeScenario && (
          <div className="bg-red-950/80 backdrop-blur-md px-3 py-1 rounded-lg border border-red-800/80 text-[11px] font-mono text-red-300 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
            BLAST RADIUS ACTIVE
          </div>
        )}
      </div>

      {/* Legend Overlay */}
      <div className="absolute bottom-3 left-4 z-10 pointer-events-none bg-zinc-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-zinc-800 flex items-center gap-4 text-[10px] font-mono text-zinc-400">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span>Healthy</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_8px_#ef4444]" />
          <span>Root Cause</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
          <span>Cascading Victim</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
          <span>Recovering</span>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.5}
        maxZoom={1.5}
      >
        <Background color="#27272a" gap={20} size={1} />
        <Controls className="!bg-zinc-900 !border-zinc-800 !fill-zinc-300" />
      </ReactFlow>
    </div>
  );
}
