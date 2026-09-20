export default function StrategyPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <header>
          <h1 className="text-4xl font-bold text-f1-red">Strategy</h1>
          <p className="text-gray-400 mt-2">Strategy Lab is planned and currently disabled in the UI.</p>
        </header>
        <section className="bg-f1-dark border border-f1-gray rounded-xl p-6">
          <p className="text-gray-300">Backend <code className="font-mono">POST /api/v1/strategy/evaluate</code> exists (PRIOR_ONLY). A typed Strategy Lab form will be added in a later phase; no fake optimizer is shown.</p>
        </section>
      </div>
    </div>
  );
}
