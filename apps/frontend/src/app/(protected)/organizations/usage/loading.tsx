'use client';

import Box from '@mui/material/Box';
import { useSearchParams } from 'next/navigation';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { PageLayout } from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { noop } from '@/components/loading/TextPlaceholder';
import { useOrganization } from '@/contexts/OrganizationContext';
import {
  normalizeTabParam,
  TAB_KEYS,
  TAB_LABELS,
  USAGE_CRUMB,
  USAGE_DESCRIPTION,
  USAGE_TITLE,
} from './components/tabs';

/** The Usage page: header and tabs for real, the active tab's card with its
 *  figures pending. The organization's crumb is real once the organization
 *  context has it. */
export default function UsageLoading() {
  const activeKey = normalizeTabParam(useSearchParams().get('tab'));
  const activeTab = TAB_KEYS.indexOf(activeKey);
  const { organization } = useOrganization();

  return (
    <SkeletonMode>
      <PageLayout
        title={USAGE_TITLE}
        description={USAGE_DESCRIPTION}
        breadcrumbs={
          organization
            ? [
                {
                  label: organization.name || 'Organization',
                  href: '/organizations',
                },
                USAGE_CRUMB,
              ]
            : []
        }
        pendingCrumbs={organization ? 0 : 2}
      >
        <Box>
          <DetailTabNav
            tabs={TAB_KEYS.map(key => ({ key, label: TAB_LABELS[key] }))}
            activeIndex={activeTab}
            onChange={noop}
            aria-label="Usage detail tabs"
          />
          <DetailTabPanel
            value={activeTab}
            index={activeTab}
            prefix="usage-detail"
          >
            <SectionPlaceholder
              title={activeKey === 'timeline' ? 'Usage Over Time' : 'Usage'}
            />
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
