'use client';

/**
 * Context that pages publish to extension sections.
 *
 * Why a context instead of props? The `OrgSettingsSection` registry
 * stores a `ComponentType` with no props. That keeps the registry
 * contract about *identity* (id, title, component) and out of the
 * business of plumbing data, so the next EE feature that needs
 * different data does not force a contract change on every existing
 * section. Sections call `useOrgSettings()` to reach the data the
 * settings page exposes.
 *
 * Mirror of how Stripe Apps, VS Code contributions, and other
 * extension systems work: the host publishes a context; extensions
 * reach for what they need.
 */

import * as React from 'react';
import type { Organization } from '@/utils/api-client/interfaces/organization';

export interface OrgSettingsContextValue {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

const OrgSettingsContext = React.createContext<OrgSettingsContextValue | null>(
  null
);

export function OrgSettingsProvider({
  value,
  children,
}: {
  value: OrgSettingsContextValue;
  children: React.ReactNode;
}) {
  return (
    <OrgSettingsContext.Provider value={value}>
      {children}
    </OrgSettingsContext.Provider>
  );
}

/**
 * Hook used by extension sections rendered on the organization
 * settings page. Throws if used outside the provider so a missing
 * mount point fails loudly during development rather than silently
 * passing `undefined` around.
 */
export function useOrgSettings(): OrgSettingsContextValue {
  const value = React.useContext(OrgSettingsContext);
  if (value === null) {
    throw new Error(
      'useOrgSettings must be used inside <OrgSettingsProvider>. This ' +
        'hook is for extension sections rendered by the organization ' +
        'settings page.'
    );
  }
  return value;
}
