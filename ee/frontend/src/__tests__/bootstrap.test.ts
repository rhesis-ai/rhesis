/**
 * Smoke test for the EE frontend bootstrap.
 *
 * Verifies that calling `bootstrapEE()` registers the SSO section into
 * core's organization-settings registry. This is what gates whether
 * the `<SSOConfigForm>` actually appears on the settings page; if the
 * registration is silently broken the form would simply never render
 * with no obvious error.
 *
 * The test resets the registry before running so it sees a clean slate,
 * regardless of whether `apps/frontend/src/ee_bootstrap.ts` has been
 * pulled in by another module's side-effect import.
 */

// `bootstrap` -> `register.tsx` pulls in `<FeatureGate>` from core,
// which imports `next-auth/react`. The test never renders the
// component (only inspects the registry shape), so a no-op mock is
// enough and avoids Jest having to transform the `next-auth/react`
// ESM build during module evaluation.
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
}));

import {
  getOrgSettingsSections,
  resetOrgSettingsSections,
} from '@/lib/extension-registries';
import { bootstrapEE } from '../bootstrap';

describe('ee bootstrap', () => {
  beforeEach(() => {
    resetOrgSettingsSections();
  });

  it('registers the SSO section', () => {
    bootstrapEE();
    const sections = getOrgSettingsSections();
    const sso = sections.find(s => s.id === 'sso');
    expect(sso).toBeDefined();
    expect(sso?.title).toMatch(/single sign-on/i);
    expect(sso?.component).toBeDefined();
    // Section is a self-contained component: it owns its own
    // <FeatureGate> wrapping rather than the registry storing a
    // `feature` field.
    expect(typeof sso?.component).toBe('function');
  });

  it('registers the API Clients section', () => {
    bootstrapEE();
    const sections = getOrgSettingsSections();
    const apiClients = sections.find(s => s.id === 'api-clients');
    expect(apiClients).toBeDefined();
    expect(apiClients?.title).toMatch(/api clients/i);
    expect(typeof apiClients?.component).toBe('function');
  });

  it('orders API Clients after SSO', () => {
    // The two sections are conceptually paired (the API Clients
    // empty state instructs the operator to configure SSO first);
    // their relative order in the page is part of the contract.
    bootstrapEE();
    const sections = getOrgSettingsSections();
    const ssoIndex = sections.findIndex(s => s.id === 'sso');
    const apiIndex = sections.findIndex(s => s.id === 'api-clients');
    expect(ssoIndex).toBeGreaterThanOrEqual(0);
    expect(apiIndex).toBeGreaterThan(ssoIndex);
  });

  it('is idempotent (can be called multiple times safely)', () => {
    bootstrapEE();
    bootstrapEE();
    bootstrapEE();
    const ssoSections = getOrgSettingsSections().filter(s => s.id === 'sso');
    const apiSections = getOrgSettingsSections().filter(
      s => s.id === 'api-clients'
    );
    expect(ssoSections).toHaveLength(1);
    expect(apiSections).toHaveLength(1);
  });

  it('returns a stable reference across reads (no churn between calls)', () => {
    bootstrapEE();
    const a = getOrgSettingsSections();
    const b = getOrgSettingsSections();
    expect(a).toBe(b);
  });

  it('invalidates the cached reference when a new section registers', () => {
    bootstrapEE();
    const before = getOrgSettingsSections();
    resetOrgSettingsSections();
    bootstrapEE();
    const after = getOrgSettingsSections();
    expect(after).not.toBe(before);
  });
});
