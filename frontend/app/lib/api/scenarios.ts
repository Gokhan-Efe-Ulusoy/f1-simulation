'use client';

import { apiFetch } from './client';

export interface Intervention {
  family: string;
  op: string;
  target: string;
  parameter: string;
  value: unknown;
}

export async function compareScenario(args: {
  race_id: string;
  interventions: Intervention[];
  seed?: number | null;
  simulations?: number;
}): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>('/scenario/compare', { method: 'POST', body: JSON.stringify(args) }, 60000);
}
