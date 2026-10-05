import React from 'react';
import { render, screen, waitFor, act } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

import ModelSetupGate from '../ModelSetupGate';
import {
  FeaturesProvider,
  useRefreshFeatures,
} from '@/contexts/FeaturesContext';
import type { FeaturesResponse } from '@/utils/api-client/features-client';
import { reportModelNotConfigured } from '@/utils/model-setup';

const mockGetFeatures = jest.fn();
const mockRouterRefresh = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: mockRouterRefresh }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getFeaturesClient: () => ({ getFeatures: mockGetFeatures }),
  })),
}));

// Stands in for the real step: one button that does what both real flows end
// in, a `GET /features` refetch.
jest.mock('@/app/(protected)/models/components/ConnectModelStep', () => {
  function MockConnectModelStep() {
    const refresh = useRefreshFeatures();
    return (
      <div data-testid="connect-model-step">
        <button onClick={() => refresh()}>connect</button>
      </div>
    );
  }
  return { __esModule: true, default: MockConnectModelStep };
});

function features(overrides: Partial<FeaturesResponse> = {}): FeaturesResponse {
  return {
    license: { edition: 'community', licensed: false },
    enabled: [],
    models_ready: true,
    ...overrides,
  };
}

function renderGate(
  initialFeatures: FeaturesResponse | null,
  hasOrganization = true
) {
  return render(
    <FeaturesProvider initialFeatures={initialFeatures}>
      <ModelSetupGate hasOrganization={hasOrganization}>
        <div data-testid="app">app</div>
      </ModelSetupGate>
    </FeaturesProvider>
  );
}

beforeEach(() => {
  mockGetFeatures.mockReset();
  mockRouterRefresh.mockReset();
});

describe('ModelSetupGate', () => {
  it('shows the step instead of the app when no model is ready', () => {
    renderGate(features({ models_ready: false }));

    expect(screen.getByTestId('connect-model-step')).toBeInTheDocument();
    expect(screen.queryByTestId('app')).not.toBeInTheDocument();
  });

  it('shows the app when a model is ready', () => {
    renderGate(features({ models_ready: true }));

    expect(screen.getByTestId('app')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
  });

  it('does not gate a user without an organization', () => {
    renderGate(features({ models_ready: false }), false);

    expect(screen.getByTestId('app')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
  });

  it('does not gate when the backend predates the field', () => {
    renderGate(features({ models_ready: undefined }));

    expect(screen.getByTestId('app')).toBeInTheDocument();
  });

  it('does not gate when the features fetch fails', async () => {
    mockGetFeatures.mockRejectedValue(new Error('boom'));

    renderGate(null);

    await waitFor(() => expect(mockGetFeatures).toHaveBeenCalled());
    expect(screen.getByTestId('app')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
  });

  it('goes away once a features refetch reports a ready model', async () => {
    mockGetFeatures.mockResolvedValue(features({ models_ready: true }));
    renderGate(features({ models_ready: false }));

    await userEvent.click(screen.getByRole('button', { name: 'connect' }));

    expect(await screen.findByTestId('app')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
    expect(mockGetFeatures).toHaveBeenCalledTimes(1);
    // The page behind the step predates the model, so its server data is refreshed.
    expect(mockRouterRefresh).toHaveBeenCalledTimes(1);
  });

  it('refreshes the page each time the gate drops', async () => {
    mockGetFeatures.mockResolvedValue(features({ models_ready: true }));
    renderGate(features({ models_ready: false }));

    await userEvent.click(screen.getByRole('button', { name: 'connect' }));
    expect(await screen.findByTestId('app')).toBeInTheDocument();
    expect(mockRouterRefresh).toHaveBeenCalledTimes(1);

    // The model goes away again (deleted, key removed): the step returns.
    mockGetFeatures.mockResolvedValue(features({ models_ready: false }));
    act(() => {
      reportModelNotConfigured();
    });
    expect(await screen.findByTestId('connect-model-step')).toBeInTheDocument();
    expect(mockRouterRefresh).toHaveBeenCalledTimes(1);

    mockGetFeatures.mockResolvedValue(features({ models_ready: true }));
    await userEvent.click(screen.getByRole('button', { name: 'connect' }));
    expect(await screen.findByTestId('app')).toBeInTheDocument();
    expect(mockRouterRefresh).toHaveBeenCalledTimes(2);
  });

  it('does not refresh the page for a user who was never gated', () => {
    renderGate(features({ models_ready: true }));

    expect(mockRouterRefresh).not.toHaveBeenCalled();
  });

  it('stays up when the refetch still reports no model', async () => {
    mockGetFeatures.mockResolvedValue(features({ models_ready: false }));
    renderGate(features({ models_ready: false }));

    await userEvent.click(screen.getByRole('button', { name: 'connect' }));

    await waitFor(() => expect(mockGetFeatures).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('connect-model-step')).toBeInTheDocument();
  });

  it('refetches features and shows the step when a model check fails anywhere', async () => {
    mockGetFeatures.mockResolvedValue(features({ models_ready: false }));
    renderGate(features({ models_ready: true }));
    expect(screen.getByTestId('app')).toBeInTheDocument();

    act(() => {
      reportModelNotConfigured();
    });

    expect(await screen.findByTestId('connect-model-step')).toBeInTheDocument();
    expect(screen.queryByTestId('app')).not.toBeInTheDocument();
  });

  it('keeps the app when a model check fails but the defaults are fine', async () => {
    mockGetFeatures.mockResolvedValue(features({ models_ready: true }));
    renderGate(features({ models_ready: true }));

    act(() => {
      reportModelNotConfigured();
    });

    await waitFor(() => expect(mockGetFeatures).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('app')).toBeInTheDocument();
  });
});
