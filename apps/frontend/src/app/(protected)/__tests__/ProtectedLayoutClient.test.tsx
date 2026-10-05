import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import { ProtectedLayoutClient } from '../ProtectedLayoutClient';
import type { FeaturesResponse } from '@/utils/api-client/features-client';

let mockPathname = '/tests';
let mockOrganizationId: string | null = 'org-1';

jest.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ refresh: jest.fn() }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1', organization_id: mockOrganizationId } },
    status: 'authenticated',
  }),
}));

// A hoisted function declaration, so the jest.mock factories below can use it.
function mockPassthrough({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

jest.mock('../error-boundary', () => ({
  __esModule: true,
  default: mockPassthrough,
}));
jest.mock('@/contexts/PermissionsContext', () => ({
  PermissionsProvider: mockPassthrough,
}));
jest.mock('@/contexts/UsageContext', () => ({
  UsageProvider: mockPassthrough,
}));
jest.mock('@/contexts/WebSocketContext', () => ({
  WebSocketProvider: mockPassthrough,
}));
jest.mock('@/contexts/NotificationsContext', () => ({
  NotificationsProvider: mockPassthrough,
}));
jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ projects: [{ id: 'p1' }], loading: false }),
}));
jest.mock('@/components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));
jest.mock('@/components/navigation/Sidebar', () => ({ Sidebar: () => null }));
jest.mock('@/components/auth/VerificationBanner', () => ({
  __esModule: true,
  default: () => <div data-testid="verification-banner" />,
}));
jest.mock('@/components/auth/SetPasswordBanner', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/components/auth/QuotaBanner', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/components/auth/TermsAcceptanceGate', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/components/common/NoProjectAccess', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/app/(protected)/models/components/ConnectModelStep', () => ({
  __esModule: true,
  default: () => <div data-testid="connect-model-step" />,
}));

function features(models_ready: boolean): FeaturesResponse {
  return {
    license: { edition: 'community', licensed: false },
    enabled: [],
    models_ready,
  };
}

function renderLayout(models_ready: boolean) {
  return render(
    <ProtectedLayoutClient
      initialFeatures={features(models_ready)}
      initialPermissions={null}
      initialTermsStatus={null}
    >
      <div data-testid="page">page</div>
    </ProtectedLayoutClient>
  );
}

beforeEach(() => {
  mockPathname = '/tests';
  mockOrganizationId = 'org-1';
});

describe('ProtectedLayoutClient model setup gate', () => {
  it('replaces the page, the shell and the banners when no model is ready', () => {
    renderLayout(false);

    expect(screen.getByTestId('connect-model-step')).toBeInTheDocument();
    expect(screen.queryByTestId('page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('app-shell')).not.toBeInTheDocument();
    expect(screen.queryByTestId('verification-banner')).not.toBeInTheDocument();
  });

  it('renders the app when a model is ready', () => {
    renderLayout(true);

    expect(screen.getByTestId('page')).toBeInTheDocument();
    expect(screen.getByTestId('app-shell')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
  });

  // Intended: the gate is hard, so a chromeless route gets the step too.
  it('replaces a chromeless route as well', () => {
    mockPathname = '/test-runs/run-1/compare';
    renderLayout(false);

    expect(screen.getByTestId('connect-model-step')).toBeInTheDocument();
    expect(screen.queryByTestId('page')).not.toBeInTheDocument();
  });

  it('leaves onboarding alone', () => {
    mockPathname = '/onboarding';
    renderLayout(false);

    expect(screen.getByTestId('page')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
  });

  it('leaves a user without an organization alone', () => {
    mockOrganizationId = null;
    renderLayout(false);

    expect(screen.getByTestId('page')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-model-step')).not.toBeInTheDocument();
  });
});
