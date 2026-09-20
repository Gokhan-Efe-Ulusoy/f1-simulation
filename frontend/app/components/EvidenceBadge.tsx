'use client';

import type { EvidenceTier } from '@/lib/api/types';

const STYLES: Record<string, string> = {
  CALIBRATED: 'bg-green-900 text-green-200 border-green-700',
  LIMITED: 'bg-yellow-900 text-yellow-200 border-yellow-700',
  PRIOR_ONLY: 'bg-orange-900 text-orange-200 border-orange-700',
  PROXY_ONLY: 'bg-orange-900 text-orange-200 border-orange-700',
  NON_IDENTIFIABLE: 'bg-red-900 text-red-200 border-red-700',
  ASSOCIATIONAL: 'bg-purple-900 text-purple-200 border-purple-700',
  UNKNOWN: 'bg-gray-800 text-gray-300 border-gray-600',
};

export default function EvidenceBadge({ tier, label }: { tier: string; label?: string }) {
  const t = (tier ?? 'UNKNOWN') as EvidenceTier;
  const cls = STYLES[t] ?? STYLES.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-2 px-2 py-1 rounded border text-xs font-mono ${cls}`} aria-label={`${label ?? 'evidence'}: ${t}`}>
      {label && <span className="font-sans">{label}</span>}
      <span>{t}</span>
    </span>
  );
}
