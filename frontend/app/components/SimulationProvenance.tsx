'use client';

export default function SimulationProvenance({ data }: { data: Record<string, unknown> }) {
  const rows: Array<[string, unknown]> = [
    ['Simulation ID', data.simulation_id],
    ['Seed', data.seed],
    ['Race', data.race_id],
    ['Simulations', data.simulations ?? data.N],
    ['Dataset', (data.provenance as Record<string, unknown> | undefined)?.dataset_version],
    ['Model', (data.provenance as Record<string, unknown> | undefined)?.model_version],
    ['Request hash', data.request_hash],
    ['Simulation ID (hash)', data.result_hash],
  ];
  return (
    <dl className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex gap-2">
          <dt className="text-gray-400 w-36 shrink-0">{k}</dt>
          <dd className="font-mono break-all">{v == null || v === '' ? '—' : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
