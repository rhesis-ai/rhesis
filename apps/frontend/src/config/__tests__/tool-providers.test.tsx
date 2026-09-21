import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TOOL_PROVIDER_ICONS } from '../tool-providers';

describe('TOOL_PROVIDER_ICONS', () => {
  const entries = Object.entries(TOOL_PROVIDER_ICONS);

  it.each(entries)(
    '%s renders an icon with explicit dimensions',
    (_key, icon) => {
      // An <svg> carrying only a viewBox has no intrinsic size and expands to
      // fill its container. Azure DevOps did exactly that and blew out its tile,
      // because the h-8/w-8 classes these once carried were Tailwind, which this
      // project does not use, so they never applied.
      const { container } = render(<div>{icon}</div>);
      const svg = container.querySelector('svg');

      expect(svg).not.toBeNull();
      expect(svg).toHaveAttribute('width');
      expect(svg).toHaveAttribute('height');
    }
  );

  it('renders every icon at the same size', () => {
    const sizes = entries.map(([, icon]) => {
      const { container } = render(<div>{icon}</div>);
      const svg = container.querySelector('svg');
      return `${svg?.getAttribute('width')}x${svg?.getAttribute('height')}`;
    });

    expect(new Set(sizes).size).toBe(1);
  });

  it('carries no dead Tailwind classes', () => {
    const { container } = render(<div>{TOOL_PROVIDER_ICONS.azure_devops}</div>);

    expect(container.querySelector('svg')).not.toHaveClass('h-8');
  });
});
