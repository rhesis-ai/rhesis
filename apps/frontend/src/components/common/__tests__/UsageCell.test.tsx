import { render, screen } from '@testing-library/react';
import UsageCell from '../UsageCell';
import { formatCost, formatTokenCount } from '@/utils/trace-utils';

describe('UsageCell', () => {
  it('renders a real zero rather than hiding it', () => {
    // The bug this guards: `value ? format(value) : '—'` turns a trace priced at zero
    // -- a free tier, a comped deployment -- back into "we have no idea".
    render(<UsageCell value={0} format={formatCost} />);
    expect(screen.getByText('$0.00')).toBeInTheDocument();
    expect(screen.queryByText('—')).not.toBeInTheDocument();
  });

  it('renders zero tokens the same way', () => {
    render(<UsageCell value={0} format={formatTokenCount} />);
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('shows a dash when the figure is genuinely unknown', () => {
    render(<UsageCell value={null} format={formatCost} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('shows a dash for undefined, which is what an older response sends', () => {
    render(<UsageCell value={undefined} format={formatCost} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('formats a real figure', () => {
    render(<UsageCell value={112743} format={formatTokenCount} />);
    expect(screen.getByText('112,743')).toBeInTheDocument();
  });

  it('carries its title through for the split tooltip', () => {
    render(
      <UsageCell
        value={5}
        format={formatTokenCount}
        title="3 input · 2 output"
      />
    );
    expect(screen.getByText('5')).toHaveAttribute(
      'title',
      '3 input · 2 output'
    );
  });
});
