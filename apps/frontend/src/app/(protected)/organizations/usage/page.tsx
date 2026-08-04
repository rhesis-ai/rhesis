'use client';

import { PageLayout } from '@/components/layout/PageLayout';
import { useOrganization } from '@/contexts/OrganizationContext';
import { UsageProvider } from '@/contexts/UsageContext';
import UsageDetailTabs from './components/UsageDetailTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

export default function OrganizationUsagePage() {
  // Not Organization.READ: every Viewer holds that one for basic org
  // context, so it would not gate anything. Usage is billing data, so it
  // has its own admin-only capability, matching what the backend now
  // requires on GET /usage.
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Usage.READ
  );
  const { organization } = useOrganization();

  const organizationName = organization?.name || 'Organization';

  const breadcrumbs = [
    { label: organizationName, href: '/organizations' },
    { label: 'Usage', href: '/organizations/usage' },
  ];

  const pageHeader = {
    title: 'Usage',
    description:
      "Track your organization's metered resource consumption against its plan limits.",
    breadcrumbs,
  };

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="usage" />;

  return (
    <PageLayout {...pageHeader}>
      {/*
        Mounted here rather than in the protected layout: this is the only
        page that reads usage, and `GET /usage` costs a license lookup plus
        a counting query per stock resource -- not worth paying on every
        protected navigation. Inside the `canRead` guard, so a user without
        the capability never fires a request that would only 403.
      */}
      <UsageProvider>
        <UsageDetailTabs />
      </UsageProvider>
    </PageLayout>
  );
}
