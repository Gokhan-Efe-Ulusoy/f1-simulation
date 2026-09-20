'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import ErrorState from '@/components/ErrorState';
import EvidenceBadge from '@/components/EvidenceBadge';
import JobProgress from '@/components/JobProgress';
import SimulationProvenance from '@/components/SimulationProvenance';
import { ApiClientError } from '@/lib/api/client';
import { getMetadata, getRace, listRaces } from '@/lib/api/races';
import { isTerminalStatus, pollSimulation, submitMonteCarlo, submitSingleRace } from '@/lib/api/simulations';
import type { MetadataResponse, MonteCarloResult, Race, SingleRaceResult } from '@/lib/api/types';

type Mode = 'single' | 'montecarlo';
type Phase = 'idle' | 'submitting' | 'polling' | 'done' | 'error';

function errMsg(e: unknown): string {
  if (e instanceof ApiClientError) return `${e.code}: ${e.message}`;
  return e instanceof Error ? e.message : 'Unknown error';
}

function classRow(r: Record<string, unknown>, i: number) {
  return (
    <tr key={String(r.driver_id ?? r.driver ?? i)} className="border-b border-f1-gray/50">
      <td className="py-1 pr-2 font-mono">{String(r.position ?? r.pos ?? i + 1)}</td>
      <td className="py-1 pr-2">{String(r.driver_id ?? r.driver ?? '—')}</td>
      <td className="py-1 pr-2 text-gray-400">{String(r.constructor_id ?? r.constructor ?? r.team ?? '—')}</td>
      <td className="py-1 font-mono">{String(r.total_time ?? r.time ?? r.status ?? '—')}</td>
    </tr>
  );
}

export default function SimulatorPage() {
  const [season, setSeason] = useState('2024');
  const [races, setRaces] = useState<Race[]>([]);
  const [racesState, setRacesState] = useState<'loading' | 'empty' | 'error' | 'success'>('loading');
  const [racesError, setRacesError] = useState('');
  const [raceId, setRaceId] = useState('');
  const [raceDetail, setRaceDetail] = useState<string>('');
  const [mode, setMode] = useState<Mode>('single');
  const [seed, setSeed] = useState('42');
  const [laps, setLaps] = useState('');
  const [count, setCount] = useState('100');
  const [enableWeather, setEnableWeather] = useState(true);
  const [enableSetup, setEnableSetup] = useState(false);
  const [enableRaceControl, setEnableRaceControl] = useState(false);
  const [enableStrategy, setEnableStrategy] = useState(false);
  const [meta, setMeta] = useState<MetadataResponse | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [job, setJob] = useState<{ simulation_id: string; status: string; progress?: number | null; current_stage?: string | null } | null>(null);
  const [result, setResult] = useState<SingleRaceResult | MonteCarloResult | null>(null);
  const [error, setError] = useState('');
  const [resultA, setResultA] = useState<SingleRaceResult | MonteCarloResult | null>(null);
  const [resultB, setResultB] = useState<SingleRaceResult | MonteCarloResult | null>(null);

  useEffect(() => {
    getMetadata().then(setMeta).catch(() => undefined);
  }, []);

  const autoSelected = useRef(false);
  const loadRaces = useCallback(async () => {
    setRacesState('loading');
    setRacesError('');
    try {
      const r = await listRaces(season.trim() || undefined, 50);
      setRaces(r.races);
      setRacesState(r.races.length === 0 ? 'empty' : 'success');
      if (r.races.length > 0 && !autoSelected.current) {
        autoSelected.current = true;
        setRaceId(r.races[0].race_id);
      }
    } catch (e) {
      setRacesState('error');
      setRacesError(errMsg(e));
    }
  }, [season]);

  useEffect(() => {
    loadRaces();
  }, [loadRaces]);

  useEffect(() => {
    if (!raceId) return;
    getRace(raceId)
      .then((d) => setRaceDetail(`${d.circuit_id ?? '?'} · ${d.race_date ?? '?'} · round ${d.round ?? '?'} · ${d.availability}`))
      .catch(() => setRaceDetail(''));
  }, [raceId]);

  function validate(): string | null {
    if (!raceId) return 'Select a race first.';
    const s = Number(seed);
    if (!Number.isInteger(s) || s < -2147483648 || s > 2147483647) return 'Seed must be an int32 integer.';
    if (laps.trim() !== '') {
      const l = Number(laps);
      if (!Number.isInteger(l) || l < 1 || l > 200) return 'Laps must be an integer 1..200.';
    }
    if (mode === 'montecarlo') {
      const n = Number(count);
      if (!Number.isInteger(n) || n < 1 || n > 5000) return 'Simulation count must be an integer 1..5000 (backend limit).';
    }
    return null;
  }

  async function onSubmit() {
    const v = validate();
    if (v) {
      setPhase('error');
      setError(v);
      return;
    }
    setPhase('submitting');
    setError('');
    setResult(null);
    try {
      const lapsOverride = laps.trim() === '' ? null : Number(laps);
      const seedNum = Number(seed);
      let sub: SingleRaceResult | MonteCarloResult;
      if (mode === 'single') {
        sub = await submitSingleRace({
          race_id: raceId,
          seed: seedNum,
          laps_override: lapsOverride,
          enable_strategy: enableStrategy,
          enable_setup: enableSetup,
          enable_weather: enableWeather,
          enable_race_control: enableRaceControl,
        });
      } else {
        sub = await submitMonteCarlo({
          race_id: raceId,
          simulations: Number(count),
          seed: seedNum,
          laps_override: lapsOverride,
          enable_strategy: enableStrategy,
          enable_setup: enableSetup,
          enable_weather: enableWeather,
          enable_race_control: enableRaceControl,
        });
      }
      setJob({ simulation_id: sub.simulation_id, status: sub.status, progress: sub.progress, current_stage: sub.current_stage });
      if (isTerminalStatus(sub.status) && ('classification' in sub || 'win_probabilities' in sub)) {
        setResult(sub);
        setPhase('done');
        return;
      }
      setPhase('polling');
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const s = await pollSimulation(sub.simulation_id);
        setJob({ simulation_id: sub.simulation_id, status: s.status, progress: (s.progress as number | null) ?? null, current_stage: (s.current_stage as string | null) ?? null });
        if (isTerminalStatus(s.status)) {
          const full = s.result && typeof s.result === 'object' && ('classification' in (s.result as object) || 'win_probabilities' in (s.result as object))
            ? (s.result as unknown as SingleRaceResult | MonteCarloResult)
            : ({ ...sub, status: s.status } as SingleRaceResult | MonteCarloResult);
          setResult(full);
          setPhase('done');
          return;
        }
      }
      setPhase('error');
      setError('Polling timed out after 120s.');
    } catch (e) {
      setPhase('error');
      setError(errMsg(e));
    }
  }

  const tiers = meta?.evidence_tiers ?? {};
  const single = mode === 'single' ? (result as SingleRaceResult | null) : null;
  const mc = mode === 'montecarlo' ? (result as MonteCarloResult | null) : null;

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-4xl font-bold text-f1-red">F1 Simulator</h1>
          <p className="text-gray-400 mt-1">Simulate the race that didn&apos;t happen — real backend, transparent uncertainty.</p>
        </header>

        <section aria-label="Race selection" className="bg-f1-dark border border-f1-gray rounded-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold">1. Race selection</h2>
          <div className="flex flex-col md:flex-row gap-4">
            <label className="flex flex-col gap-1">
              <span>Season</span>
              <input aria-label="Season" value={season} onChange={(e) => setSeason(e.target.value)} className="px-3 py-2 rounded bg-f1-gray text-white" placeholder="2024" />
            </label>
            <label className="flex flex-col gap-1 flex-1">
              <span>Race</span>
              <select aria-label="Race" value={raceId} onChange={(e) => setRaceId(e.target.value)} className="px-3 py-2 rounded bg-f1-gray text-white">
                {races.map((r) => (
                  <option key={r.race_id} value={r.race_id}>
                    {r.race_id} ({r.circuit_id ?? '?'})
                  </option>
                ))}
              </select>
            </label>
          </div>
          {racesState === 'loading' && <p>Loading races…</p>}
          {racesState === 'empty' && <p>No races available.</p>}
          {racesState === 'error' && <ErrorState title="Unable to load races." message={racesError} />}
          {racesState === 'success' && <p className="text-sm text-gray-400">{races.length} races available. {raceDetail}</p>}
        </section>

        <section aria-label="Simulation mode" className="bg-f1-dark border border-f1-gray rounded-xl p-6 space-y-2">
          <h2 className="text-xl font-semibold">2. Simulation mode</h2>
          <div role="radiogroup" aria-label="Mode" className="flex gap-4">
            <label><input type="radio" name="mode" checked={mode === 'single'} onChange={() => setMode('single')} /> Single Race</label>
            <label><input type="radio" name="mode" checked={mode === 'montecarlo'} onChange={() => setMode('montecarlo')} /> Monte Carlo</label>
          </div>
          <p className="text-sm text-gray-400">Strategy Lab, Counterfactual, Championship, Regulation Lab: planned, disabled.</p>
        </section>

        <section aria-label="Configuration" className="bg-f1-dark border border-f1-gray rounded-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold">3. Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="flex flex-col gap-1"><span>Seed (int32)</span>
              <input aria-label="Seed" value={seed} onChange={(e) => setSeed(e.target.value)} className="px-3 py-2 rounded bg-f1-gray text-white" /></label>
            <label className="flex flex-col gap-1"><span>Laps override (1..200, blank = default)</span>
              <input aria-label="Laps override" value={laps} onChange={(e) => setLaps(e.target.value)} className="px-3 py-2 rounded bg-f1-gray text-white" /></label>
            {mode === 'montecarlo' && (
              <label className="flex flex-col gap-1"><span>Simulations (1..5000)</span>
                <input aria-label="Simulations" value={count} onChange={(e) => setCount(e.target.value)} className="px-3 py-2 rounded bg-f1-gray text-white" />
                <span className="text-xs text-gray-400">Maximum simulations: 5,000</span></label>
            )}
          </div>
          <fieldset>
            <legend className="font-medium">Supported modifiers (backend schema)</legend>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
              <label><input type="checkbox" checked={enableWeather} onChange={(e) => setEnableWeather(e.target.checked)} /> Weather enabled</label>
              <label><input type="checkbox" checked={enableSetup} onChange={(e) => setEnableSetup(e.target.checked)} /> Setup modifier</label>
              <label><input type="checkbox" checked={enableRaceControl} onChange={(e) => setEnableRaceControl(e.target.checked)} /> Race-control scenario</label>
              <label><input type="checkbox" checked={enableStrategy} onChange={(e) => setEnableStrategy(e.target.checked)} /> Strategy integration</label>
            </div>
          </fieldset>
        </section>

        <section aria-label="Evidence and model status" className="bg-f1-dark border border-f1-gray rounded-xl p-6 space-y-2">
          <h2 className="text-xl font-semibold">4. Evidence / model status</h2>
          {meta ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(tiers).slice(0, 8).map(([k, v]) => (
                <EvidenceBadge key={k} tier={v} label={k} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">Loading model status…</p>
          )}
          <p className="text-sm text-gray-400">Weather and setup modifiers are hypothetical / PRIOR_ONLY where indicated — not historical measurements. Fuel is NON_IDENTIFIABLE.</p>
        </section>

        <section aria-label="Run" className="bg-f1-dark border border-f1-gray rounded-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold">5. Run simulation</h2>
          <button onClick={onSubmit} disabled={phase === 'submitting' || phase === 'polling'} className="px-4 py-2 bg-f1-red rounded-lg disabled:opacity-50">
            {phase === 'submitting' ? 'Submitting…' : phase === 'polling' ? 'Polling…' : 'Run simulation'}
          </button>
          {job && <JobProgress status={job.status} progress={job.progress} stage={job.current_stage} />}
          {phase === 'error' && <ErrorState title="Simulation could not be completed." message={error} />}
        </section>

        {result && (
          <section aria-label="Results" className="bg-f1-dark border border-f1-gray rounded-xl p-6 space-y-4">
            <h2 className="text-xl font-semibold">6. Results</h2>
            {single?.classification && (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead><tr className="border-b border-f1-gray text-gray-400"><th>Pos</th><th>Driver</th><th>Constructor</th><th>Time / Status</th></tr></thead>
                  <tbody>{(single.classification as Record<string, unknown>[]).map(classRow)}</tbody>
                </table>
              </div>
            )}
            {mc?.win_probabilities && (
              <div className="space-y-4">
                <p className="text-sm text-gray-300">Model-generated probabilities under the selected scenario and assumptions, not deterministic predictions.</p>
                <table className="w-full text-left">
                  <thead><tr className="border-b border-f1-gray text-gray-400"><th>Driver</th><th>Win prob</th><th>Podium prob</th><th>Expected finish</th></tr></thead>
                  <tbody>
                    {Object.keys(mc.win_probabilities).sort((a, b) => (mc.win_probabilities?.[b] ?? 0) - (mc.win_probabilities?.[a] ?? 0)).slice(0, 10).map((d) => (
                      <tr key={d} className="border-b border-f1-gray/50">
                        <td className="py-1 font-mono">{d}</td>
                        <td className="py-1 font-mono">{((mc.win_probabilities?.[d] ?? 0) * 100).toFixed(1)}%</td>
                        <td className="py-1 font-mono">{((mc.podium_probabilities?.[d] ?? 0) * 100).toFixed(1)}%</td>
                        <td className="py-1 font-mono">{String((mc as unknown as Record<string, Record<string, number>>).expected_finish?.[d] ?? (mc.finish_position_distribution?.[d] ? '—' : '—'))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <SimulationProvenance data={result as unknown as Record<string, unknown>} />
            <div className="flex gap-2">
              <button onClick={() => setResultA(result)} className="px-3 py-1 border border-f1-gray rounded">Set as A</button>
              <button onClick={() => setResultB(result)} className="px-3 py-1 border border-f1-gray rounded">Set as B</button>
              <button onClick={onSubmit} className="px-3 py-1 border border-f1-gray rounded">Rerun with different seed/config</button>
            </div>
            {resultA && resultB && <ComparisonView a={resultA} b={resultB} />}
          </section>
        )}
      </div>
    </div>
  );
}

function ComparisonView({ a, b }: { a: SingleRaceResult | MonteCarloResult; b: SingleRaceResult | MonteCarloResult }) {
  const aCls = (a as SingleRaceResult).classification as Record<string, unknown>[] | undefined;
  const bCls = (b as SingleRaceResult).classification as Record<string, unknown>[] | undefined;
  if (aCls && bCls) {
    const pos = (rows: Record<string, unknown>[]) => Object.fromEntries(rows.map((r) => [String(r.driver_id ?? r.driver), Number(r.position ?? r.pos ?? 0)]));
    const pa = pos(aCls);
    const pb = pos(bCls);
    const drivers = [...new Set([...Object.keys(pa), ...Object.keys(pb)])].sort();
    return (
      <div>
        <h3 className="font-semibold mt-4">Comparison A vs B (observed differences only — not causal attribution)</h3>
        <table className="w-full text-left mt-2">
          <thead><tr className="text-gray-400"><th>Driver</th><th>A pos</th><th>B pos</th><th>Δ (B−A)</th></tr></thead>
          <tbody>
            {drivers.map((d) => (
              <tr key={d} className="border-b border-f1-gray/50">
                <td className="font-mono">{d}</td><td className="font-mono">{pa[d] ?? '—'}</td><td className="font-mono">{pb[d] ?? '—'}</td>
                <td className="font-mono">{pa[d] != null && pb[d] != null ? (pb[d] as number) - (pa[d] as number) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  const aw = (a as MonteCarloResult).win_probabilities;
  const bw = (b as MonteCarloResult).win_probabilities;
  if (aw && bw) {
    const drivers = [...new Set([...Object.keys(aw), ...Object.keys(bw)])].sort();
    return (
      <div>
        <h3 className="font-semibold mt-4">Comparison A vs B (observed differences only — not causal attribution)</h3>
        <table className="w-full text-left mt-2">
          <thead><tr className="text-gray-400"><th>Driver</th><th>A win</th><th>B win</th><th>Δ</th></tr></thead>
          <tbody>
            {drivers.map((d) => (
              <tr key={d} className="border-b border-f1-gray/50">
                <td className="font-mono">{d}</td>
                <td className="font-mono">{((aw[d] ?? 0) * 100).toFixed(1)}%</td>
                <td className="font-mono">{((bw[d] ?? 0) * 100).toFixed(1)}%</td>
                <td className="font-mono">{(((bw[d] ?? 0) - (aw[d] ?? 0)) * 100).toFixed(1)}pp</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return <p className="text-sm text-gray-400">Selected results are not comparable (different modes).</p>;
}
