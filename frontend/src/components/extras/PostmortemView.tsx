// D:\CoffeeOverflow\Agnitia\frontend\src\components\extras\PostmortemView.tsx - SRE Postmortem Generator
import React, { useEffect, useState } from 'react';
import { X, Download, FileText, CheckCircle2, ShieldCheck, Flame, Server, Loader2, AlertTriangle } from 'lucide-react';
import { Incident } from '../../types';

interface PostmortemViewProps {
  isOpen: boolean;
  onClose: () => void;
  incident: Incident | null;
}

function getApiBase(): string {
  const wsUrl: string = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000/ws';
  try {
    const u = new URL(wsUrl);
    u.protocol = u.protocol === 'wss:' ? 'https:' : 'http:';
    return `${u.protocol}//${u.host}`;
  } catch {
    return 'http://localhost:8000';
  }
}

function durationLabel(startedAt?: string | null, resolvedAt?: string | null): string {
  if (!startedAt || !resolvedAt) return 'ongoing';
  const secs = Math.max(0, Math.round((new Date(resolvedAt).getTime() - new Date(startedAt).getTime()) / 1000));
  return `${secs}s`;
}

/** Minimal, dependency-free markdown renderer: headers, bold, rules, lists, code fences. */
function renderMarkdown(md: string): React.ReactNode[] {
  const lines = md.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  let codeBuffer: string[] | null = null;

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul key={key} className="list-disc pl-4 text-ink-400 text-[11px] space-y-1">
        {listBuffer.map((item, i) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: inlineMd(item) }} />
        ))}
      </ul>
    );
    listBuffer = [];
  };

  const inlineMd = (text: string): string =>
    text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code class="bg-ink-800 px-1 rounded text-[10px]">$1</code>');

  lines.forEach((line, idx) => {
    const key = `l-${idx}`;

    if (line.trim().startsWith('```')) {
      if (codeBuffer === null) {
        codeBuffer = [];
      } else {
        out.push(
          <pre key={key} className="bg-ink-950 text-ink-200 text-[10px] p-2.5 rounded-lg overflow-x-auto font-mono">
            {codeBuffer.join('\n')}
          </pre>
        );
        codeBuffer = null;
      }
      return;
    }
    if (codeBuffer !== null) {
      codeBuffer.push(line);
      return;
    }

    if (/^---+$/.test(line.trim())) {
      flushList(key);
      out.push(<hr key={key} className="border-ink-700 my-2" />);
      return;
    }
    if (line.startsWith('### ')) {
      flushList(key);
      out.push(
        <h4 key={key} className="text-xs font-bold font-mono text-ink-200 uppercase flex items-center gap-1.5 mt-2">
          {line.slice(4)}
        </h4>
      );
      return;
    }
    if (line.startsWith('## ')) {
      flushList(key);
      out.push(
        <h3 key={key} className="text-xs font-bold font-mono text-ink-200 uppercase flex items-center gap-1.5 mt-3">
          {line.slice(3)}
        </h3>
      );
      return;
    }
    if (line.startsWith('# ')) {
      flushList(key);
      out.push(<h2 key={key} className="text-sm font-black text-ink-50">{line.slice(2)}</h2>);
      return;
    }
    if (/^[-*]\s+/.test(line)) {
      listBuffer.push(line.replace(/^[-*]\s+/, ''));
      return;
    }
    flushList(key);
    if (line.trim() === '') return;
    out.push(
      <p
        key={key}
        className="text-ink-400 text-[11px] leading-relaxed font-sans"
        dangerouslySetInnerHTML={{ __html: inlineMd(line) }}
      />
    );
  });
  flushList('l-end');

  return out;
}

export default function PostmortemView({ isOpen, onClose, incident }: PostmortemViewProps) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !incident) return;
    let cancelled = false;
    setMarkdown(null);
    setError(null);
    setLoading(true);

    fetch(`${getApiBase()}/api/incidents/${incident.id}/postmortem`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.text().catch(() => '');
          throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ''}`);
        }
        return res.text();
      })
      .then((text) => {
        if (!cancelled) setMarkdown(text);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err?.message || 'Failed to generate postmortem');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, incident?.id]);

  if (!isOpen || !incident) return null;

  const { id, root_service, rca, started_at, resolved_at, raw_alert_count } = incident;
  const confidencePct = rca ? Math.round(rca.confidence * 100) : null;

  const handleDownload = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `postmortem-${id}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/60 backdrop-blur-xs p-4 animate-fadeIn font-mono">
      <div className="w-full max-w-2xl bg-ink-900 rounded-2xl shadow-2xl border border-ink-700 overflow-hidden flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="p-4 border-b border-ink-700 bg-ink-850 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-copper-500 text-ink-950 flex items-center justify-center">
              <FileText size={17} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-black text-ink-50 tracking-tight">
                  INCIDENT POSTMORTEM REPORT
                </h2>
                <span className="bg-emerald-500/15 text-emerald-300 text-[11px] font-bold px-2 py-0.5 rounded border border-emerald-500/35">
                  {id} • {incident.status.toUpperCase()}
                </span>
              </div>
              <p className="text-[11px] text-ink-500 font-sans">
                Generated live by Agnitia's AI postmortem writer
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg hover:bg-ink-800 text-ink-500 hover:text-ink-200 flex items-center justify-center transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable Document Content */}
        <div className="p-5 space-y-4 overflow-y-auto custom-scrollbar flex-1 text-xs">

          {/* Key Metrics Grid (real incident data, not placeholders) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div className="bg-ink-850 p-2.5 rounded-xl border border-ink-700">
              <span className="text-ink-500 block text-[10px] uppercase">MTTR</span>
              <span className="font-bold text-emerald-300 text-xs">{durationLabel(started_at, resolved_at)}</span>
            </div>
            <div className="bg-ink-850 p-2.5 rounded-xl border border-ink-700">
              <span className="text-ink-500 block text-[10px] uppercase">ALERTS -&gt; INCIDENTS</span>
              <span className="font-bold text-ink-200 text-xs">{raw_alert_count} -&gt; 1</span>
            </div>
            <div className="bg-ink-850 p-2.5 rounded-xl border border-ink-700">
              <span className="text-ink-500 block text-[10px] uppercase">ROOT CAUSE</span>
              <span className="font-bold text-rose-300 text-xs">{root_service}</span>
            </div>
            <div className="bg-ink-850 p-2.5 rounded-xl border border-ink-700">
              <span className="text-ink-500 block text-[10px] uppercase">CONFIDENCE</span>
              <span className="font-bold text-emerald-300 text-xs">{confidencePct !== null ? `${confidencePct}%` : '—'}</span>
            </div>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-ink-400 text-xs py-8 justify-center">
              <Loader2 size={14} className="animate-spin" />
              Writing postmortem…
            </div>
          )}
          {error && (
            <div className="flex items-start gap-2 text-rose-300 text-[11px] bg-rose-500/10 border border-rose-500/30 rounded-lg p-2.5">
              <AlertTriangle size={14} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          {markdown && (
            <div className="space-y-1.5">
              {renderMarkdown(markdown)}
            </div>
          )}

          {/* Verified citations, rendered from live rca.evidence regardless of the
              generated markdown's own wording, so the Verified badges always show. */}
          {rca && rca.evidence.length > 0 && (
            <div className="space-y-1.5 font-sans">
              <h3 className="text-xs font-bold font-mono text-ink-200 uppercase flex items-center gap-1.5">
                <ShieldCheck size={13} className="text-emerald-400" />
                Verified citations
              </h3>
              <div className="space-y-1 pt-1 font-mono">
                {rca.evidence.map((ev, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-[11px] bg-ink-850 p-1.5 rounded border border-ink-700">
                    {ev.verified ? (
                      <CheckCircle2 size={11} className="text-emerald-400 shrink-0" />
                    ) : (
                      <Flame size={11} className="text-rose-400 shrink-0" />
                    )}
                    <span className="text-ink-400 font-bold uppercase text-[9px] bg-ink-700 px-1 rounded">
                      {ev.type}
                    </span>
                    <span className="truncate text-ink-300">{ev.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3.5 border-t border-ink-700 bg-ink-850 flex items-center justify-between shrink-0">
          <span className="text-[11px] text-ink-500 flex items-center gap-1">
            <Server size={11} />
            Fetched from /api/incidents/{id}/postmortem
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg border border-ink-600 hover:bg-ink-800 text-ink-200 text-xs font-bold uppercase transition-colors"
            >
              CLOSE
            </button>

            <button
              onClick={handleDownload}
              disabled={!markdown}
              className="px-3.5 py-1.5 rounded-lg bg-copper-500 hover:bg-copper-400 disabled:opacity-40 disabled:hover:bg-copper-500 text-ink-950 text-xs font-bold uppercase flex items-center gap-1.5 transition-colors"
            >
              <Download size={13} />
              <span>EXPORT POSTMORTEM (.MD)</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
