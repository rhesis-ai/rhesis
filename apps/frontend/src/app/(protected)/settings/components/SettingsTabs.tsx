'use client';

import React, { useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import ProfileForm from './ProfileForm';
import SecuritySection from './SecuritySection';
import NotificationsForm from './NotificationsForm';
import PreferencesForm from './PreferencesForm';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'preferences', label: 'Preferences' },
  { id: 'notifications', label: 'Notifications' },
] as const;

const TAB_IDS = TABS.map(t => t.id);

interface SettingsTabsProps {
  userSettings?: UserSettings;
}

export default function SettingsTabs({ userSettings }: SettingsTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = useMemo(() => {
    const param = searchParams.get('tab');
    const idx = param ? TAB_IDS.indexOf(param as (typeof TAB_IDS)[number]) : -1;
    return idx >= 0 ? idx : 0;
  }, [searchParams]);

  const handleTabChange = useCallback(
    (newIndex: number) => {
      const key = TABS[newIndex]?.id;
      if (!key) return;
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const navTabs = TABS.map((tab, index) => ({
    key: tab.id,
    label: tab.label,
    id: `settings-tab-${index}`,
    'aria-controls': `settings-tabpanel-${index}`,
  }));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Settings sections"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="settings">
        <ProfileForm userSettings={userSettings} />
        <SecuritySection userSettings={userSettings} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="settings">
        <PreferencesForm userSettings={userSettings} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="settings">
        <NotificationsForm userSettings={userSettings} />
      </DetailTabPanel>
    </Box>
  );
}
