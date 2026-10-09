// D:\CoffeeOverflow\Agnitia\frontend\src\components\PredictionBanner.tsx - Predictive Capacity Anomaly Banner
import React from 'react';
import { AlertTriangle, TrendingUp, ArrowRight, X, Clock, ShieldAlert } from 'lucide-react';
import { executeFullHealFlow } from '../ws';

interface PredictionBannerProps {
  prediction: {
    service?: string;
    message: string;
    seconds: number;
    trend_mb_s?: number;
  } | null;
  onDismiss?: () => void;
}

export default function PredictionBanner({ prediction, onDismiss }: PredictionBannerProps) {
  if (!prediction) return null;

  const { service = 'postgres', message, seconds, trend_mb_s = 1.2 } = prediction;

  const handlePreventiveAction = () => {
    executeFullHealFlow();
  };

  return (
    <div className="bg-amber-500/10 border border-amber-500/35 rounded-xl p-3 px-4 font-mono text-xs text-amber-100 animate-fadeIn">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Icon & Warning */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-300 flex items-center justify-center shrink-0">
            <AlertTriangle size={17} className="animate-bounce text-amber-300" />
          </div>

          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="bg-amber-500/18 text-amber-200 px-2 py-0.5 rounded text-[10px] font-black tracking-wider border border-amber-500/40 uppercase">
                PREDICTIVE CAPACITY ALERT
              </span>
              <span className="text-amber-300 font-bold text-[11px]">
                TARGET: {service.toUpperCase()}
              </span>
              <span className="text-amber-400 text-[10px] flex items-center gap-1 font-sans">
                <TrendingUp size={11} />
                Slope: +{trend_mb_s} MiB/sec
              </span>
            </div>

            <p className="text-amber-200 text-[11px] font-medium font-sans mt-0.5">
              {message || `Memory exhaustion predicted on ${service} in ${seconds}s based on linear regression trend.`}
            </p>
          </div>
        </div>

        {/* Right: Countdown & Preventive Action */}
        <div className="flex items-center gap-2.5 ml-auto">
          <div className="bg-ink-900 border border-amber-500/35 px-3 py-1.5 rounded-lg flex items-center gap-2">
            <Clock size={13} className="text-amber-400" />
            <span className="text-[10px] text-amber-400 uppercase font-bold">CRASH ETA:</span>
            <span className="text-amber-200 font-black text-sm tabular-nums">
              {seconds}s
            </span>
          </div>

          <button
            onClick={handlePreventiveAction}
            className="bg-copper-500 hover:bg-copper-400 text-ink-950 font-extrabold text-[11px] px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 uppercase transition-all active:scale-[0.98]"
          >
            <span>PREVENTIVE PATCH (256Mi)</span>
            <ArrowRight size={13} />
          </button>

          {onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1.5 rounded-lg hover:bg-amber-500/15 text-amber-400 transition-colors"
              title="Dismiss predictive alert"
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
