import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ToolbarActions from '../ToolbarActions';

jest.mock('@toolpad/core/Account', () => ({
  Account: () => <div data-testid="account" />,
}));

jest.mock('@/components/common/ThemeToggle', () => ({
  __esModule: true,
  default: () => <button data-testid="theme-toggle">Theme</button>,
}));

jest.mock('@/components/common/AppVersion', () => ({
  __esModule: true,
  default: () => <span data-testid="app-version">v1.0.0</span>,
}));

const mockShouldShowGitInfo = jest.fn();

jest.mock('@/utils/git-utils', () => ({
  shouldShowGitInfo: () => mockShouldShowGitInfo(),
}));

describe('ToolbarActions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the theme toggle', () => {
    mockShouldShowGitInfo.mockReturnValue(false);
    render(<ToolbarActions />);
    expect(screen.getByTestId('theme-toggle')).toBeInTheDocument();
  });

  it('renders the Account component', () => {
    mockShouldShowGitInfo.mockReturnValue(false);
    render(<ToolbarActions />);
    expect(screen.getByTestId('account')).toBeInTheDocument();
  });

  it('renders AppVersion when shouldShowGitInfo returns true', () => {
    mockShouldShowGitInfo.mockReturnValue(true);
    render(<ToolbarActions />);
    expect(screen.getByTestId('app-version')).toBeInTheDocument();
  });

  it('does not render AppVersion when shouldShowGitInfo returns false', () => {
    mockShouldShowGitInfo.mockReturnValue(false);
    render(<ToolbarActions />);
    expect(screen.queryByTestId('app-version')).not.toBeInTheDocument();
  });
});
