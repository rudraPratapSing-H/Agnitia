// frontend/src/components/extras/PostmortemView.tsx (Member 4, task 3.11)
// <PostmortemView incidentId={incident.id} /> -- fetches /api/incidents/{id}/postmortem,
// renders it, and lets the viewer download the raw markdown.
import React, { useState } from 'react';
import { FileText, Download, X, Loader2, AlertTriangle } from 'lucide-react';

interface PostmortemViewProps {
  incidentId: string;
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

/** Minimal, dependency-free markdown renderer: headers, bold, rules, lists, code fences. */
function renderMarkdown(md: string): React.ReactNode[] {
  const lines = md.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  let codeBuffer: string[] | null = null;

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul key={key} className="list-disc pl-5 space-y-0.5 text-stone-700">
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
      .replace(/`(.+?)`/g, '<code class="bg-stone-100 px-1 rounded text-[11px]">$1</code>');

  lines.forEach((line, idx) => {
    const key = `l-${idx}`;

    if (line.trim().startsWith('```')) {
      if (codeBuffer === null) {
        codeBuffer = [];
      } else {
        out.push(
          <pre key={key} className="bg-stone-900 text-stone-100 text-[11px] p-2.5 rounded-lg overflow-x-auto">
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
      out.push(<h4 key={key} className="text-xs font-bold text-stone-800 mt-2">{line.slice(4)}</h4>);
      return;
    }
    if (line.startsWith('## ')) {
      flushList(key);
      out.push(<h3 key={key} className="text-sm font-bold text-stone-900 mt-3">{line.slice(3)}</h3>);
      return;
    }
    if (line.startsWith('# ')) {
      flushList(key);
      out.push(<h2 key={key} className="text-base font-black text-stone-900">{line.slice(2)}</h2>);
      return;
    }
    if (/^[-*]\s+/.test(line)) {
      listBuffer.push(line.replace(/^[-*]\s+/, ''));
      return;
    }
    flushList(key);
    if (line.trim() === '') return;
    out.push(
      <p key={key} className="text-[11px] text-stone-600 leading-relaxed" dangerouslySetInnerHTML={{ __html: inlineMd(line) }} />
    );
  });
  flushList('l-end');

  return out;
}

export default function PostmortemView({ incidentId }: PostmortemViewProps) {
  const [open, setOpen] = useState(false);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setOpen(true);
    if (markdown !== null || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBase()}/api/incidents/${incidentId}/postmortem`);
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ''}`);
      }
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await res.json();
        setMarkdown(data.markdown ?? data.content ?? JSON.stringify(data, null, 2));
      } else {
        setMarkdown(await res.text());
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load postmortem');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `postmortem-${incidentId}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <button
        onClick={load}
        className="px-3 py-1.5 rounded-lg border border-stone-300 hover:bg-stone-100 text-stone-700 text-xs font-bold uppercase flex items-center gap-1.5 transition-colors"
      >
        <FileText size={13} />
        <span>Postmortem</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 backdrop-blur-xs p-4 font-mono">
          <div className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-stone-300 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-3.5 border-b border-stone-200 bg-stone-50/90 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <FileText size={15} className="text-stone-700" />
                <span className="text-xs font-black text-stone-900 uppercase tracking-tight">
                  Postmortem — {incidentId}
                </span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="w-6 h-6 rounded-md hover:bg-stone-200 text-stone-400 hover:text-stone-700 flex items-center justify-center transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            <div className="p-4 overflow-y-auto flex-1 space-y-1.5">
              {loading && (
                <div className="flex items-center gap-2 text-stone-500 text-xs py-8 justify-center">
                  <Loader2 size={14} className="animate-spin" />
                  Generating postmortem…
                </div>
              )}
              {error && (
                <div className="flex items-start gap-2 text-rose-700 text-[11px] bg-rose-50 border border-rose-200 rounded-lg p-2.5">
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}
              {markdown && renderMarkdown(markdown)}
            </div>

            <div className="p-3 border-t border-stone-200 bg-stone-50/90 flex items-center justify-end gap-2 shrink-0">
              <button
                onClick={() => setOpen(false)}
                className="px-3 py-1.5 rounded-lg border border-stone-300 hover:bg-stone-100 text-stone-700 text-xs font-bold uppercase transition-colors"
              >
                Close
              </button>
              <button
                onClick={handleDownload}
                disabled={!markdown}
                className="px-3.5 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 disabled:opacity-40 disabled:hover:bg-stone-900 text-white text-xs font-bold uppercase flex items-center gap-1.5 transition-colors"
              >
                <Download size={13} />
                <span>Download .md</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
