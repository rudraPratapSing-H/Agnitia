// frontend/src/presets.ts - Multi-Architecture Preset Registry
// Supports both Standard K8s Cluster (6 nodes) and Amazon Hyperscale Architecture (20 nodes)
import { ServiceNode } from './types';

export type PresetId = 'k8s-core' | 'amazon-scale';

export interface PresetServiceMeta {
  role: string;
  resilience: string;
  avgThroughput: string;
  p99Latency: string;
}

export interface ArchitecturePreset {
  id: PresetId;
  name: string;
  shortName: string;
  tagline: string;
  description: string;
  badge: string;
  nodeCount: number;
  tierCount: number;
  workloadType: string;
  avgThroughput: string;
  clusterType: string;
  initialServices: Record<string, ServiceNode>;
  serviceMeta: Record<string, PresetServiceMeta>;
  layoutPositions: Record<string, { x: number; y: number }>;
  rawEdges: Array<{ id: string; source: string; target: string }>;
  downstreamGraph: Record<string, string[]>;
  alertBadgeCounts: {
    db_oom: string;
    bad_config: string;
    cpu_spike: string;
    slow_leak: string;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// PRESET 1: STANDARD KUBERNETES CLUSTER (6 NODES)
// ─────────────────────────────────────────────────────────────────────────────
export const K8S_CORE_PRESET: ArchitecturePreset = {
  id: 'k8s-core',
  name: 'Standard K8s Microservices',
  shortName: 'K8s Core (6)',
  tagline: 'Standard 6-node enterprise Kubernetes application cluster',
  description:
    'A reference microservices architecture featuring stateless API services, dedicated relational and cache layers, and edge ingress routing.',
  badge: 'CORE REFERENCE',
  nodeCount: 6,
  tierCount: 4,
  workloadType: 'Containerized E-Commerce',
  avgThroughput: '1,250 req/sec',
  clusterType: 'EKS / Vanilla k8s v1.28',
  alertBadgeCounts: {
    db_oom: '56 ALERTS',
    bad_config: 'CRASH LOOP',
    cpu_spike: 'AUTOSCALE',
    slow_leak: 'PREDICTIVE'
  },
  initialServices: {
    postgres: {
      id: 'postgres',
      label: 'PostgreSQL 16',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 42, mem_limit_mb: 64, cpu_pct: 12, restarts: 0 }
    },
    redis: {
      id: 'redis',
      label: 'Redis Cache',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 18, mem_limit_mb: 128, cpu_pct: 4, restarts: 0 }
    },
    'auth-service': {
      id: 'auth-service',
      label: 'Auth Service',
      tier: 'backend',
      depends_on: ['postgres', 'redis'],
      status: 'healthy',
      metrics: { mem_mb: 38, mem_limit_mb: 128, cpu_pct: 8, restarts: 0 }
    },
    'payment-service': {
      id: 'payment-service',
      label: 'Payment Service',
      tier: 'backend',
      depends_on: ['postgres'],
      status: 'healthy',
      metrics: { mem_mb: 64, mem_limit_mb: 256, cpu_pct: 11, restarts: 0 }
    },
    'api-gateway': {
      id: 'api-gateway',
      label: 'Kong API Gateway',
      tier: 'edge',
      depends_on: ['auth-service', 'payment-service'],
      status: 'healthy',
      metrics: { mem_mb: 92, mem_limit_mb: 256, cpu_pct: 21, restarts: 0 }
    },
    'web-ui': {
      id: 'web-ui',
      label: 'Web Storefront',
      tier: 'frontend',
      depends_on: ['api-gateway'],
      status: 'healthy',
      metrics: { mem_mb: 55, mem_limit_mb: 128, cpu_pct: 15, restarts: 0 }
    }
  },
  serviceMeta: {
    postgres: {
      role: 'Primary relational ACID store for orders and identity credentials',
      resilience: 'Single replica with PersistentVolumeClaim (PVC)',
      avgThroughput: '480 QPS',
      p99Latency: '4.2 ms'
    },
    redis: {
      role: 'In-memory caching for auth tokens and fast session lookup',
      resilience: 'Standalone in-memory instance with AOF persistence',
      avgThroughput: '1,200 QPS',
      p99Latency: '0.8 ms'
    },
    'auth-service': {
      role: 'JWT token issuance, OAuth2 provider integration, and user authorization',
      resilience: 'Deployment with 1 replica, HPA configured (1-5 pods)',
      avgThroughput: '350 req/s',
      p99Latency: '14 ms'
    },
    'payment-service': {
      role: 'Payment processing gateway and checkout ledger management',
      resilience: 'Deployment with 1 replica, idempotency key checks',
      avgThroughput: '120 req/s',
      p99Latency: '45 ms'
    },
    'api-gateway': {
      role: 'Layer 7 reverse proxy, route routing, throttling, and TLS termination',
      resilience: 'DaemonSet across worker nodes with Envoy core',
      avgThroughput: '1,250 req/s',
      p99Latency: '8 ms'
    },
    'web-ui': {
      role: 'Next.js SSR storefront serving retail customer browser sessions',
      resilience: 'Multi-pod deployment behind cluster ingress',
      avgThroughput: '980 req/s',
      p99Latency: '24 ms'
    }
  },
  layoutPositions: {
    redis: { x: 80, y: 50 },
    postgres: { x: 440, y: 50 },
    'auth-service': { x: 80, y: 290 },
    'payment-service': { x: 440, y: 290 },
    'api-gateway': { x: 260, y: 530 },
    'web-ui': { x: 260, y: 770 }
  },
  rawEdges: [
    { id: 'e-redis-auth', source: 'redis', target: 'auth-service' },
    { id: 'e-pg-auth', source: 'postgres', target: 'auth-service' },
    { id: 'e-pg-pay', source: 'postgres', target: 'payment-service' },
    { id: 'e-auth-gw', source: 'auth-service', target: 'api-gateway' },
    { id: 'e-pay-gw', source: 'payment-service', target: 'api-gateway' },
    { id: 'e-gw-web', source: 'api-gateway', target: 'web-ui' }
  ],
  downstreamGraph: {
    postgres: ['auth-service', 'payment-service'],
    redis: ['auth-service'],
    'auth-service': ['api-gateway'],
    'payment-service': ['api-gateway'],
    'api-gateway': ['web-ui'],
    'web-ui': []
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// PRESET 2: AMAZON HYPERSCALE ARCHITECTURE (20 NODES)
// ─────────────────────────────────────────────────────────────────────────────
export const AMAZON_SCALE_PRESET: ArchitecturePreset = {
  id: 'amazon-scale',
  name: 'Amazon Hyperscale Architecture',
  shortName: 'Amazon (20)',
  tagline: 'Production-grade 20-node AWS distributed retail topology',
  description:
    'Simulates Amazon’s distributed e-commerce architecture across 6 tiers: Multi-AZ Aurora DBs, DynamoDB, OpenSearch, SQS message bus, domain microservices, and CloudFront edge CDN.',
  badge: 'AWS HYPERSCALE',
  nodeCount: 20,
  tierCount: 6,
  workloadType: 'Hyperscale Distributed Microservices',
  avgThroughput: '84,500 req/sec',
  clusterType: 'Multi-AZ AWS EKS + Managed AWS Native',
  alertBadgeCounts: {
    db_oom: '84 ALERTS',
    bad_config: 'CRASH LOOP',
    cpu_spike: 'AUTOSCALE',
    slow_leak: 'PREDICTIVE'
  },
  initialServices: {
    // ── Tier 1: Data Persistence ───────────────────────────────────────────
    'aurora-orders-db': {
      id: 'aurora-orders-db',
      label: 'Aurora PostgreSQL',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 3420, mem_limit_mb: 4096, cpu_pct: 18, restarts: 0 }
    },
    'dynamodb-cart': {
      id: 'dynamodb-cart',
      label: 'DynamoDB Cart Store',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 210, mem_limit_mb: 512, cpu_pct: 9, restarts: 0 }
    },
    'redis-cache': {
      id: 'redis-cache',
      label: 'ElastiCache Redis',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 1420, mem_limit_mb: 2048, cpu_pct: 14, restarts: 0 }
    },
    'opensearch-cluster': {
      id: 'opensearch-cluster',
      label: 'OpenSearch Cluster',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 2840, mem_limit_mb: 4096, cpu_pct: 22, restarts: 0 }
    },
    'warehouse-db': {
      id: 'warehouse-db',
      label: 'Warehouse MySQL',
      tier: 'data',
      depends_on: [],
      status: 'healthy',
      metrics: { mem_mb: 1180, mem_limit_mb: 2048, cpu_pct: 12, restarts: 0 }
    },

    // ── Tier 2: Core Domain Services (Direct DB Consumers) ─────────────────
    'payment-service': {
      id: 'payment-service',
      label: 'Amazon Pay Gateway',
      tier: 'backend',
      depends_on: ['aurora-orders-db'],
      status: 'healthy',
      metrics: { mem_mb: 340, mem_limit_mb: 1024, cpu_pct: 15, restarts: 0 }
    },
    'cart-service': {
      id: 'cart-service',
      label: 'Cart & Checkout',
      tier: 'backend',
      depends_on: ['dynamodb-cart', 'product-catalog'],
      status: 'healthy',
      metrics: { mem_mb: 320, mem_limit_mb: 512, cpu_pct: 18, restarts: 0 }
    },
    'product-catalog': {
      id: 'product-catalog',
      label: 'Product Catalog',
      tier: 'backend',
      depends_on: ['redis-cache'],
      status: 'healthy',
      metrics: { mem_mb: 410, mem_limit_mb: 1024, cpu_pct: 19, restarts: 0 }
    },
    'search-service': {
      id: 'search-service',
      label: 'Search & Discovery',
      tier: 'backend',
      depends_on: ['opensearch-cluster'],
      status: 'healthy',
      metrics: { mem_mb: 560, mem_limit_mb: 1024, cpu_pct: 26, restarts: 0 }
    },
    'inventory-service': {
      id: 'inventory-service',
      label: 'Inventory Allocation',
      tier: 'backend',
      depends_on: ['warehouse-db'],
      status: 'healthy',
      metrics: { mem_mb: 290, mem_limit_mb: 512, cpu_pct: 11, restarts: 0 }
    },

    // ── Tier 3: Domain Orchestration & Async Queues ────────────────────────
    'order-service': {
      id: 'order-service',
      label: 'Order Orchestrator',
      tier: 'backend',
      depends_on: ['aurora-orders-db', 'payment-service', 'inventory-service'],
      status: 'healthy',
      metrics: { mem_mb: 480, mem_limit_mb: 1024, cpu_pct: 24, restarts: 0 }
    },
    'auth-service': {
      id: 'auth-service',
      label: 'Cognito / IAM Auth',
      tier: 'backend',
      depends_on: ['redis-cache'],
      status: 'healthy',
      metrics: { mem_mb: 260, mem_limit_mb: 512, cpu_pct: 16, restarts: 0 }
    },
    'recommendation-engine': {
      id: 'recommendation-engine',
      label: 'Personalization AI',
      tier: 'backend',
      depends_on: ['redis-cache'],
      status: 'healthy',
      metrics: { mem_mb: 880, mem_limit_mb: 2048, cpu_pct: 34, restarts: 0 }
    },
    'sqs-event-bus': {
      id: 'sqs-event-bus',
      label: 'SQS / EventBridge Bus',
      tier: 'backend',
      depends_on: ['order-service'],
      status: 'healthy',
      metrics: { mem_mb: 195, mem_limit_mb: 512, cpu_pct: 8, restarts: 0 }
    },
    'notification-service': {
      id: 'notification-service',
      label: 'SNS / SES Notifier',
      tier: 'backend',
      depends_on: ['sqs-event-bus'],
      status: 'healthy',
      metrics: { mem_mb: 180, mem_limit_mb: 512, cpu_pct: 6, restarts: 0 }
    },

    // ── Tier 4: Fulfillment & Gateway Hub ──────────────────────────────────
    'shipping-service': {
      id: 'shipping-service',
      label: 'Logistics & Shipping',
      tier: 'backend',
      depends_on: ['sqs-event-bus'],
      status: 'healthy',
      metrics: { mem_mb: 210, mem_limit_mb: 512, cpu_pct: 7, restarts: 0 }
    },
    'api-gateway': {
      id: 'api-gateway',
      label: 'Amazon API Gateway',
      tier: 'edge',
      depends_on: ['auth-service', 'order-service', 'cart-service', 'product-catalog'],
      status: 'healthy',
      metrics: { mem_mb: 620, mem_limit_mb: 1024, cpu_pct: 31, restarts: 0 }
    },

    // ── Tier 5: Client Storefronts & BFF ───────────────────────────────────
    'web-storefront': {
      id: 'web-storefront',
      label: 'Storefront Web UI',
      tier: 'frontend',
      depends_on: ['api-gateway', 'search-service', 'recommendation-engine'],
      status: 'healthy',
      metrics: { mem_mb: 420, mem_limit_mb: 1024, cpu_pct: 22, restarts: 0 }
    },
    'mobile-bff': {
      id: 'mobile-bff',
      label: 'Mobile App BFF',
      tier: 'frontend',
      depends_on: ['api-gateway', 'search-service'],
      status: 'healthy',
      metrics: { mem_mb: 380, mem_limit_mb: 1024, cpu_pct: 19, restarts: 0 }
    },

    // ── Tier 6: Edge CDN & WAF ─────────────────────────────────────────────
    'cloud-front': {
      id: 'cloud-front',
      label: 'CloudFront CDN & WAF',
      tier: 'edge',
      depends_on: ['web-storefront', 'mobile-bff'],
      status: 'healthy',
      metrics: { mem_mb: 190, mem_limit_mb: 512, cpu_pct: 14, restarts: 0 }
    }
  },
  serviceMeta: {
    'aurora-orders-db': {
      role: 'Multi-AZ ACID relational ledger for checkouts, ledger records & payment settlements',
      resilience: 'Aurora Multi-AZ with read replica auto-failover (< 30s)',
      avgThroughput: '14,200 write QPS',
      p99Latency: '2.1 ms'
    },
    'dynamodb-cart': {
      role: 'Serverless low-latency Key-Value store holding active customer carts and session locks',
      resilience: 'Global Tables active-active multi-region replication',
      avgThroughput: '28,000 WCU / 45,000 RCU',
      p99Latency: '1.2 ms'
    },
    'redis-cache': {
      role: 'ElastiCache cluster caching hot product SKUs, auth tokens, and search facets',
      resilience: 'Multi-AZ cluster with automatic failover and Redis 7.2 engine',
      avgThroughput: '64,000 ops/s',
      p99Latency: '0.4 ms'
    },
    'opensearch-cluster': {
      role: 'Distributed search engine indexing 45M+ product listings with faceted search',
      resilience: '3 Master dedicated nodes, 6 Data nodes across 3 AZs',
      avgThroughput: '8,500 queries/s',
      p99Latency: '11.5 ms'
    },
    'warehouse-db': {
      role: 'Fulfillment center and warehouse inventory physical bin allocation store',
      resilience: 'RDS MySQL Multi-AZ with synchronous standby',
      avgThroughput: '3,800 QPS',
      p99Latency: '3.8 ms'
    },
    'payment-service': {
      role: '1-Click checkout, credit card billing, Amazon Pay and fraud risk scoring',
      resilience: 'Stateless HPA (4-16 pods) with circuit breakers for payment acquirers',
      avgThroughput: '4,200 tps',
      p99Latency: '68 ms'
    },
    'cart-service': {
      role: 'Real-time cart manipulations, promotions, coupon calculations & tax estimation',
      resilience: 'HPA auto-scaling with local memoization cache',
      avgThroughput: '18,500 req/s',
      p99Latency: '8.4 ms'
    },
    'product-catalog': {
      role: 'Master SKU hierarchy, product variants, price calculation, and seller metadata',
      resilience: 'HPA auto-scaling with read-through ElastiCache pattern',
      avgThroughput: '32,000 req/s',
      p99Latency: '6.2 ms'
    },
    'search-service': {
      role: 'Faceted product search, auto-completion, typo tolerance & relevance ranking',
      resilience: 'Stateless pods with query hedging and timeout fallback',
      avgThroughput: '14,000 req/s',
      p99Latency: '16 ms'
    },
    'inventory-service': {
      role: 'Warehouse stock reservation locks, backorder rules & safety stock management',
      resilience: 'Distributed locking via Redis redlock with optimistic concurrency',
      avgThroughput: '6,200 req/s',
      p99Latency: '12 ms'
    },
    'order-service': {
      role: 'Saga orchestrator executing distributed transaction states (Placed -> Dispatched)',
      resilience: 'Temporal/Step-Functions saga coordinator with exponential retries',
      avgThroughput: '5,400 req/s',
      p99Latency: '32 ms'
    },
    'auth-service': {
      role: 'Amazon Cognito / OAuth2 token exchange, JWT signature verify & merchant permissions',
      resilience: 'Multi-pod deployment with cryptographic worker pool pool-size auto-tuning',
      avgThroughput: '22,000 req/s',
      p99Latency: '4.8 ms'
    },
    'recommendation-engine': {
      role: 'Personalized product suggestions ("Frequently Bought Together") and rankings',
      resilience: 'GPU-backed inference worker pools with fast fallback heuristics',
      avgThroughput: '12,500 req/s',
      p99Latency: '28 ms'
    },
    'sqs-event-bus': {
      role: 'Fully-managed async message queue decoupling orders from fulfillment & messaging',
      resilience: 'SQS Standard with Dead-Letter Queues (DLQ) and redrive policy',
      avgThroughput: '15,000 msg/s',
      p99Latency: '1.8 ms'
    },
    'notification-service': {
      role: 'Transactional emails, dispatch notifications, SMS delivery alerts, and push notifications',
      resilience: 'Async consumer worker pool scaling on SQS queue depth metric',
      avgThroughput: '2,400 msg/s',
      p99Latency: '42 ms'
    },
    'shipping-service': {
      role: 'Carrier selection (Amazon Logistics, UPS, FedEx), shipping labels & tracking',
      resilience: 'Worker cluster with carrier API circuit breakers and fallback rate cards',
      avgThroughput: '1,800 req/s',
      p99Latency: '85 ms'
    },
    'api-gateway': {
      role: 'AWS API Gateway & Envoy L7 Ingress proxying external traffic to internal microservices',
      resilience: 'Global Envoy cluster with rate limiting, WAF hooks & automatic retries',
      avgThroughput: '72,000 req/s',
      p99Latency: '3.4 ms'
    },
    'web-storefront': {
      role: 'Next.js SSR edge frontend serving browser desktop & mobile web traffic',
      resilience: 'Edge SSR instances deployed on AWS ECS with auto-recovery',
      avgThroughput: '38,000 req/s',
      p99Latency: '18 ms'
    },
    'mobile-bff': {
      role: 'Backend-for-Frontend payload aggregator tailored for Amazon iOS and Android apps',
      resilience: 'Stateless Node/Go aggregator service with GraphQL query caching',
      avgThroughput: '44,000 req/s',
      p99Latency: '14 ms'
    },
    'cloud-front': {
      role: 'Global Edge CDN (400+ PoPs), AWS WAF Layer-7 rules & DDoS Shield Advanced',
      resilience: 'Amazon Anycast DNS and distributed edge points of presence',
      avgThroughput: '84,500 req/s',
      p99Latency: '1.1 ms'
    }
  },
  layoutPositions: {
    // Tier 1: Data Persistence (y: 50)
    'aurora-orders-db': { x: 50, y: 50 },
    'dynamodb-cart': { x: 330, y: 50 },
    'redis-cache': { x: 610, y: 50 },
    'opensearch-cluster': { x: 890, y: 50 },
    'warehouse-db': { x: 1170, y: 50 },

    // Tier 2: Direct DB Consumers (y: 280)
    'payment-service': { x: 50, y: 280 },
    'cart-service': { x: 330, y: 280 },
    'product-catalog': { x: 610, y: 280 },
    'search-service': { x: 890, y: 280 },
    'inventory-service': { x: 1170, y: 280 },

    // Tier 3: Domain Orchestration & Secondary Services (y: 510)
    'order-service': { x: 50, y: 510 },
    'auth-service': { x: 330, y: 510 },
    'recommendation-engine': { x: 610, y: 510 },
    'sqs-event-bus': { x: 890, y: 510 },
    'notification-service': { x: 1170, y: 510 },

    // Tier 4: Fulfillment & Gateway Hub (y: 740)
    'api-gateway': { x: 330, y: 740 },
    'shipping-service': { x: 890, y: 740 },

    // Tier 5: Frontends & Client Aggregation (y: 970)
    'web-storefront': { x: 190, y: 970 },
    'mobile-bff': { x: 470, y: 970 },

    // Tier 6: Edge CDN & Ingress (y: 1200)
    'cloud-front': { x: 330, y: 1200 }
  },
  rawEdges: [
    // Data Tier -> Microservices
    { id: 'e-aurora-pay', source: 'aurora-orders-db', target: 'payment-service' },
    { id: 'e-aurora-order', source: 'aurora-orders-db', target: 'order-service' },
    { id: 'e-dynamo-cart', source: 'dynamodb-cart', target: 'cart-service' },
    { id: 'e-redis-catalog', source: 'redis-cache', target: 'product-catalog' },
    { id: 'e-redis-auth', source: 'redis-cache', target: 'auth-service' },
    { id: 'e-redis-recs', source: 'redis-cache', target: 'recommendation-engine' },
    { id: 'e-opensearch-search', source: 'opensearch-cluster', target: 'search-service' },
    { id: 'e-warehouse-inv', source: 'warehouse-db', target: 'inventory-service' },

    // Microservices Cross-Dependencies
    { id: 'e-pay-order', source: 'payment-service', target: 'order-service' },
    { id: 'e-inv-order', source: 'inventory-service', target: 'order-service' },
    { id: 'e-catalog-cart', source: 'product-catalog', target: 'cart-service' },
    { id: 'e-order-sqs', source: 'order-service', target: 'sqs-event-bus' },

    // Async Event Bus Consumers
    { id: 'e-sqs-ship', source: 'sqs-event-bus', target: 'shipping-service' },
    { id: 'e-sqs-notif', source: 'sqs-event-bus', target: 'notification-service' },

    // Ingress to API Gateway
    { id: 'e-order-gw', source: 'order-service', target: 'api-gateway' },
    { id: 'e-cart-gw', source: 'cart-service', target: 'api-gateway' },
    { id: 'e-catalog-gw', source: 'product-catalog', target: 'api-gateway' },
    { id: 'e-auth-gw', source: 'auth-service', target: 'api-gateway' },

    // Direct search & recs to frontends
    { id: 'e-search-web', source: 'search-service', target: 'web-storefront' },
    { id: 'e-search-mob', source: 'search-service', target: 'mobile-bff' },
    { id: 'e-recs-web', source: 'recommendation-engine', target: 'web-storefront' },

    // Gateway to Frontends
    { id: 'e-gw-web', source: 'api-gateway', target: 'web-storefront' },
    { id: 'e-gw-mob', source: 'api-gateway', target: 'mobile-bff' },

    // Frontends to CloudFront Edge
    { id: 'e-web-cf', source: 'web-storefront', target: 'cloud-front' },
    { id: 'e-mob-cf', source: 'mobile-bff', target: 'cloud-front' }
  ],
  downstreamGraph: {
    'aurora-orders-db': ['payment-service', 'order-service'],
    'dynamodb-cart': ['cart-service'],
    'redis-cache': ['product-catalog', 'auth-service', 'recommendation-engine'],
    'opensearch-cluster': ['search-service'],
    'warehouse-db': ['inventory-service'],
    'payment-service': ['order-service'],
    'inventory-service': ['order-service'],
    'product-catalog': ['cart-service', 'api-gateway'],
    'cart-service': ['api-gateway'],
    'order-service': ['sqs-event-bus', 'api-gateway'],
    'auth-service': ['api-gateway'],
    'recommendation-engine': ['web-storefront'],
    'search-service': ['web-storefront', 'mobile-bff'],
    'sqs-event-bus': ['shipping-service', 'notification-service'],
    'shipping-service': [],
    'notification-service': [],
    'api-gateway': ['web-storefront', 'mobile-bff'],
    'web-storefront': ['cloud-front'],
    'mobile-bff': ['cloud-front'],
    'cloud-front': []
  }
};

export const PRESETS: Record<PresetId, ArchitecturePreset> = {
  'k8s-core': K8S_CORE_PRESET,
  'amazon-scale': AMAZON_SCALE_PRESET
};
