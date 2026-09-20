import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SimulatorPage from '../app/simulator/page';

function mockFetchOnce(data: unknown, ok = true, status = 200) {
  (global.fetch as jest.Mock).mockResolvedValueOnce({ ok, status, json: async () => data } as Response);
}

describe('SimulatorPage', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    // metadata, races, race detail
    mockFetchOnce({ evidence_tiers: { weather: 'PRIOR_ONLY', fuel: 'NON_IDENTIFIABLE' } });
    mockFetchOnce({ races: [{ race_id: '2024-bahrain', circuit_id: 'bahrain' }], total: 1 });
    mockFetchOnce({ circuit_id: 'bahrain', race_date: '2024-03-02', round: 1, availability: 'available' });
  });
  afterEach(() => jest.restoreAllMocks());

  it('loads races and shows race selection', async () => {
    render(<SimulatorPage />);
    expect(screen.getByText('Loading races…')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/1 races available/)).toBeInTheDocument());
  });

  it('rejects invalid simulation count before submission', async () => {
    render(<SimulatorPage />);
    await waitFor(() => expect(screen.getByText(/1 races available/)).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText('Monte Carlo'));
    fireEvent.change(screen.getByLabelText('Simulations'), { target: { value: '99999' } });
    fireEvent.click(screen.getByText('Run simulation'));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('1..5000'));
  });

  it('shows empty state when no races', async () => {
    (global.fetch as jest.Mock).mockReset();
    mockFetchOnce({ evidence_tiers: {} });
    mockFetchOnce({ races: [], total: 0 });
    render(<SimulatorPage />);
    await waitFor(() => expect(screen.getByText('No races available.')).toBeInTheDocument());
  });

  it('shows error state on races failure', async () => {
    (global.fetch as jest.Mock).mockReset();
    mockFetchOnce({ evidence_tiers: {} });
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('down'));
    render(<SimulatorPage />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });
});
