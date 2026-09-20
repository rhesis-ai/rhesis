'use client';

import React, { useState } from 'react';
import { Box, Typography } from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import CurrencySelect from '@/components/common/CurrencySelect';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useCurrency } from '@/contexts/CurrencyContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { BASE_CURRENCY, isCurrency, type Currency } from '@/utils/money';
import { Organization } from '@/utils/api-client/interfaces/organization';

interface OrganizationCurrencyFormProps {
  organization: Organization;
  onUpdate: () => void;
}

/**
 * The currency everyone in the organization sees costs in, unless they have
 * chosen their own in their personal settings.
 *
 * Deliberately the same card, the same select label and the same explanation as
 * the personal one in settings/components/PreferencesForm. Only the sentence
 * saying whose setting it is differs, because that is the only real difference.
 */
export default function OrganizationCurrencyForm({
  organization,
  onUpdate,
}: OrganizationCurrencyFormProps) {
  const notifications = useNotifications();
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const { rates } = useCurrency();
  const [saving, setSaving] = useState(false);

  const stored = organization.organization_settings?.display?.currency;
  const value: Currency = isCurrency(stored) ? stored : BASE_CURRENCY;

  const handleChange = async (next: string) => {
    if (!isCurrency(next) || next === value) return;
    setSaving(true);
    try {
      await new ApiClientFactory()
        .getOrganizationsClient()
        .updateOrganizationSettings({ display: { currency: next } });
      onUpdate();
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Could not save the currency',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard
      title="Currency"
      subtitle="The currency costs are shown in, across traces and test runs. This is the default for everyone in the organization, and anyone can override it in their own preferences."
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <CurrencySelect
          label="Currency"
          value={value}
          onChange={handleChange}
          rates={rates}
          disabled={saving || !canUpdateOrg}
        />
        <Typography variant="body2" color="text.secondary">
          Costs are recorded in {BASE_CURRENCY} and converted at the daily
          European Central Bank reference rate. This changes how costs are
          shown, not what was spent.
        </Typography>
      </Box>
    </SectionCard>
  );
}
