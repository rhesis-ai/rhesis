import { Box } from '@mui/material';
import { PAGE_SECTION_GAP } from '@/styles/theme-constants';
import { PageLayout } from '@/components/layout/PageLayout';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import ProfileForm from './components/ProfileForm';
import SecuritySection from './components/SecuritySection';

export default async function SettingsPage() {
  await requireSession();

  const factory = await createServerApiFactory();
  const userSettings = await factory.getUsersClient().getUserSettings();

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
