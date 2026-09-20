import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'F1 Simulation Platform',
  description: 'Professional Formula 1 Simulation Platform',
};

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/simulator', label: 'Simulator' },
  { href: '/monte-carlo', label: 'Monte Carlo' },
  { href: '/strategy', label: 'Strategy' },
  { href: '/championship', label: 'Championship' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-f1-black text-white">
        <nav aria-label="Primary" className="border-b border-f1-gray">
          <div className="max-w-5xl mx-auto px-4 py-3 flex gap-4">
            {NAV.map((n) => (
              <a key={n.href} href={n.href} className="text-sm text-gray-300 hover:text-white focus:underline">
                {n.label}
              </a>
            ))}
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
