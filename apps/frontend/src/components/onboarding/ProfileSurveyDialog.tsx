'use client';

import * as React from 'react';
import {
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import ProfileQuestionsFields from './ProfileQuestionsFields';
import { useNotifications } from '@/components/common/NotificationContext';
import { userSettingsKeys } from '@/constants/query-keys';
import {
  EMPTY_PROFILE_ANSWERS,
  toProfileUpdate,
  type ProfileAnswers,
} from '@/constants/user-profile';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { useUserSettings } from '@/hooks/useUserSettings';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

/**
 * Asks invitees the profile questions org creators answer in /onboarding,
 * which invitees never see. Shows once: saving or skipping clears the flag.
 */
export default function ProfileSurveyDialog() {
  const userId = useUserScope();
  const queryClient = useQueryClient();
  const notifications = useNotifications();
  const { data: settings } = useUserSettings();
  const [answers, setAnswers] = React.useState<ProfileAnswers>(
    EMPTY_PROFILE_ANSWERS
  );
  const [closed, setClosed] = React.useState(false);
  const [saving, setSaving] = React.useState(false);

  const open = !closed && settings?.onboarding?.profile_survey_pending === true;

  const finish = async (saveAnswers: boolean) => {
    setSaving(true);
    try {
      await new ApiClientFactory().getUsersClient().updateUserSettings({
        onboarding: {
          profile_survey_pending: false,
          ...(saveAnswers && { profile: toProfileUpdate(answers) }),
        },
      });
      setClosed(true);
      await queryClient.invalidateQueries({
        queryKey: userSettingsKeys.all(userId),
      });
    } catch (error) {
      console.error('Failed to save profile survey:', error);
      notifications.show('Could not save your answers. Please try again.', {
        severity: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      aria-labelledby="profile-survey-title"
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle id="profile-survey-title" sx={{ typography: 'h5' }}>
        Tell us a bit about yourself
      </DialogTitle>
      <DialogContent>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          This helps us improve Rhesis for people like you.
        </Typography>
        <ProfileQuestionsFields
          answers={answers}
          onChange={update => setAnswers(prev => ({ ...prev, ...update }))}
          spacing={2.5}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={() => finish(false)} disabled={saving}>
          Skip
        </Button>
        <Button
          variant="contained"
          onClick={() => finish(true)}
          disabled={saving || !answers.jobRole}
          startIcon={saving ? <CircularProgress size={16} /> : undefined}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
