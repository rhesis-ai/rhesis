'use client';

import React from 'react';
import AccessibilityModeCard from '@/components/common/AccessibilityModeCard';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { getDeploymentBranding } from '@/config/branding';
import { useUserSettings } from '@/hooks/useUserSettings';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Organization } from '@/utils/api-client/interfaces/organization';

interface OrganizationAccessibilityFormProps {
  organization: Organization;
  onUpdate: () => void;
}

/** Accessibility mode for everyone in the organization. */
export default function OrganizationAccessibilityForm({
  organization,
  onUpdate,
}: OrganizationAccessibilityFormProps) {
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const { data: userSettings } = useUserSettings();
  const forcedByDeployment = getDeploymentBranding().accessibilityMode === true;

  const save = async (mode: boolean) => {
    await new ApiClientFactory()
      .getOrganizationsClient()
      .updateOrganizationSettings({ accessibility: { mode } });
    onUpdate();
  };

  return (
    <AccessibilityModeCard
      subtitle="Applies to everyone in the organization. Members can also turn it on just for themselves in their own preferences."
      checked={organization.organization_settings?.accessibility?.mode === true}
      onElsewhere={userSettings?.ui?.accessibility_mode === true}
      lockedReason={
        forcedByDeployment ? 'Turned on for this whole deployment.' : undefined
      }
      disabled={!canUpdateOrg}
      save={save}
    />
  );
}
