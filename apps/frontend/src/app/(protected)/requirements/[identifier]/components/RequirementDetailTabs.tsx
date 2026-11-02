'use client';

import React from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import GridBadge from '@/components/common/GridBadge';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import RequirementBasicInfo from './RequirementBasicInfo';
import RequirementExamples from './RequirementExamples';
import RequirementLinkedMetrics from './RequirementLinkedMetrics';
import RequirementLinkedTests from './RequirementLinkedTests';
import RequirementLinkedRequirements from './RequirementLinkedRequirements';

export const REQUIREMENT_TAB_KEYS = [
  'basic',
  'examples',
  'linked-metrics',
  'linked-tests',
  'linked-requirements',
] as const;

export type RequirementTabKey = (typeof REQUIREMENT_TAB_KEYS)[number];

const NAV_LABELS: Record<RequirementTabKey, string> = {
  basic: 'Basic Information',
  examples: 'Examples',
  'linked-metrics': 'Linked Metrics',
  'linked-tests': 'Linked Tests',
  'linked-requirements': 'Linked Requirements',
};

/** Parent (if any) plus children: the rows of the Linked Requirements tab. */
export function linkedRequirementCount(
  requirement: Pick<RequirementWithMetrics, 'parent' | 'children_count'>
): number {
  return (requirement.children_count ?? 0) + (requirement.parent ? 1 : 0);
}

interface RequirementDetailTabsProps {
  requirement: RequirementWithMetrics;
  onUpdated: (updated: RequirementWithMetrics) => void;
  initialLinkedTests?: TestDetail[];
  activeTab: number;
  onTabChange: (index: number) => void;
}

export default function RequirementDetailTabs({
  requirement,
  onUpdated,
  initialLinkedTests,
  activeTab,
  onTabChange,
}: RequirementDetailTabsProps) {
  const counts: Partial<Record<RequirementTabKey, number>> = {
    examples: requirement.examples_count ?? 0,
    'linked-metrics': requirement.metrics?.length ?? 0,
    'linked-tests': requirement.test_counts?.total ?? 0,
    'linked-requirements': linkedRequirementCount(requirement),
  };

  const navTabs = REQUIREMENT_TAB_KEYS.map((key, index) => {
    const count = counts[key];
    return {
      key,
      label: NAV_LABELS[key],
      ...(count !== undefined && {
        badge: <GridBadge label={String(count)} />,
      }),
      id: `requirement-detail-tab-${index}`,
      'aria-controls': `requirement-detail-tabpanel-${index}`,
    };
  });

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={onTabChange}
        aria-label="Requirement detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="requirement-detail">
        <RequirementBasicInfo requirement={requirement} onUpdated={onUpdated} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="requirement-detail">
        <RequirementExamples requirement={requirement} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="requirement-detail">
        <RequirementLinkedMetrics requirement={requirement} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="requirement-detail">
        <RequirementLinkedTests
          requirement={requirement}
          initialTests={initialLinkedTests}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={4} prefix="requirement-detail">
        <RequirementLinkedRequirements
          requirement={requirement}
          onUpdated={onUpdated}
        />
      </DetailTabPanel>
    </Box>
  );
}
