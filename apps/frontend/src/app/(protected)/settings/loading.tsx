'use client';

import Box from '@mui/material/Box';
import { useSearchParams } from 'next/navigation';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { PageLayout } from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { noop } from '@/components/loading/TextPlaceholder';
import {
  activeTabIndex,
  CARD_HEADINGS,
  SETTINGS_HEADER,
  TABS,
} from './components/tabs';

/** The cards each tab opens with; their values wait for the user's
 *  settings. */
function TabCards({ tab }: { tab: (typeof TABS)[number]['id'] }) {
  if (tab === 'preferences') {
    return (
      <>
        <SectionPlaceholder {...CARD_HEADINGS.currency} />
        <SectionPlaceholder {...CARD_HEADINGS.accessibility} />
      </>
    );
  }
  if (tab === 'notifications') {
    return <SectionPlaceholder {...CARD_HEADINGS.emails} />;
  }
  return (
    <>
      <SectionPlaceholder title="Account" fields={['Email', 'Password']} />
      <SectionPlaceholder
        title="Personal Information"
        editable
        fields={['First Name', 'Last Name', 'Display Name', 'Picture URL']}
      />
      <SectionPlaceholder title="Password" />
    </>
  );
}

/** The Settings page: header and tabs for real, the active tab's cards with
 *  their values pending. */
export default function SettingsLoading() {
  const activeTab = activeTabIndex(useSearchParams().get('tab'));
  return (
    <SkeletonMode>
      <PageLayout {...SETTINGS_HEADER}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <DetailTabNav
            tabs={TABS.map(tab => ({ key: tab.id, label: tab.label }))}
            activeIndex={activeTab}
            onChange={noop}
            aria-label="Settings sections"
          />
          <DetailTabPanel value={activeTab} index={activeTab} prefix="settings">
            <TabCards tab={TABS[activeTab].id} />
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
