import { Box } from '@mui/material';
import { PAGE_SECTION_GAP } from '@/styles/theme-constants';
import { PageLayout } from '@/components/layout/PageLayout';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import ProfileForm from './components/ProfileForm';
import SecuritySection from './components/SecuritySection';

/**
 * Server component: fetches the current user's settings so the profile and
 * security cards render with content already in place -- no full-page
 * spinner on first load. Both sections read `userSettings` optionally, so a
 * failed fetch degrades to empty fields rather than an error page.
 */
export default async function SettingsPage() {
  await requireSession();

  let userSettings: UserSettings | undefined;

  try {
    const factory = await createServerApiFactory();
    userSettings = await factory.getUsersClient().getUserSettings();
  } catch (err) {
    console.warn('[settings] failed to prefetch user settings:', err);
  }

  const breadcrumbs = [{ label: 'Settings', href: '/settings' }];

  return (
    <PageLayout
      title="Settings"
      description="Manage your profile and account."
      breadcrumbs={breadcrumbs}
    >
      <Box
        sx={{ display: 'flex', flexDirection: 'column', gap: PAGE_SECTION_GAP }}
      >
        <ProfileForm userSettings={userSettings} />
        <SecuritySection userSettings={userSettings} />
      </Box>
    </PageLayout>
  );
}
