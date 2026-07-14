/**
 * Smoke test for the EE frontend bootstrap.
 *
 * Verifies that calling `bootstrapEE()` registers tabs (SSO, API, Roles)
 * and member role extensions into core's extension registries. These
 * registrations gate whether each EE surface actually appears; if one
 * is silently broken the UI would simply never render with no obvious
 * error.
 *
 * The test resets registries before each run so it sees a clean slate.
 */

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
}));

import {
  getOrgSettingsTabs,
  resetOrgSettingsTabs,
  getMemberRoleExtensions,
  resetMemberRoleExtensions,
  getTokenScopeExtensions,
  resetTokenScopeExtensions,
} from '@/lib/extension-registries';
import { bootstrapEE } from '../bootstrap';

describe('ee bootstrap', () => {
  beforeEach(() => {
    resetOrgSettingsTabs();
    resetMemberRoleExtensions();
    resetTokenScopeExtensions();
  });

  it('registers the SSO tab', () => {
    bootstrapEE();
    const tabs = getOrgSettingsTabs();
    const sso = tabs.find(t => t.id === 'sso');
    expect(sso).toBeDefined();
    expect(sso?.title).toBe('SSO');
    expect(typeof sso?.component).toBe('function');
  });

  it('registers the API tab', () => {
    bootstrapEE();
    const tabs = getOrgSettingsTabs();
    const api = tabs.find(t => t.id === 'api');
    expect(api).toBeDefined();
    expect(api?.title).toBe('API');
    expect(typeof api?.component).toBe('function');
  });

  it('registers the Roles tab', () => {
    bootstrapEE();
    const tabs = getOrgSettingsTabs();
    const roles = tabs.find(t => t.id === 'roles');
    expect(roles).toBeDefined();
    expect(roles?.title).toBe('Roles');
    expect(typeof roles?.component).toBe('function');
  });

  it('orders tabs: Roles < SSO < API', () => {
    bootstrapEE();
    const tabs = getOrgSettingsTabs();
    const ssoOrder = tabs.find(t => t.id === 'sso')?.order ?? -1;
    const apiOrder = tabs.find(t => t.id === 'api')?.order ?? -1;
    const rolesOrder = tabs.find(t => t.id === 'roles')?.order ?? -1;
    expect(rolesOrder).toBeLessThan(ssoOrder);
    expect(ssoOrder).toBeLessThan(apiOrder);
  });

  it('registers member role extension components', () => {
    bootstrapEE();
    const ext = getMemberRoleExtensions();
    expect(ext.OrgRoleCell).toBeDefined();
    expect(ext.ProjectRoleCell).toBeDefined();
    expect(ext.AddMemberRoleField).toBeDefined();
    expect(ext.assignProjectMemberRole).toBeDefined();
    expect(typeof ext.assignProjectMemberRole).toBe('function');
  });

  it('registers token scope extension', () => {
    bootstrapEE();
    const ext = getTokenScopeExtensions();
    expect(ext.TokenScopeField).toBeDefined();
    expect(typeof ext.TokenScopeField).toBe('function');
  });

  it('is idempotent (can be called multiple times safely)', () => {
    bootstrapEE();
    bootstrapEE();
    bootstrapEE();
    const tabs = getOrgSettingsTabs();
    expect(tabs.filter(t => t.id === 'sso')).toHaveLength(1);
    expect(tabs.filter(t => t.id === 'api')).toHaveLength(1);
    expect(tabs.filter(t => t.id === 'roles')).toHaveLength(1);
  });

  it('returns a stable reference across reads (no churn between calls)', () => {
    bootstrapEE();
    const a = getOrgSettingsTabs();
    const b = getOrgSettingsTabs();
    expect(a).toBe(b);
  });

  it('invalidates the cached reference when a reset + re-register occurs', () => {
    bootstrapEE();
    const before = getOrgSettingsTabs();
    resetOrgSettingsTabs();
    bootstrapEE();
    const after = getOrgSettingsTabs();
    expect(after).not.toBe(before);
  });
});
