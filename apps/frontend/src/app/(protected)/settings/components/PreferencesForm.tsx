'use client';

import React, { useState } from 'react';
import { Box, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { SectionCard } from '@/components/common/SectionCard';
import CurrencySelect, {
  FOLLOW_ORGANIZATION,
} from '@/components/common/CurrencySelect';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCurrency } from '@/contexts/CurrencyContext';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { writeUserSettingsCache } from '@/hooks/useUserSettings';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { BASE_CURRENCY, type Currency } from '@/utils/money';
import type { UserSettings } from '@/utils/api-client/interfaces/user';

interface PreferencesFormProps {
  userSettings?: UserSettings;
}

/**
 * How this person wants costs shown, whatever the organization chose.
 *
 * Deliberately the same card, the same select label and the same explanation as
 * the organization one in organizations/settings/components/OrganizationCurrencyForm.
 * Only the sentence saying whose setting it is differs.
 *
 * Writes straight through the settings cache rather than invalidating and
 * refreshing, so the figures across the app change as the select closes
 * instead of blanking and coming back.
 */
export default function PreferencesForm({
  userSettings,
}: PreferencesFormProps) {
  const queryClient = useQueryClient();
  const userScope = useUserScope();
  const notifications = useNotifications();
  const { rates, organizationCurrency, userCurrency } = useCurrency();

  const [saving, setSaving] = useState(false);

  const inherited = organizationCurrency ?? BASE_CURRENCY;
  const value = userCurrency ?? FOLLOW_ORGANIZATION;

  const handleChange = async (next: Currency | typeof FOLLOW_ORGANIZATION) => {
    const currency = next === FOLLOW_ORGANIZATION ? null : next;
    setSaving(true);
    try {
      const updated = await new ApiClientFactory()
        .getUsersClient()
        .updateUserSettings({ localization: { currency } });
      writeUserSettingsCache(queryClient, userScope, {
        ...(userSettings ?? updated),
        ...updated,
      });
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
      subtitle="The currency costs are shown in, across traces and test runs. This applies to you only, and overrides the organization's default."
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <CurrencySelect
          label="Currency"
          value={value}
          onChange={handleChange}
          rates={rates}
          disabled={saving}
          inheritLabel={`Use the organization's currency (${inherited})`}
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
