import React from 'react';
import { render, screen, waitFor, act } from '@/test-utils';
import '@testing-library/jest-dom';

import { FeatureName } from '@/constants/features';
import {
  FeatureGate,
  FeaturesProvider,
  useFeature,
  useFeaturesState,
  useIsLocalMode,
  usePlan,
  useRhesisKeyEnabled,
} from '../FeaturesContext';

const mockGetFeatures = jest.fn();

const AUTHENTICATED_SESSION = {
  data: { session_token: 'test-token', user: { id: 'user-1' } },
  status: 'authenticated',
};

// Mutable so individual tests can simulate an unauthenticated/loading session.
// Named with the `mock` prefix so jest.mock's factory may reference it.
let mockSession: { data: unknown; status: string } = AUTHENTICATED_SESSION;

jest.mock('next-auth/react', () => ({
  useSession: () => mockSession,
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
  mockSession = AUTHENTICATED_SESSION;
});

function Probe({ feature }: { feature: FeatureName }) {
  const enabled = useFeature(feature);
  return <div data-testid="probe">{enabled ? 'on' : 'off'}</div>;
}

function PlanProbe() {
  const plan = usePlan();
  return <div data-testid="plan">{plan?.name ?? 'none'}</div>;
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

describe('FeaturesProvider server-seeded initialFeatures', () => {
  it('reports loading=false and the seeded feature synchronously, with no fetch', () => {
    // Never-resolving promise: if the provider fell back to fetching instead
    // of trusting the seed, `loading` would stay true forever and this
    // assertion would time out rather than pass synchronously.
    mockGetFeatures.mockReturnValue(new Promise(() => {}));

    render(
      <FeaturesProvider
        initialFeatures={{ license: LICENSE, enabled: ['sso'] }}
      >
        <Probe feature={FeatureName.SSO} />
        <StateProbe />
      </FeaturesProvider>
    );

    expect(screen.getByTestId('probe')).toHaveTextContent('on');
    expect(screen.getByTestId('loading')).toHaveTextContent('false');
  });

  it('still exposes a feature absent from the seed as off', () => {
    mockGetFeatures.mockReturnValue(new Promise(() => {}));

    render(
      <FeaturesProvider initialFeatures={{ license: LICENSE, enabled: [] }}>
        <Probe feature={FeatureName.SSO} />
      </FeaturesProvider>
    );

    expect(screen.getByTestId('probe')).toHaveTextContent('off');
  });

  it('falls back to the normal client fetch when initialFeatures is null', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: ['sso'] });

    render(
      <FeaturesProvider initialFeatures={null}>
        <Probe feature={FeatureName.SSO} />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('probe')).toHaveTextContent('on')
    );
    expect(mockGetFeatures).toHaveBeenCalledTimes(1);
  });
});

describe('FeaturesProvider session gating', () => {
  it('stays fail-closed (loading) while the session is still resolving', () => {
    // While next-auth resolves the session there is no token, so the query is
    // disabled/idle (isLoading=false, data=undefined). The provider must report
    // loading=true rather than treating idle as "loaded, no features".
    mockSession = { data: null, status: 'loading' };
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: ['sso'] });

    render(
      <FeaturesProvider>
        <Probe feature={FeatureName.SSO} />
        <StateProbe />
      </FeaturesProvider>
    );

    expect(screen.getByTestId('probe')).toHaveTextContent('off');
    expect(screen.getByTestId('loading')).toHaveTextContent('true');
    expect(mockGetFeatures).not.toHaveBeenCalled();
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

function LocalModeProbe() {
  const isLocalMode = useIsLocalMode();
  return <div data-testid="local-mode">{String(isLocalMode)}</div>;
}

describe('useIsLocalMode', () => {
  it('returns true when the backend reports is_local', async () => {
    mockGetFeatures.mockResolvedValue({
      license: LICENSE,
      enabled: [],
      is_local: true,
    });

    render(
      <FeaturesProvider>
        <LocalModeProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('local-mode')).toHaveTextContent('true')
    );
  });

  it('defaults to false when is_local is absent (older backend)', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: [] });

    render(
      <FeaturesProvider>
        <LocalModeProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('local-mode')).toHaveTextContent('false')
    );
  });

  it('fails closed (false) while loading and on fetch error', async () => {
    mockGetFeatures.mockRejectedValue(new Error('boom'));

    render(
      <FeaturesProvider>
        <LocalModeProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('local-mode')).toHaveTextContent('false')
    );
  });
});

function RhesisKeyEnabledProbe() {
  const rhesisKeyEnabled = useRhesisKeyEnabled();
  return <div data-testid="rhesis-key-enabled">{String(rhesisKeyEnabled)}</div>;
}

describe('useRhesisKeyEnabled', () => {
  it('returns true when the backend reports rhesis_key_enabled', async () => {
    mockGetFeatures.mockResolvedValue({
      license: LICENSE,
      enabled: [],
      rhesis_key_enabled: true,
    });

    render(
      <FeaturesProvider>
        <RhesisKeyEnabledProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('rhesis-key-enabled')).toHaveTextContent('true')
    );
  });

  it('defaults to false when rhesis_key_enabled is absent (older backend)', async () => {
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: [] });

    render(
      <FeaturesProvider>
        <RhesisKeyEnabledProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('rhesis-key-enabled')).toHaveTextContent(
        'false'
      )
    );
  });

  it('fails closed (false) while loading and on fetch error', async () => {
    mockGetFeatures.mockRejectedValue(new Error('boom'));

    render(
      <FeaturesProvider>
        <RhesisKeyEnabledProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('rhesis-key-enabled')).toHaveTextContent(
        'false'
      )
    );
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

describe('usePlan', () => {
  const PLAN = { name: 'Team', is_paid: true, is_active: true };

  it('has the plan on first paint from the server seed, with no fetch', () => {
    // The point of carrying the plan on this response. A never-resolving fetch
    // stands in for the round trip: sourced from `GET /usage` instead, every
    // plan surface rendered blank until it came back, which is the flicker
    // this replaced.
    mockGetFeatures.mockReturnValue(new Promise(() => {}));

    render(
      <FeaturesProvider
        initialFeatures={{ license: LICENSE, enabled: [], plan: PLAN }}
      >
        <PlanProbe />
      </FeaturesProvider>
    );

    expect(screen.getByTestId('plan')).toHaveTextContent('Team');
    expect(mockGetFeatures).not.toHaveBeenCalled();
  });

  it('reports null when the backend response has no plan', async () => {
    // An older backend. Must read as "unknown" rather than being filled in
    // with a guessed free tier, which would prompt a paying org to upgrade.
    mockGetFeatures.mockResolvedValue({ license: LICENSE, enabled: [] });

    render(
      <FeaturesProvider>
        <PlanProbe />
      </FeaturesProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('plan')).toHaveTextContent('none')
    );
  });

  it('reports null while the plan is still loading', () => {
    mockGetFeatures.mockReturnValue(new Promise(() => {}));

    render(
      <FeaturesProvider>
        <PlanProbe />
      </FeaturesProvider>
    );

    expect(screen.getByTestId('plan')).toHaveTextContent('none');
  });
});
