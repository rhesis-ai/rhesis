'use client';

import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import AccessibilityModeCard from '@/components/common/AccessibilityModeCard';
import { getDeploymentBranding } from '@/config/branding';
import { useOrganization } from '@/contexts/OrganizationContext';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { writeUserSettingsCache } from '@/hooks/useUserSettings';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UserSettings } from '@/utils/api-client/interfaces/user';

interface AccessibilityPreferenceFormProps {
  userSettings?: UserSettings;
}

/**
 * Accessibility mode for this person only. It adds to the organization's
 * setting: where the organization or deployment turned it on, it stays on.
 */
export default function AccessibilityPreferenceForm({
  userSettings,
}: AccessibilityPreferenceFormProps) {
  const queryClient = useQueryClient();
  const userScope = useUserScope();
  const { organization } = useOrganization();

  const forcedByDeployment = getDeploymentBranding().accessibilityMode === true;
  const forcedByOrganization =
    organization?.organization_settings?.accessibility?.mode === true;
  const lockedReason = forcedByDeployment
    ? 'Turned on for this whole deployment.'
    : forcedByOrganization
      ? 'Turned on for your whole organization.'
      : undefined;

  const save = async (mode: boolean) => {
    const updated = await new ApiClientFactory()
      .getUsersClient()
      .updateUserSettings({ ui: { accessibility_mode: mode } });
    writeUserSettingsCache(queryClient, userScope, {
      ...(userSettings ?? updated),
      ...updated,
    });
  };

  return (
    <AccessibilityModeCard
      subtitle="Applies to you only, on top of your organization's setting."
      checked={userSettings?.ui?.accessibility_mode === true}
      onElsewhere={forcedByDeployment || forcedByOrganization}
      lockedReason={lockedReason}
      save={save}
    />
  );
}
