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
    <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-3 px-4 shadow-sm font-mono text-xs text-amber-950 animate-fadeIn">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Icon & Warning */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-200/80 border border-amber-400 text-amber-900 flex items-center justify-center shrink-0 shadow-xs">
            <AlertTriangle size={17} className="animate-bounce text-amber-800" />
          </div>

          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="bg-amber-200 text-amber-900 px-2 py-0.5 rounded text-[10px] font-black tracking-wider border border-amber-300 uppercase">
                PREDICTIVE CAPACITY ALERT
              </span>
              <span className="text-amber-800 font-bold text-[11px]">
                TARGET: {service.toUpperCase()}
              </span>
              <span className="text-amber-600 text-[10px] flex items-center gap-1 font-sans">
                <TrendingUp size={11} />
                Slope: +{trend_mb_s} MiB/sec
              </span>
            </div>

            <p className="text-amber-900 text-[11px] font-medium font-sans mt-0.5">
              {message || `Memory exhaustion predicted on ${service} in ${seconds}s based on linear regression trend.`}
            </p>
          </div>
        </div>

        {/* Right: Countdown & Preventive Action */}
        <div className="flex items-center gap-2.5 ml-auto">
          <div className="bg-white border border-amber-300 px-3 py-1.5 rounded-lg flex items-center gap-2 shadow-2xs">
            <Clock size={13} className="text-amber-700" />
            <span className="text-[10px] text-amber-700 uppercase font-bold">CRASH ETA:</span>
            <span className="text-amber-900 font-black text-sm tabular-nums">
              {seconds}s
            </span>
          </div>

          <button
            onClick={handlePreventiveAction}
            className="bg-amber-900 hover:bg-amber-800 text-white font-extrabold text-[11px] px-3.5 py-1.5 rounded-lg border border-amber-950 shadow-xs flex items-center gap-1.5 uppercase transition-all active:scale-[0.98]"
          >
            <span>PREVENTIVE PATCH (256Mi)</span>
            <ArrowRight size={13} />
          </button>

          {onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1.5 rounded-lg hover:bg-amber-200/60 text-amber-700 transition-colors"
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
