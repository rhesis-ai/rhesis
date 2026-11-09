import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import DetailTabNav from '../DetailTabNav';

describe('DetailTabNav', () => {
  it('renders a tab badge beside its label', () => {
    render(
      <DetailTabNav
        tabs={[
          { key: 'basic', label: 'Basic Information' },
          { key: 'tuning', label: 'Tuning', badge: <span>beta</span> },
        ]}
        activeIndex={0}
        onChange={() => {}}
      />
    );

    const tuningTab = screen.getByRole('tab', { name: /Tuning/ });
    expect(tuningTab).toHaveTextContent('Tuning');
    expect(tuningTab).toHaveTextContent('beta');
    // The badge belongs to the Tuning tab, not to the whole tablist.
    expect(
      screen.getByRole('tab', { name: 'Basic Information' })
    ).not.toHaveTextContent('beta');
  });

  it('keeps a tab icon out of the tab name', () => {
    render(
      <DetailTabNav
        tabs={[
          {
            key: 'linked',
            label: 'Tests',
            icon: <svg role="img" aria-label="Linked" />,
          },
        ]}
        activeIndex={0}
        onChange={() => {}}
      />
    );

    expect(screen.getByRole('tab', { name: /^tests$/i })).toBeInTheDocument();
  });
});
