import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageOverviewFilterDrawer from '../UsageOverviewFilterDrawer';

describe('UsageOverviewFilterDrawer', () => {
  it('defaults the select to "Current period" when no period is applied', () => {
    render(
      <UsageOverviewFilterDrawer
        open
        onClose={jest.fn()}
        periodStart={null}
        onApply={jest.fn()}
      />
    );

    expect(screen.getByText('Current period')).toBeInTheDocument();
  });

  it('applies the selected past month and closes', () => {
    const onApply = jest.fn();
    const onClose = jest.fn();
    render(
      <UsageOverviewFilterDrawer
        open
        onClose={onClose}
        periodStart={null}
        onApply={onApply}
      />
    );

    fireEvent.mouseDown(screen.getByLabelText('Period'));
    const options = screen.getAllByRole('option');
    // options[0] is "Current period"; the next one is the most recent past month.
    fireEvent.click(options[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onApply).toHaveBeenCalledWith(
      expect.stringMatching(/^\d{4}-\d{2}-01$/)
    );
    expect(onClose).toHaveBeenCalled();
  });

  it('resets the draft back to the current period without applying', () => {
    const onApply = jest.fn();
    render(
      <UsageOverviewFilterDrawer
        open
        onClose={jest.fn()}
        periodStart="2026-07-01"
        onApply={onApply}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));

    expect(screen.getByText('Current period')).toBeInTheDocument();
    expect(onApply).not.toHaveBeenCalled();
  });
});
