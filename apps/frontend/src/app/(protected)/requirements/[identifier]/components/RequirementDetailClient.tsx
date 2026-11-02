'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import { format } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import RequirementDetailTabs, {
  REQUIREMENT_TAB_KEYS,
  type RequirementTabKey,
} from './RequirementDetailTabs';
import RequirementSuggestionsFab from './RequirementSuggestionsFab';
import { SOURCES_CARD_ID } from './RequirementSourcesCard';
import type { RuleHintId } from './requirement-suggestions';
import { FabGroup } from '@/components/common/Fab';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface RequirementDetailClientProps {
  requirement: RequirementWithMetrics;
  identifier: string;
  initialLinkedTests?: TestDetail[];
}

export default function RequirementDetailClient({
  requirement: initialRequirement,
  identifier,
  initialLinkedTests,
}: RequirementDetailClientProps) {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Requirement.READ
  );
  const [requirement, setRequirement] =
    React.useState<RequirementWithMetrics>(initialRequirement);

  const { activeTab, handleTabChange } = useDetailTabNav(REQUIREMENT_TAB_KEYS);

  React.useEffect(() => {
    setRequirement(initialRequirement);
  }, [initialRequirement]);

  const goToTab = React.useCallback(
    (key: RequirementTabKey) =>
      handleTabChange(REQUIREMENT_TAB_KEYS.indexOf(key)),
    [handleTabChange]
  );

  const handleRuleAction = React.useCallback(
    (id: RuleHintId) => {
      if (id === 'no_metric') goToTab('linked-metrics');
      if (id === 'no_examples') goToTab('examples');
      if (id === 'no_source') {
        goToTab('basic');
        // After the tab has rendered its cards.
        requestAnimationFrame(() =>
          document
            .getElementById(SOURCES_CARD_ID)
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        );
      }
    },
    [goToTab]
  );

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="requirements" />;

  const title = requirement.name || `Requirement ${identifier}`;
  const breadcrumbs = [
    { label: 'Requirements', href: API_ENDPOINTS.requirements },
    ...(requirement.parent
      ? [
          {
            label: requirement.parent.name,
            href: `${API_ENDPOINTS.requirements}/${requirement.parent.id}`,
          },
        ]
      : []),
    { label: title, href: `${API_ENDPOINTS.requirements}/${identifier}` },
  ];

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: requirement.user?.name || '—' },
        {
          label: 'created on:',
          value: requirement.created_at
            ? format(new Date(requirement.created_at), 'dd/MM/yyyy')
            : '—',
        },
      ]}
    />
  );

  return (
    <PageLayout
      title={title}
      breadcrumbs={breadcrumbs}
      metadata={metadataStrip}
      actions={
        <FabGroup>
          <RequirementSuggestionsFab
            requirement={requirement}
            onUpdated={setRequirement}
            onRuleAction={handleRuleAction}
          />
        </FabGroup>
      }
    >
      <Box sx={{ flexGrow: 1 }}>
        <RequirementDetailTabs
          requirement={requirement}
          onUpdated={setRequirement}
          initialLinkedTests={initialLinkedTests}
          activeTab={activeTab}
          onTabChange={handleTabChange}
        />
      </Box>
    </PageLayout>
  );
}
