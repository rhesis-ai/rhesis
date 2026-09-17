'use client';

import React, { useCallback, useState } from 'react';
import {
  Box,
  CircularProgress,
  FormControlLabel,
  Switch,
  Typography,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  EmailNotificationSettings,
  UserSettings,
} from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { userSettingsKeys } from '@/constants/query-keys';
import { SectionCard } from '@/components/common/SectionCard';

interface NotificationsFormProps {
  userSettings?: UserSettings;
}

type EmailPreference = keyof EmailNotificationSettings;

const EMAIL_TOGGLES: { key: EmailPreference; label: string; help: string }[] = [
  {
    key: 'job_completion',
    label: 'Job completion',
    help: 'Test runs, test set generation, and Garak import and sync.',
  },
  {
    key: 'task_assignment',
    label: 'Task assignments',
    help: 'When someone assigns a task to you.',
  },
];

/** Unset reads as on, matching how the backend treats a preference nobody has touched. */
function isOn(
  settings: UserSettings | undefined,
  key: EmailPreference
): boolean {
  return settings?.notifications?.email?.[key] !== false;
}

export default function NotificationsForm({
  userSettings,
}: NotificationsFormProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const userScope = useUserScope();
  const notifications = useNotifications();

  const [email, setEmail] = useState<Record<EmailPreference, boolean>>({
    job_completion: isOn(userSettings, 'job_completion'),
    task_assignment: isOn(userSettings, 'task_assignment'),
  });
  const [saving, setSaving] = useState<EmailPreference | null>(null);

  const handleToggle = useCallback(
    async (key: EmailPreference, checked: boolean) => {
      const previous = email;
      setEmail(prev => ({ ...prev, [key]: checked }));
      setSaving(key);

      try {
        await new ApiClientFactory()
          .getUsersClient()
          .updateUserSettings({ notifications: { email: { [key]: checked } } });

        queryClient.invalidateQueries({
          queryKey: userSettingsKeys.all(userScope),
        });
        router.refresh();
      } catch (err: unknown) {
        setEmail(previous);
        notifications.show(
          err instanceof Error
            ? err.message
            : 'Failed to update notification settings',
          { severity: 'error' }
        );
      } finally {
        setSaving(null);
      }
    },
    [email, notifications, queryClient, router, userScope]
  );

  return (
    <SectionCard
      title="Email notifications"
      subtitle="Choose which emails to receive. The matching in-app notifications keep coming either way."
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {EMAIL_TOGGLES.map(toggle => (
          <FormControlLabel
            key={toggle.key}
            sx={{ ml: 0, alignItems: 'flex-start', gap: 1.5 }}
            control={
              <Switch
                checked={email[toggle.key]}
                disabled={saving !== null}
                onChange={e => handleToggle(toggle.key, e.target.checked)}
                sx={{ mt: 0.25 }}
                inputProps={{ 'aria-label': toggle.label }}
              />
            }
            label={
              <Box component="span" sx={{ display: 'block' }}>
                <Box
                  component="span"
                  sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                >
                  <Typography variant="body1" component="span">
                    {toggle.label}
                  </Typography>
                  {saving === toggle.key && <CircularProgress size={14} />}
                </Box>
                <Typography
                  variant="body2"
                  component="span"
                  sx={{
                    display: 'block',
                    color: theme => theme.palette.greyscale.body,
                  }}
                >
                  {toggle.help}
                </Typography>
              </Box>
            }
          />
        ))}
      </Box>
    </SectionCard>
  );
}
