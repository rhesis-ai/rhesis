import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageOverTimeFilterDrawer from '../UsageOverTimeFilterDrawer';

describe('UsageOverTimeFilterDrawer', () => {
  it('renders a chip for each timespan option', () => {
    render(
      <UsageOverTimeFilterDrawer
        open
        onClose={jest.fn()}
        months={6}
        onChange={jest.fn()}
      />
    );

    expect(screen.getByText('3M')).toBeInTheDocument();
    expect(screen.getByText('6M')).toBeInTheDocument();
    expect(screen.getByText('12M')).toBeInTheDocument();
  });

  it('calls onChange immediately when a chip is clicked, without an Apply step', () => {
    const onChange = jest.fn();
    render(
      <UsageOverTimeFilterDrawer
        open
        onClose={jest.fn()}
        months={6}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByText('12M'));

    expect(onChange).toHaveBeenCalledWith(12);
    expect(
      screen.queryByRole('button', { name: 'Apply' })
    ).not.toBeInTheDocument();
  });
});
