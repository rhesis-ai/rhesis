/**
 * SSO feature registration.
 *
 * Plugs the SSO settings section into core's organization-settings
 * registry. Each EE feature has a sibling `register.ts(x)` so
 * `bootstrap.ts` stays a one-line list of feature registrations and
 * adding the next feature is a self-contained edit.
 *
 * Why lazy?
 * ---------
 * The SSO form is ~500 lines and pulls in MUI icons. Lazy-loading
 * keeps it out of the main client chunk for orgs without SSO licensed
 * (or that simply never visit the settings page), trading a tiny
 * loading state for measurable bundle savings.
 *
 * Why is `<FeatureGate>` here and not in the page?
 * ------------------------------------------------
 * The registry contract is about identity (id, title, component); EE
 * owns its own gating end-to-end so core's settings page does not need
 * a `feature` field in the section type.
 */

import * as React from 'react';
import { Alert, Box, CircularProgress } from '@mui/material';
import { FeatureName } from '@/constants/features';
import { FeatureGate, useFeatureWarning } from '@/contexts/FeaturesContext';
import { registerOrgSettingsTab } from '@/lib/extension-registries';
import { SectionCard } from '@/components/common/SectionCard';
import SSOEmptyState from './components/SSOEmptyState';

const SSOConfigForm = React.lazy(() => import('./components/SSOConfigForm'));

function SSOSection() {
  const warning = useFeatureWarning(FeatureName.SSO);

  return (
    <FeatureGate feature={FeatureName.SSO} fallback={<SSOEmptyState />}>
      {warning && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {warning}
        </Alert>
      )}
      <React.Suspense
        fallback={
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={24} />
          </Box>
        }
      >
        <SectionCard title="Single Sign-On (SSO)">
          <SSOConfigForm />
        </SectionCard>
      </React.Suspense>
    </FeatureGate>
  );
}

export function registerSSO(): void {
  registerOrgSettingsTab({
    id: 'sso',
    title: 'SSO',
    order: 30,
    component: SSOSection,
  });
}
