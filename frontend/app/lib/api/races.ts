'use client';

import { apiFetch } from './client';
import type { Race, RaceDetail } from './types';

export async function listRaces(season?: string, limit = 50): Promise<{ races: Race[]; total: number }> {
  const q = new URLSearchParams();
  if (season) q.set('season', season);
  q.set('limit', String(limit));
  return apiFetch<{ races: Race[]; total: number }>(`/races?${q.toString()}`);
}

export async function getRace(raceId: string): Promise<RaceDetail> {
  return apiFetch<RaceDetail>(`/races/${encodeURIComponent(raceId)}`);
}

export async function getMetadata(): Promise<import('./types').MetadataResponse> {
  return apiFetch<import('./types').MetadataResponse>('/metadata');
}
