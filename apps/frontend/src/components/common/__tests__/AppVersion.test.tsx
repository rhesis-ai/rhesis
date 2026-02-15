import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AppVersion } from '../AppVersion';

// Mock git-utils to control version output
jest.mock('@/utils/git-utils', () => ({
  getVersionInfo: () => ({
    version: '1.2.3',
    branch: 'main',
    commit: 'abc1234',
    isProduction: true,
  }),
  formatVersionDisplay: (
    info: { version: string },
    prefix: string
  ) => `${prefix}${info.version}`,
}));

describe('AppVersion', () => {
  it('renders version with default prefix', () => {
    render(<AppVersion />);
    expect(screen.getByText('v1.2.3')).toBeInTheDocument();
  });

  it('renders version with custom prefix', () => {
    render(<AppVersion prefix="Version " />);
    expect(screen.getByText('Version 1.2.3')).toBeInTheDocument();
  });

  it('renders version without prefix when showPrefix is false', () => {
    render(<AppVersion showPrefix={false} />);
    expect(screen.getByText('1.2.3')).toBeInTheDocument();
  });

  it('renders as caption typography by default', () => {
    const { container } = render(<AppVersion />);
    const typography = container.querySelector('.MuiTypography-caption');
    expect(typography).toBeInTheDocument();
  });

  it('supports custom variant', () => {
    const { container } = render(<AppVersion variant="body2" />);
    const typography = container.querySelector('.MuiTypography-body2');
    expect(typography).toBeInTheDocument();
  });
});
