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
import UsageTab from '@/app/(protected)/organizations/settings/components/UsageTab';

registerOrgSettingsTab({
  id: 'team',
  title: 'Team',
  order: 10,
  component: TeamTab,
});

registerOrgSettingsTab({
  id: 'usage',
  title: 'Usage',
  // 25 sits between EE's Roles (20) and SSO (30) -- see ee/frontend/src/rbac/register.tsx
  // and ee/frontend/src/sso/register.tsx.
  order: 25,
  component: UsageTab,
});
