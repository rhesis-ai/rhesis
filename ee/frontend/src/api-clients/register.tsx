/**
 * API Clients feature registration.
 *
 * Mirror of `ee/frontend/src/sso/register.tsx`. Plugs the API Clients
 * settings section into core's organization-settings registry.
 *
 * The component is `React.lazy()`-loaded because the section pulls in
 * MUI Table primitives that aren't otherwise on the settings page;
 * orgs that never visit the section don't pay for that JS. The
 * load runs only when the section actually renders, which itself
 * only happens after the FeatureGate confirms the org has the
 * feature enabled.
 *
 * Section ordering
 * ----------------
 * `order: 110` puts API Clients immediately after SSO (which uses
 * 100). Keeping them adjacent is intentional -- the API Clients
 * section's empty state tells the operator to configure SSO first,
 * and surrounding the two sections groups them in the page's
 * reading order.
 */

import * as React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { FeatureName } from '@/constants/features';
import { FeatureGate } from '@/contexts/FeaturesContext';
import { registerOrgSettingsTab } from '@/lib/extension-registries';
import ApiClientsEmptyState from './components/ApiClientsEmptyState';

const ApiClientsSection = React.lazy(
  () => import('./components/ApiClientsSection')
);

function ApiClientsSectionGate() {
  return (
    <FeatureGate
      feature={FeatureName.API_CLIENTS}
      fallback={<ApiClientsEmptyState />}
    >
      <React.Suspense
        fallback={
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={24} />
          </Box>
        }
      >
        <ApiClientsSection />
      </React.Suspense>
    </FeatureGate>
  );
}

export function registerApiClients(): void {
  registerOrgSettingsTab({
    id: 'api',
    title: 'API',
    order: 60,
    component: ApiClientsSectionGate,
  });
}
