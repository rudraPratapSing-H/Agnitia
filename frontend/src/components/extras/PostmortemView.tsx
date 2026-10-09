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
      <ul key={key} className="list-disc pl-4 text-stone-600 text-[11px] space-y-1">
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
      .replace(/`(.+?)`/g, '<code class="bg-stone-100 px-1 rounded text-[10px]">$1</code>');

  lines.forEach((line, idx) => {
    const key = `l-${idx}`;

    if (line.trim().startsWith('```')) {
      if (codeBuffer === null) {
        codeBuffer = [];
      } else {
        out.push(
          <pre key={key} className="bg-stone-900 text-stone-100 text-[10px] p-2.5 rounded-lg overflow-x-auto font-mono">
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
      out.push(<hr key={key} className="border-stone-200 my-2" />);
      return;
    }
    if (line.startsWith('### ')) {
      flushList(key);
      out.push(
        <h4 key={key} className="text-xs font-bold font-mono text-stone-800 uppercase flex items-center gap-1.5 mt-2">
          {line.slice(4)}
        </h4>
      );
      return;
    }
    if (line.startsWith('## ')) {
      flushList(key);
      out.push(
        <h3 key={key} className="text-xs font-bold font-mono text-stone-800 uppercase flex items-center gap-1.5 mt-3">
          {line.slice(3)}
        </h3>
      );
      return;
    }
    if (line.startsWith('# ')) {
      flushList(key);
      out.push(<h2 key={key} className="text-sm font-black text-stone-900">{line.slice(2)}</h2>);
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
        className="text-stone-600 text-[11px] leading-relaxed font-sans"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 backdrop-blur-xs p-4 animate-fadeIn font-mono">
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-stone-300 overflow-hidden flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="p-4 border-b border-stone-200 bg-stone-50/90 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-stone-900 text-white flex items-center justify-center shadow-xs">
              <FileText size={17} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-black text-stone-900 tracking-tight">
                  INCIDENT POSTMORTEM REPORT
                </h2>
                <span className="bg-emerald-100 text-emerald-900 text-[11px] font-bold px-2 py-0.5 rounded border border-emerald-300">
                  {id} • {incident.status.toUpperCase()}
                </span>
              </div>
              <p className="text-[11px] text-stone-500 font-sans">
                Generated live by Agnitia's AI postmortem writer
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg hover:bg-stone-200 text-stone-400 hover:text-stone-700 flex items-center justify-center transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable Document Content */}
        <div className="p-5 space-y-4 overflow-y-auto custom-scrollbar flex-1 text-xs">

          {/* Key Metrics Grid (real incident data, not placeholders) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div className="bg-stone-50 p-2.5 rounded-xl border border-stone-200">
              <span className="text-stone-400 block text-[10px] uppercase">MTTR</span>
              <span className="font-bold text-emerald-700 text-xs">{durationLabel(started_at, resolved_at)}</span>
            </div>
            <div className="bg-stone-50 p-2.5 rounded-xl border border-stone-200">
              <span className="text-stone-400 block text-[10px] uppercase">ALERTS -&gt; INCIDENTS</span>
              <span className="font-bold text-stone-800 text-xs">{raw_alert_count} -&gt; 1</span>
            </div>
            <div className="bg-stone-50 p-2.5 rounded-xl border border-stone-200">
              <span className="text-stone-400 block text-[10px] uppercase">ROOT CAUSE</span>
              <span className="font-bold text-rose-700 text-xs">{root_service}</span>
            </div>
            <div className="bg-stone-50 p-2.5 rounded-xl border border-stone-200">
              <span className="text-stone-400 block text-[10px] uppercase">CONFIDENCE</span>
              <span className="font-bold text-emerald-700 text-xs">{confidencePct !== null ? `${confidencePct}%` : '—'}</span>
            </div>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-stone-500 text-xs py-8 justify-center">
              <Loader2 size={14} className="animate-spin" />
              Writing postmortem…
            </div>
          )}
          {error && (
            <div className="flex items-start gap-2 text-rose-700 text-[11px] bg-rose-50 border border-rose-200 rounded-lg p-2.5">
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
              <h3 className="text-xs font-bold font-mono text-stone-800 uppercase flex items-center gap-1.5">
                <ShieldCheck size={13} className="text-emerald-600" />
                Verified citations
              </h3>
              <div className="space-y-1 pt-1 font-mono">
                {rca.evidence.map((ev, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-[11px] bg-stone-50 p-1.5 rounded border border-stone-200">
                    {ev.verified ? (
                      <CheckCircle2 size={11} className="text-emerald-600 shrink-0" />
                    ) : (
                      <Flame size={11} className="text-rose-600 shrink-0" />
                    )}
                    <span className="text-stone-500 font-bold uppercase text-[9px] bg-stone-200 px-1 rounded">
                      {ev.type}
                    </span>
                    <span className="truncate text-stone-700">{ev.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3.5 border-t border-stone-200 bg-stone-50/90 flex items-center justify-between shrink-0">
          <span className="text-[11px] text-stone-500 flex items-center gap-1">
            <Server size={11} />
            Fetched from /api/incidents/{id}/postmortem
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg border border-stone-300 hover:bg-stone-100 text-stone-700 text-xs font-bold uppercase transition-colors"
            >
              CLOSE
            </button>

            <button
              onClick={handleDownload}
              disabled={!markdown}
              className="px-3.5 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 disabled:opacity-40 disabled:hover:bg-stone-900 text-white text-xs font-bold uppercase flex items-center gap-1.5 shadow-xs transition-colors"
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
