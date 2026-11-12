import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ArchitectWelcome from '../ArchitectWelcome';
import { useProjectNeedsEndpoint } from '@/hooks/useProjectNeedsEndpoint';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/hooks/useProjectNeedsEndpoint', () => ({
  useProjectNeedsEndpoint: jest.fn(),
}));

// The help section is covered by its own suite; keep it out of the way here.
jest.mock('../ArchitectHelpSection', () => ({
  __esModule: true,
  default: () => <div data-testid="help-section" />,
}));

const mockUseProjectNeedsEndpoint =
  useProjectNeedsEndpoint as jest.MockedFunction<
    typeof useProjectNeedsEndpoint
  >;

const CHIP_LABEL = 'Safety & fairness tests';

describe('ArchitectWelcome', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows the suggestion chips when the project has an endpoint', () => {
    mockUseProjectNeedsEndpoint.mockReturnValue({
      pending: false,
      needsEndpoint: false,
    });

    render(<ArchitectWelcome onSubmit={jest.fn()} />);

    expect(screen.getByText(CHIP_LABEL)).toBeInTheDocument();
  });

  it('hides the chips when the project has no endpoint — they cannot run', () => {
    mockUseProjectNeedsEndpoint.mockReturnValue({
      pending: false,
      needsEndpoint: true,
    });

    render(<ArchitectWelcome onSubmit={jest.fn()} />);

    expect(screen.queryByText(CHIP_LABEL)).not.toBeInTheDocument();
    // The input stays available, and asks about the agent to connect.
    expect(
      screen.getByPlaceholderText(
        'Describe your agent, or paste its API URL or docs...'
      )
    ).toBeInTheDocument();
  });

  it('shows the chips optimistically while the endpoint check is pending', () => {
    mockUseProjectNeedsEndpoint.mockReturnValue({
      pending: true,
      needsEndpoint: false,
    });

    render(<ArchitectWelcome onSubmit={jest.fn()} />);

    expect(screen.getByText(CHIP_LABEL)).toBeInTheDocument();
  });

  it('asks to connect an agent when the project has no endpoint', () => {
    mockUseProjectNeedsEndpoint.mockReturnValue({
      pending: false,
      needsEndpoint: true,
    });

    render(<ArchitectWelcome onSubmit={jest.fn()} />);

    expect(
      screen.getByText(
        "Let's connect your agent and build your test foundation"
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByText('What would you like to test?')
    ).not.toBeInTheDocument();
  });

  it('asks what to test once the project has an endpoint', () => {
    mockUseProjectNeedsEndpoint.mockReturnValue({
      pending: false,
      needsEndpoint: false,
    });

    render(<ArchitectWelcome onSubmit={jest.fn()} />);

    expect(
      screen.getByText('What would you like to test?')
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('Describe what you want to test...')
    ).toBeInTheDocument();
  });
});
