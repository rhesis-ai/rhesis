import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import StatusChip, { MetricStatusChip, SimpleStatusChip } from '../StatusChip';

describe('StatusChip', () => {
  it('renders passed status correctly', () => {
    render(<StatusChip passed={true} label="Test Passed" />);

    expect(screen.getByText('Test Passed')).toBeInTheDocument();
    expect(screen.getByTestId('CheckCircleOutlineIcon')).toBeInTheDocument();
  });

  it('renders failed status correctly', () => {
    render(<StatusChip passed={false} label="Test Failed" />);

    expect(screen.getByText('Test Failed')).toBeInTheDocument();
    expect(screen.getByTestId('CancelOutlinedIcon')).toBeInTheDocument();
  });

  it('applies correct colors for passed status', () => {
    const { container } = render(<StatusChip passed={true} label="Passed" />);
    const chip = container.querySelector('.MuiChip-root');

    expect(chip).toHaveClass('MuiChip-colorSuccess');
  });

  it('applies correct colors for failed status', () => {
    const { container } = render(<StatusChip passed={false} label="Failed" />);
    const chip = container.querySelector('.MuiChip-root');

    expect(chip).toHaveClass('MuiChip-colorError');
  });

  it('supports different sizes', () => {
    const { container } = render(
      <StatusChip passed={true} label="Test" size="medium" />
    );
    const chip = container.querySelector('.MuiChip-root');

    expect(chip).toHaveClass('MuiChip-sizeMedium');
  });

  it('supports different variants', () => {
    const { container } = render(
      <StatusChip passed={true} label="Test" variant="filled" />
    );
    const chip = container.querySelector('.MuiChip-root');

    expect(chip).toHaveClass('MuiChip-filled');
  });
});

describe('MetricStatusChip', () => {
  it('renders passed metrics correctly', () => {
    render(<MetricStatusChip passedCount={5} totalCount={5} />);

    expect(screen.getByText('Passed (5/5)')).toBeInTheDocument();
    expect(screen.getByTestId('CheckCircleOutlineIcon')).toBeInTheDocument();
  });

  it('renders failed metrics correctly', () => {
    render(<MetricStatusChip passedCount={3} totalCount={5} />);

    expect(screen.getByText('Failed (3/5)')).toBeInTheDocument();
    expect(screen.getByTestId('CancelOutlinedIcon')).toBeInTheDocument();
  });

  it('handles zero total count', () => {
    render(<MetricStatusChip passedCount={0} totalCount={0} />);

    expect(screen.getByText('Failed (0/0)')).toBeInTheDocument();
    expect(screen.getByTestId('CancelOutlinedIcon')).toBeInTheDocument();
  });
});

describe('SimpleStatusChip', () => {
  it('renders passed status', () => {
    render(<SimpleStatusChip passed={true} />);

    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByTestId('CheckCircleOutlineIcon')).toBeInTheDocument();
  });

  it('renders failed status', () => {
    render(<SimpleStatusChip passed={false} />);

    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByTestId('CancelOutlinedIcon')).toBeInTheDocument();
  });
});
