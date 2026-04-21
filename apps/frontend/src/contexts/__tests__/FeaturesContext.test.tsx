import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';

import { FeatureName } from '@/constants/features';
import {
  FeatureGate,
  FeaturesProvider,
  useFeature,
  useFeaturesState,
} from '../FeaturesContext';

const mockGetFeatures = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'test-token' },
    status: 'authenticated',
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getFeaturesClient: () => ({
      getFeatures: mockGetFeatures,
    }),
  })),
}));

const LICENSE = { edition: 'community', licensed: false };

beforeEach(() => {
  mockGetFeatures.mockReset();
});

function Probe({ feature }: { feature: FeatureName }) {
  const enabled = useFeature(feature);
  return <div data-testid="probe">{enabled ? 'on' : 'off'}</div>;
}

function StateProbe() {
  const state = useFeaturesState();
  return (
    <div>
      <div data-testid="loading">{String(state.loading)}</div>
      <div data-testid="error">{state.error?.message ?? 'none'}</div>
      <div data-testid="edition">{state.license?.edition ?? 'none'}</div>
    </div>
  );
}

describe('FeaturesProvider', () => {
  it('fetches features on mount and exposes them via useFeature', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: ['sso'] });

    render(
      <FeaturesProvider>
        <Probe feature={FeatureName.SSO} />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('probe')).toHaveTextContent('on')
    );
    expect(mockGetFeatures).toHaveBeenCalledTimes(1);
  });

  it('returns false for features that are not enabled', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: [] });

    render(
      <FeaturesProvider>
        <Probe feature={FeatureName.SSO} />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('probe')).toHaveTextContent('off')
    );
  });

  it('fails closed on fetch error (every feature disabled)', async () => {
    mockGetFeatures.mockRejectedValue(new Error('boom'));

    render(
      <FeaturesProvider>
        <Probe feature={FeatureName.SSO} />
        <StateProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('error')).toHaveTextContent('boom')
    );
    expect(screen.getByTestId('probe')).toHaveTextContent('off');
    expect(screen.getByTestId('loading')).toHaveTextContent('false');
  });

  it('exposes license info in useFeaturesState after load', async () => {
    mockGetFeatures.mockResolvedValue({
      license: { edition: 'enterprise', licensed: true },
      enabled: ['sso'],
    });

    render(
      <FeaturesProvider>
        <StateProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('edition')).toHaveTextContent('enterprise')
    );
  });
});

describe('useFeature', () => {
  it('returns false while features are loading (fail-closed)', async () => {
    // Promise that never resolves during the test.
    mockGetFeatures.mockReturnValue(new Promise(() => {}));

    render(
      <FeaturesProvider>
        <Probe feature={FeatureName.SSO} />
      </FeaturesProvider>
    );

    expect(screen.getByTestId('probe')).toHaveTextContent('off');
  });
});

describe('FeatureGate', () => {
  it('renders children when the feature is enabled', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: ['sso'] });

    render(
      <FeaturesProvider>
        <FeatureGate feature={FeatureName.SSO}>
          <div data-testid="gated">visible</div>
        </FeatureGate>
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('gated')).toBeInTheDocument()
    );
  });

  it('renders fallback when the feature is disabled', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: [] });

    render(
      <FeaturesProvider>
        <FeatureGate
          feature={FeatureName.SSO}
          fallback={<div data-testid="fallback">hidden</div>}
        >
          <div data-testid="gated">visible</div>
        </FeatureGate>
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('fallback')).toBeInTheDocument()
    );
    expect(screen.queryByTestId('gated')).not.toBeInTheDocument();
  });

  it('renders fallback during initial loading (fail-closed)', async () => {
    // Never-resolving promise keeps the provider in loading state.
    let resolveFn: (value: unknown) => void = () => {};
    mockGetFeatures.mockReturnValue(
      new Promise(resolve => {
        resolveFn = resolve;
      })
    );

    render(
      <FeaturesProvider>
        <FeatureGate
          feature={FeatureName.SSO}
          fallback={<div data-testid="fallback">hidden</div>}
        >
          <div data-testid="gated">visible</div>
        </FeatureGate>
      </FeaturesProvider>
    );

    expect(screen.getByTestId('fallback')).toBeInTheDocument();
    expect(screen.queryByTestId('gated')).not.toBeInTheDocument();

    // Resolve so React can unmount cleanly without the unresolved promise leaking.
    await act(async () => {
      resolveFn({ license: LICENSE, enabled: [] });
    });
  });

  it('renders null when no fallback is provided and feature is disabled', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: [] });

    const { container } = render(
      <FeaturesProvider>
        <FeatureGate feature={FeatureName.SSO}>
          <div data-testid="gated">visible</div>
        </FeatureGate>
      </FeaturesProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId('gated')).not.toBeInTheDocument();
    });
    // Body contains no gated content.
    expect(container.textContent).toBe('');
  });
});
