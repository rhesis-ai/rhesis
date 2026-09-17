import { PageLayout } from '@/components/layout/PageLayout';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import SettingsTabs from './components/SettingsTabs';

/**
 * Server component: fetches the current user's settings so the profile,
 * security and notification cards render with content already in place -- no
 * full-page spinner on first load. Every section reads `userSettings`
 * optionally, so a failed fetch degrades to empty fields rather than an error
 * page.
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
      description="Manage your profile, account and notifications."
      breadcrumbs={breadcrumbs}
    >
      <SettingsTabs userSettings={userSettings} />
    </PageLayout>
  );
}
