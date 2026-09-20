'use client';

import { apiFetch } from './client';
import type { JobStatus, MonteCarloRequest, MonteCarloResult, RaceSimulationRequest, SingleRaceResult } from './types';

export async function submitSingleRace(req: RaceSimulationRequest): Promise<SingleRaceResult> {
  return apiFetch<SingleRaceResult>('/simulate/race', { method: 'POST', body: JSON.stringify(req) }, 60000);
}

export async function submitMonteCarlo(req: MonteCarloRequest): Promise<MonteCarloResult> {
  return apiFetch<MonteCarloResult>('/simulate/monte-carlo', { method: 'POST', body: JSON.stringify(req) }, 60000);
}

export async function pollSimulation(simulationId: string): Promise<JobStatus & Record<string, unknown>> {
  return apiFetch<JobStatus & Record<string, unknown>>(`/simulation/${encodeURIComponent(simulationId)}`);
}

export function isTerminalStatus(status: string): boolean {
  return ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT'].includes(status.toUpperCase());
}

export async function pollUntilDone(
  simulationId: string,
  onUpdate?: (s: JobStatus) => void,
  intervalMs = 2000,
  maxAttempts = 60,
): Promise<JobStatus & Record<string, unknown>> {
  let last: JobStatus & Record<string, unknown> = { simulation_id: simulationId, status: 'QUEUED' };
  for (let i = 0; i < maxAttempts; i++) {
    last = await pollSimulation(simulationId);
    onUpdate?.(last as JobStatus);
    if (isTerminalStatus(last.status)) return last;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error('Polling timed out');
}
