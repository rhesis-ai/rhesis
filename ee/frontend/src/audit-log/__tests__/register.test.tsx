/**
 * The Audit Log settings tab: registration, the licence gate and its teaser,
 * and the `audit_log:read` check.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  getOrgSettingsTabs,
  resetOrgSettingsTabs,
} from '@/lib/extension-registries';
import { AUDIT_LOG_TAB_ID, registerAuditLog } from '../register';

const featuresState = { loading: false, enabled: new Set<string>() };
let plan: { name: string; is_paid: boolean; is_active: boolean } | null = null;
let canRead = { allowed: true, loading: false };

jest.mock('@/contexts/FeaturesContext', () => ({
  useFeaturesState: () => featuresState,
  usePlan: () => plan,
  FeatureGate: ({
    feature,
    fallback,
    children,
  }: {
    feature: string;
    fallback: React.ReactNode;
    children: React.ReactNode;
  }) => <>{featuresState.enabled.has(feature) ? children : fallback}</>,
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => canRead.allowed,
  useCanWithStatus: () => canRead,
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('../components/AuditEventsGrid', () => ({
  __esModule: true,
  default: () => <div data-testid="audit-events-grid" />,
}));

function renderTab() {
  const tab = getOrgSettingsTabs().find(t => t.id === AUDIT_LOG_TAB_ID);
  if (!tab) throw new Error('audit log tab not registered');
  const Component = tab.component;
  return render(<Component />);
}

beforeEach(() => {
  resetOrgSettingsTabs();
  registerAuditLog();
  featuresState.loading = false;
  featuresState.enabled = new Set();
  plan = null;
  canRead = { allowed: true, loading: false };
});

describe('registerAuditLog', () => {
  it('registers the tab after API', () => {
    const tab = getOrgSettingsTabs().find(t => t.id === AUDIT_LOG_TAB_ID);
    expect(tab?.title).toBe('Audit Log');
    const api = getOrgSettingsTabs().find(t => t.id === 'api');
    expect(tab?.order).toBeGreaterThan(api?.order ?? 40);
  });

  it('waits for /features instead of flashing the teaser', () => {
    featuresState.loading = true;
    renderTab();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /enterprise/i })
    ).not.toBeInTheDocument();
  });

  it('shows the teaser without a licence', () => {
    plan = { name: 'Free', is_paid: false, is_active: true };
    renderTab();
    expect(
      screen.getByText('See who changed what, and when')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Learn about Enterprise' })
    ).toBeInTheDocument();
  });

  it('tells a lapsed licence apart from no licence', () => {
    plan = { name: 'Enterprise (expired)', is_paid: true, is_active: false };
    renderTab();
    expect(
      screen.getByText('The audit log needs an active Enterprise licence')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Renew Enterprise' })
    ).toBeInTheDocument();
  });

  it('keeps the teaser copy to what v1 promises', () => {
    renderTab();
    const text = document.body.textContent ?? '';
    expect(text).toContain('Append-only');
    expect(text).not.toMatch(/hash|chain|verify|tamper|lock(ed|out)/i);
  });

  it('shows the events with the feature and audit_log:read', async () => {
    featuresState.enabled = new Set(['audit_log']);
    renderTab();
    expect(await screen.findByTestId('audit-events-grid')).toBeInTheDocument();
    expect(
      screen.getByText(
        /Entries are append-only and cannot be edited or deleted/
      )
    ).toBeInTheDocument();
  });

  it('denies a user without audit_log:read', async () => {
    featuresState.enabled = new Set(['audit_log']);
    canRead = { allowed: false, loading: false };
    renderTab();
    expect(await screen.findByText('Access denied')).toBeInTheDocument();
    expect(screen.queryByTestId('audit-events-grid')).not.toBeInTheDocument();
  });
});
