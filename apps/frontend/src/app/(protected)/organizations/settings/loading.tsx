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
import { getOrgSettingsTabs } from '@/lib/extension-registries';
import {
  activeTabIndex,
  mergeOrgSettingsTabs,
  ORG_SETTINGS_CRUMB,
  ORG_SETTINGS_DESCRIPTION,
  ORG_SETTINGS_TITLE,
} from './components/tabs';

/** Card titles of the built-in tabs; registered tabs get a neutral card. */
const TAB_CARDS: Record<string, readonly string[]> = {
  branding: ['Brand Identity', 'Favicon', 'Brand Font'],
  preferences: ['Currency', 'Accessibility'],
};

function TabCards({ tabId }: { tabId: string }) {
  if (tabId === 'information') {
    return (
      <>
        <SectionPlaceholder
          title="Basic Information"
          editable
          fields={[
            'Organization ID',
            'Organization Name',
            'Display Name',
            'Description',
            'Website',
            'Logo URL',
          ]}
        />
        <SectionPlaceholder
          title="Contact Information"
          editable
          fields={['Email', 'Phone', 'Address']}
        />
      </>
    );
  }
  const titles = TAB_CARDS[tabId];
  if (!titles) return <SectionPlaceholder />;
  return titles.map(title => <SectionPlaceholder key={title} title={title} />);
}

/** Organization settings: header and tabs for real (its tabs come from the
 *  same registry the page reads, so registered ones show too), the active
 *  tab's cards with their values pending. The organization's crumb is real
 *  once the organization context has it. */
export default function OrganizationSettingsLoading() {
  const param = useSearchParams().get('tab');
  const { organization } = useOrganization();
  const tabs = mergeOrgSettingsTabs(getOrgSettingsTabs());
  const activeTab = activeTabIndex(
    param,
    tabs.map(tab => tab.id)
  );

  return (
    <SkeletonMode>
      <PageLayout
        title={ORG_SETTINGS_TITLE}
        description={ORG_SETTINGS_DESCRIPTION}
        breadcrumbs={
          organization
            ? [
                {
                  label: organization.name || 'Organization',
                  href: '/organizations',
                },
                ORG_SETTINGS_CRUMB,
              ]
            : []
        }
        pendingCrumbs={organization ? 0 : 2}
      >
        <Box>
          <DetailTabNav
            tabs={tabs.map(tab => ({ key: tab.id, label: tab.label }))}
            activeIndex={activeTab}
            onChange={noop}
            aria-label="Organization settings sections"
          />
          <DetailTabPanel
            value={activeTab}
            index={activeTab}
            prefix="org-settings"
          >
            <TabCards tabId={tabs[activeTab]?.id ?? 'information'} />
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
