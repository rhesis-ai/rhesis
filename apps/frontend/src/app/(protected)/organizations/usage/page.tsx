'use client';

import { PageLayout } from '@/components/layout/PageLayout';
import { useOrganization } from '@/contexts/OrganizationContext';
import UsageDetailTabs from './components/UsageDetailTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

export default function OrganizationUsagePage() {
  // Same gate as Org Settings -- usage/quota data is org-scoped in exactly
  // the same way, and there's no separate usage/billing capability yet.
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Organization.READ
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
      <UsageDetailTabs />
    </PageLayout>
  );
}
