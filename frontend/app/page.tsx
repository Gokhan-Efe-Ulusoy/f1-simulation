import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <div className="max-w-4xl w-full text-center space-y-8">
        <header className="space-y-4">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-f1-red">
            F1 Simulation Platform
          </h1>
          <p className="text-xl md:text-2xl text-gray-300 max-w-2xl mx-auto">
            Professional-grade Formula 1 simulation engine with modular architecture,
            deterministic modeling, and Monte Carlo capabilities.
          </p>
        </header>

        <nav className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
          <Link
            href="/simulator"
            className="group p-6 bg-f1-dark border border-f1-gray rounded-xl hover:border-f1-red/50 transition-colors text-left"
          >
            <h2 className="text-xl font-semibold mb-2 group-hover:text-f1-red transition-colors">
              Race Simulator
            </h2>
            <p className="text-gray-400">
              Simulate individual races with full physics-based modeling
            </p>
          </Link>

          <Link
            href="/championship"
            className="group p-6 bg-f1-dark border border-f1-gray rounded-xl hover:border-f1-red/50 transition-colors text-left"
          >
            <h2 className="text-xl font-semibold mb-2 group-hover:text-f1-red transition-colors">
              Championship
            </h2>
            <p className="text-gray-400">
              Full season simulation with standings and points
            </p>
          </Link>

          <Link
            href="/monte-carlo"
            className="group p-6 bg-f1-dark border border-f1-gray rounded-xl hover:border-f1-red/50 transition-colors text-left"
          >
            <h2 className="text-xl font-semibold mb-2 group-hover:text-f1-red transition-colors">
              Monte Carlo
            </h2>
            <p className="text-gray-400">
              Run thousands of simulations for probability analysis
            </p>
          </Link>

          <Link
            href="/strategy"
            className="group p-6 bg-f1-dark border border-f1-gray rounded-xl hover:border-f1-red/50 transition-colors text-left"
          >
            <h2 className="text-xl font-semibold mb-2 group-hover:text-f1-red transition-colors">
              Strategy Engine
            </h2>
            <p className="text-gray-400">
              Optimize pit stops, tyre choices, and race strategy
            </p>
          </Link>
        </nav>

        <footer className="border-t border-f1-gray pt-8 mt-8">
          <p className="text-gray-500 text-sm">
            Version 0.1.0 &mdash; Phase 0: Architecture & Repository Setup
          </p>
          <p className="text-gray-500 text-sm mt-1">
            API: <code className="text-f1-red">http://localhost:8000/docs</code>
          </p>
        </footer>
      </div>
    </main>
  );
}