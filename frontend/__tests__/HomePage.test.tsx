import { render, screen } from '@testing-library/react';
import HomePage from '../app/page';

describe('HomePage', () => {
  it('renders the main title', () => {
    render(<HomePage />);
    expect(screen.getByText('F1 Simulation Platform')).toBeInTheDocument();
  });

  it('renders navigation cards', () => {
    render(<HomePage />);
    expect(screen.getByText('Race Simulator')).toBeInTheDocument();
    expect(screen.getByText('Championship')).toBeInTheDocument();
    expect(screen.getByText('Monte Carlo')).toBeInTheDocument();
    expect(screen.getByText('Strategy Engine')).toBeInTheDocument();
  });
});