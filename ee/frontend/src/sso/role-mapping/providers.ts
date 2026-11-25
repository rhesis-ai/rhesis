/**
 * Identity provider wording. The list itself and the issuer detection live in
 * the backend (`ee/sso/providers.py`); this module only reads them.
 */

import type { ProviderInfo } from '../types';

/** Used until the catalog loads, and for an unknown key. */
export const GENERIC_PROVIDER: ProviderInfo = {
  key: 'oidc',
  name: 'identity provider',
  title: 'Other OIDC provider',
  supports_groups: true,
  groups_hint: '',
};

export function findProvider(
  catalog: ProviderInfo[],
  key: string | null | undefined
): ProviderInfo {
  return (
    catalog.find(p => p.key === key) ??
    catalog.find(p => p.key === GENERIC_PROVIDER.key) ??
    GENERIC_PROVIDER
  );
}

/** "Keycloak" in sentences, or "your identity provider" for a generic one. */
export function providerPhrase(p: ProviderInfo): string {
  return p.key === GENERIC_PROVIDER.key ? 'your identity provider' : p.name;
}
