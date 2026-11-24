import React from 'react';
import { render, screen } from '@testing-library/react';
import { Fab } from '../Fab';

describe('Fab', () => {
  it('uses the tooltip as the button name', () => {
    render(<Fab icon={<span />} tooltip="Manual test" />);
    expect(
      screen.getByRole('button', { name: 'Manual test' })
    ).toBeInTheDocument();
  });

  it('names only the button, not the tooltip wrapper', () => {
    const { container } = render(
      <Fab icon={<span />} tooltip="Download results" />
    );
    expect(container.querySelectorAll('[aria-label]')).toHaveLength(1);
    expect(
      screen.getByRole('button', { name: 'Download results' })
    ).toBeInTheDocument();
  });

  it('prefers an explicit aria-label over the tooltip', () => {
    render(
      <Fab icon={<span />} tooltip="Delete" aria-label="Delete Test Runs" />
    );
    expect(
      screen.getByRole('button', { name: 'Delete Test Runs' })
    ).toBeInTheDocument();
  });
});
