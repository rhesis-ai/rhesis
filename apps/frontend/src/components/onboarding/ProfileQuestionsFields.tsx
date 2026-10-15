'use client';

import * as React from 'react';
import { MenuItem, Stack, TextField } from '@mui/material';
import {
  JOB_ROLE_OPTIONS,
  REFERRAL_SOURCE_OPTIONS,
  type JobRole,
  type ProfileAnswers,
  type ReferralSource,
} from '@/constants/user-profile';

interface ProfileQuestionsFieldsProps {
  answers: ProfileAnswers;
  onChange: (answers: Partial<ProfileAnswers>) => void;
  jobRoleError?: string;
  spacing?: number;
}

/** Role (required) and "how did you hear about us" (optional), each with an "Other" text box. */
export default function ProfileQuestionsFields({
  answers,
  onChange,
  jobRoleError,
  spacing = 3.75,
}: ProfileQuestionsFieldsProps) {
  return (
    <Stack spacing={spacing} sx={{ width: '100%' }}>
      <TextField
        select
        fullWidth
        required
        label="What's your role?"
        name="jobRole"
        value={answers.jobRole}
        onChange={e => onChange({ jobRole: e.target.value as JobRole })}
        error={Boolean(jobRoleError)}
        helperText={jobRoleError || ''}
      >
        {JOB_ROLE_OPTIONS.map(option => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>

      {answers.jobRole === 'other' && (
        <TextField
          fullWidth
          label="Your role"
          name="jobRoleOther"
          value={answers.jobRoleOther}
          onChange={e => onChange({ jobRoleOther: e.target.value })}
          slotProps={{ htmlInput: { maxLength: 255 } }}
        />
      )}

      <TextField
        select
        fullWidth
        label="How did you hear about Rhesis? (optional)"
        name="referralSource"
        value={answers.referralSource}
        onChange={e =>
          onChange({ referralSource: e.target.value as ReferralSource })
        }
      >
        {REFERRAL_SOURCE_OPTIONS.map(option => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>

      {answers.referralSource === 'other' && (
        <TextField
          fullWidth
          label="Where did you hear about us?"
          name="referralSourceOther"
          value={answers.referralSourceOther}
          onChange={e => onChange({ referralSourceOther: e.target.value })}
          slotProps={{ htmlInput: { maxLength: 255 } }}
        />
      )}
    </Stack>
  );
}
