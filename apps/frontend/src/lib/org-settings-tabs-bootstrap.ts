/**
 * Core organization-settings tab registrations.
 *
 * EE features register their own tabs via `ee_bootstrap.ts`. Core-owned
 * tabs (Team, and any future MIT tabs) register here so
 * `OrganizationSettingsTabs` can merge them with the built-in Information
 * and Danger zone panels.
 */

import { registerOrgSettingsTab } from '@/lib/extension-registries';
import TeamTab from '@/app/(protected)/organizations/settings/components/TeamTab';

registerOrgSettingsTab({
  id: 'team',
  title: 'Team',
  order: 10,
  component: TeamTab,
});
