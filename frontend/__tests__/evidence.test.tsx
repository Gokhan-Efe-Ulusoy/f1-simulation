import { render, screen } from '@testing-library/react';
import EvidenceBadge from '../app/components/EvidenceBadge';

describe('EvidenceBadge scientific safety', () => {
  it.each(['NON_IDENTIFIABLE', 'PRIOR_ONLY', 'LIMITED'])('renders %s without upgrade', (tier) => {
    render(<EvidenceBadge tier={tier} label="Fuel" />);
    expect(screen.getByLabelText(`Fuel: ${tier}`)).toBeInTheDocument();
    expect(screen.queryByText('KNOWN')).not.toBeInTheDocument();
    expect(screen.queryByText('CALIBRATED')).not.toBeInTheDocument();
    expect(screen.queryByText('OBSERVED')).not.toBeInTheDocument();
  });
});
