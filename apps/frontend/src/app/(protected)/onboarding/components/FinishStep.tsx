'use client';

import * as React from 'react';
import { Box, Stack, Typography } from '@mui/material';
import OnboardingStepHeader from './OnboardingStepHeader';
import OnboardingNavButtons from './OnboardingNavButtons';
import ViewField from '@/components/common/ViewField';
import { ONBOARDING_STEPS } from './onboarding-steps';
import {
  labelForJobRole,
  labelForReferralSource,
  type ProfileAnswers,
} from '@/constants/user-profile';
import { rem } from '@/styles/theme-constants';

interface FormData extends ProfileAnswers {
  firstName: string;
  lastName: string;
  organizationName: string;
  projectName: string;
  website: string;
  invites: { id: string; email: string }[];
}

interface FinishStepProps {
  formData: FormData;
  onNext: () => void;
  onBack: () => void;
  /** Set when this is the last step, i.e. there is no welcome video. */
  finishLabel?: string;
  isSubmitting?: boolean;
  disabled?: boolean;
}

export default function FinishStep({
  formData,
  onNext,
  onBack,
  finishLabel,
  isSubmitting,
  disabled,
}: FinishStepProps) {
  const step = ONBOARDING_STEPS[2];

  const validInvites = formData.invites.filter(
    invite => invite.email.trim() !== ''
  );

  return (
    <Box
      sx={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '50px',
      }}
    >
      <OnboardingStepHeader
        title={step.contentTitle}
        description={step.contentDescription}
      />

      <Stack spacing={3.75} sx={{ width: '100%' }}>
        <ViewField
          label="Organization Name"
          value={formData.organizationName}
        />
        <ViewField label="Project Name" value={formData.projectName} />
        <ViewField
          label="Your Name"
          value={`${formData.firstName} ${formData.lastName}`}
        />
        <ViewField label="Your Role" value={labelForJobRole(formData)} />
        {formData.referralSource && (
          <ViewField
            label="How You Heard About Us"
            value={labelForReferralSource(formData)}
          />
        )}
        {formData.website && (
          <ViewField label="Website" value={formData.website} />
        )}
        {validInvites.length > 0 && (
          <Box>
            <Typography
              sx={{
                fontSize: rem(14),
                lineHeight: rem(22),
                color: theme => theme.palette.greyscale.subtitle,
                px: '14px',
                mb: '6px',
              }}
            >
              Team Members Invited ({validInvites.length})
            </Typography>
            <Stack spacing={1.5}>
              {validInvites.map(invite => (
                <Typography
                  key={invite.id}
                  sx={{
                    fontSize: rem(16),
                    lineHeight: rem(24),
                    color: theme => theme.palette.greyscale.body,
                    bgcolor: theme => theme.palette.greyscale.fieldSurface,
                    borderRadius: '4px',
                    px: 2,
                    py: 2,
                  }}
                >
                  {invite.email}
                </Typography>
              ))}
            </Stack>
          </Box>
        )}
      </Stack>

      <OnboardingNavButtons
        onBack={onBack}
        primaryLabel={finishLabel ?? 'Next'}
        onPrimary={onNext}
        isSubmitting={isSubmitting}
        disabled={disabled}
      />
    </Box>
  );
}
