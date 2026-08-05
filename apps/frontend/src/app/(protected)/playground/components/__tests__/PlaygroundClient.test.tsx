import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import PlaygroundClient from '../PlaygroundClient';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('next/navigation', () => ({
  useSearchParams: jest.fn(),
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useEndpointOptions: jest.fn(),
}));

jest.mock('../PlaygroundChat', () => ({
  __esModule: true,
  default: ({ endpointId }: { endpointId: string }) => (
    <div data-testid="playground-chat">{endpointId}</div>
  ),
}));

jest.mock('../PlaygroundEndpointDrawer', () => ({
  __esModule: true,
  default: () => <div data-testid="endpoint-drawer" />,
}));

import { useSearchParams } from 'next/navigation';
import { useEndpointOptions, type EndpointOption } from '@/hooks/useEndpoints';

function makeOption(id: string): EndpointOption {
  return {
    endpointId: id,
    endpointName: `Endpoint ${id}`,
    projectId: `project-${id}`,
    projectName: `Project ${id}`,
    environment: 'development',
  };
}

function mockEndpoints(options: EndpointOption[]) {
  (useEndpointOptions as jest.Mock).mockReturnValue({
    options,
    isLoading: false,
    error: null,
  });
}

function mockSearchParams(params: Record<string, string> = {}) {
  (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams(params));
}

function renderClient() {
  return render(
    <ThemeProvider theme={lightTheme}>
      <PlaygroundClient />
    </ThemeProvider>
  );
}

describe('PlaygroundClient endpoint defaulting', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('selects the only endpoint automatically', () => {
    mockSearchParams();
    mockEndpoints([makeOption('a')]);

    renderClient();

    expect(screen.getByTestId('playground-chat')).toHaveTextContent('a');
  });

  it('shows the placeholder when several endpoints are available', () => {
    mockSearchParams();
    mockEndpoints([makeOption('a'), makeOption('b')]);

    renderClient();

    expect(screen.queryByTestId('playground-chat')).not.toBeInTheDocument();
    expect(
      screen.getByText('Select an endpoint to start chatting')
    ).toBeInTheDocument();
  });

  it('prefers the endpointId URL param over the single-endpoint default', () => {
    mockSearchParams({ endpointId: 'b' });
    mockEndpoints([makeOption('a'), makeOption('b')]);

    renderClient();

    expect(screen.getByTestId('playground-chat')).toHaveTextContent('b');
  });

  it('leaves nothing selected when the URL param does not match an endpoint', () => {
    mockSearchParams({ endpointId: 'missing' });
    mockEndpoints([makeOption('a')]);

    renderClient();

    expect(screen.queryByTestId('playground-chat')).not.toBeInTheDocument();
  });
});
