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

  it('prefers an explicit aria-label over the tooltip', () => {
    render(
      <Fab icon={<span />} tooltip="Delete" aria-label="Delete Test Runs" />
    );
    expect(
      screen.getByRole('button', { name: 'Delete Test Runs' })
    ).toBeInTheDocument();
  });
});
