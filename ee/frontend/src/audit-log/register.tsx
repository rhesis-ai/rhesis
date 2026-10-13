/**
 * Audit log feature registration.
 *
 * Adds the Audit Log tab to organization settings, after API (order 40).
 * Like RBAC, the `<FeatureGate>` lives here: without `AUDIT_LOG` (no licence,
 * or a lapsed one) the tab shows the teaser instead of the log.
 */

import * as React from 'react';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { FeatureName } from '@/constants/features';
import { FeatureGate, useFeaturesState } from '@/contexts/FeaturesContext';
import { registerOrgSettingsTab } from '@/lib/extension-registries';
import AuditLogTeaser from './components/AuditLogTeaser';

export const AUDIT_LOG_TAB_ID = 'audit-log';

const AuditLogTab = React.lazy(() => import('./components/AuditLogTab'));

function Loading() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
      <CircularProgress size={24} />
    </Box>
  );
}

function AuditLogTabSection() {
  // FeatureGate is closed while /features loads; wait rather than flash the teaser.
  const { loading } = useFeaturesState();
  if (loading) return <Loading />;

  return (
    <FeatureGate feature={FeatureName.AUDIT_LOG} fallback={<AuditLogTeaser />}>
      <React.Suspense fallback={<Loading />}>
        <AuditLogTab />
      </React.Suspense>
    </FeatureGate>
  );
}

export function registerAuditLog(): void {
  registerOrgSettingsTab({
    id: AUDIT_LOG_TAB_ID,
    title: 'Audit Log',
    order: 50,
    component: AuditLogTabSection,
  });
}
