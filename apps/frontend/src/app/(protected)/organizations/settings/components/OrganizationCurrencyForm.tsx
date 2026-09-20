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

interface DisplayCurrencyFormProps {
  organization: Organization;
  onUpdate: () => void;
}

/**
 * The currency everyone in the organization sees costs in, unless they have
 * chosen their own in their personal settings.
 */
export default function DisplayCurrencyForm({
  organization,
  onUpdate,
}: DisplayCurrencyFormProps) {
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
      subtitle="How costs are shown to everyone here, unless they pick their own in their personal settings."
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <CurrencySelect
          label="Organization currency"
          value={value}
          onChange={handleChange}
          rates={rates}
          disabled={saving || !canUpdateOrg}
        />
        <Typography variant="body2" color="text.secondary">
          Costs are recorded in {BASE_CURRENCY} and converted at the daily
          European Central Bank reference rate. This changes how they are
          displayed, not what was spent.
        </Typography>
      </Box>
    </SectionCard>
  );
}
