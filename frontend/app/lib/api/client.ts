'use client';

import type { ApiError } from './types';

export function apiBaseUrl(): string {
  const v = process.env.NEXT_PUBLIC_API_URL;
  if (v && v.length > 0) return v.replace(/\/$/, '');
  return 'http://localhost:8000/api/v1';
}

export class ApiClientError extends Error {
  code: string;
  httpStatus: number;
  constructor(code: string, message: string, httpStatus: number) {
    super(message);
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
    const data: unknown = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = data as ApiError;
      throw new ApiClientError(
        err?.error?.code ?? `HTTP_${res.status}`,
        err?.error?.message ?? `Request failed (${res.status})`,
        res.status,
      );
    }
    return data as T;
  } catch (e) {
    if (e instanceof ApiClientError) throw e;
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiClientError('TIMEOUT', 'Request timed out', 408);
    }
    throw new ApiClientError('NETWORK_ERROR', e instanceof Error ? e.message : 'Network error', 0);
  } finally {
    clearTimeout(t);
  }
}
