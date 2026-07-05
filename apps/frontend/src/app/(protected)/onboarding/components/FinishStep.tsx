'use client';

import * as React from 'react';
import { Box, Stack, Typography } from '@mui/material';
import OnboardingStepHeader from './OnboardingStepHeader';
import OnboardingNavButtons from './OnboardingNavButtons';
import ViewField from '@/components/common/ViewField';
import { ONBOARDING_STEPS } from './onboarding-steps';

interface FormData {
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
}

export default function FinishStep({
  formData,
  onNext,
  onBack,
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
        {formData.website && (
          <ViewField label="Website" value={formData.website} />
        )}
        {validInvites.length > 0 && (
          <Box>
            <Typography
              sx={{
                fontSize: 14,
                lineHeight: '22px',
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
                    fontSize: 16,
                    lineHeight: '24px',
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
        primaryLabel="Next"
        onPrimary={onNext}
      />
    </Box>
  );
}
