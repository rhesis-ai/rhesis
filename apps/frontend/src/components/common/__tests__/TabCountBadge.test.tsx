import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import { TabCountBadge } from '../TabCountBadge';

describe('TabCountBadge', () => {
  it('shows the count', () => {
    render(<TabCountBadge count={3} />);

    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders nothing at zero', () => {
    // Also the state every caller starts in, before its query resolves.
    const { container } = render(<TabCountBadge count={0} />);

    expect(container).toBeEmptyDOMElement();
  });
});
