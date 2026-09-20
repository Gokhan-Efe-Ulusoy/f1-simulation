'use client';

import Link from 'next/link';

export default function MonteCarloPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <header>
          <h1 className="text-4xl font-bold text-f1-red">Monte Carlo</h1>
          <p className="text-gray-400 mt-2">Probability analysis runs in the Simulator (Monte Carlo mode).</p>
        </header>
        <section className="bg-f1-dark border border-f1-gray rounded-xl p-6">
          <p className="text-gray-300">Use the simulator with mode set to Monte Carlo (N 1..5000, deterministic seed). Results show model-generated probabilities, not predictions.</p>
          <Link href="/simulator" className="inline-block mt-4 px-4 py-2 bg-f1-red rounded-lg">Open Simulator</Link>
        </section>
      </div>
    </div>
  );
}
