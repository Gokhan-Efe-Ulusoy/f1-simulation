'use client';

export default function JobProgress({ status, progress, stage }: { status: string; progress?: number | null; stage?: string | null }) {
  const s = status.toUpperCase();
  return (
    <div className="space-y-1" role="status" aria-label={`job ${s}`}>
      <div className="text-sm text-gray-300">
        Status: <span className="font-mono">{s}</span>
        {stage && <span className="text-gray-400"> · Stage: <span className="font-mono">{stage}</span></span>}
      </div>
      {typeof progress === 'number' && (
        <div className="text-sm text-gray-400">
          Progress: <span className="font-mono">{Math.round(progress * 100)}%</span> (backend-reported; no per-lap fabrication)
        </div>
      )}
      {s === 'RUNNING' && typeof progress !== 'number' && (
        <div className="text-sm text-gray-400">Simulation running… stage-level progress only.</div>
      )}
    </div>
  );
}
