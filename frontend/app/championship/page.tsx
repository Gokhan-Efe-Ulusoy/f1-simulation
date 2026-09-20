export default function ChampionshipPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <header>
          <h1 className="text-4xl font-bold text-f1-red">Championship</h1>
          <p className="text-gray-400 mt-2">Championship simulation is planned and currently disabled.</p>
        </header>
        <section className="bg-f1-dark border border-f1-gray rounded-xl p-6">
          <p className="text-gray-300">No championship endpoint exists yet. Single races and Monte Carlo run in the Simulator.</p>
        </section>
      </div>
    </div>
  );
}
