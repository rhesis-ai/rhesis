import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import { QuotaNotice } from '../QuotaNotice';
import { QuotaResource } from '@/constants/quota';

function baseProps(
  overrides: Partial<React.ComponentProps<typeof QuotaNotice>> = {}
) {
  return {
    resource: QuotaResource.PROJECTS,
    kind: 'stock' as const,
    used: 1,
    limit: 1,
    zone: 'blocked' as const,
    canUpgrade: false,
    ...overrides,
  };
}

describe('QuotaNotice', () => {
  it('shows an error icon and the blocked sentence', () => {
    render(<QuotaNotice {...baseProps()} />);
    expect(
      screen.getByText('Your organization is at its projects limit (1 of 1).')
    ).toBeInTheDocument();
    expect(screen.getByTestId('ErrorOutlineIcon')).toBeInTheDocument();
  });

  it('always links to org usage, admin or not', () => {
    render(<QuotaNotice {...baseProps()} />);
    expect(screen.getByRole('link', { name: /org usage/i })).toHaveAttribute(
      'href',
      '/organizations/usage'
    );
  });

  it('only offers the upgrade link when the reader can act on it', () => {
    const { rerender } = render(
      <QuotaNotice {...baseProps({ canUpgrade: false })} />
    );
    expect(
      screen.queryByRole('link', { name: /upgrade plan/i })
    ).not.toBeInTheDocument();

    rerender(<QuotaNotice {...baseProps({ canUpgrade: true })} />);
    expect(
      screen.getByRole('link', { name: /upgrade plan/i })
    ).toBeInTheDocument();
  });

  it('renders an info icon for a past-included zone, not an error one', () => {
    render(
      <QuotaNotice
        {...baseProps({
          resource: QuotaResource.TEST_EXECUTIONS,
          kind: 'flow',
          zone: 'pastIncluded',
        })}
      />
    );
    expect(screen.getByTestId('InfoOutlinedIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('ErrorOutlineIcon')).not.toBeInTheDocument();
  });
});
