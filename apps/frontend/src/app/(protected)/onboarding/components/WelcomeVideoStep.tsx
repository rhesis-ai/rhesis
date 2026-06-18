'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import OnboardingStepHeader from './OnboardingStepHeader';
import OnboardingNavButtons from './OnboardingNavButtons';
import OnboardingVideoPlayer from './OnboardingVideoPlayer';
import { ONBOARDING_STEPS } from './onboarding-steps';
import { getOnboardingVideoUrl } from '@/utils/onboarding-video';

type OnboardingStatus =
  | 'idle'
  | 'creating_organization'
  | 'updating_user'
  | 'loading_initial_data'
  | 'completed';

interface WelcomeVideoStepProps {
  onComplete: () => void;
  onBack: () => void;
  isSubmitting?: boolean;
  onboardingStatus: OnboardingStatus;
}

export default function WelcomeVideoStep({
  onComplete,
  onBack,
  isSubmitting = false,
  onboardingStatus,
}: WelcomeVideoStepProps) {
  const step = ONBOARDING_STEPS[3];
  const videoUrl = getOnboardingVideoUrl();

  const getButtonText = () => {
    switch (onboardingStatus) {
      case 'creating_organization':
        return 'Creating organization...';
      case 'updating_user':
        return 'Updating user information...';
      case 'loading_initial_data':
        return 'Loading initial data...';
      case 'completed':
        return 'Setup complete. Redirecting...';
      default:
        return 'Finish up';
    }
  };

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

      {videoUrl ? (
        <OnboardingVideoPlayer videoUrl={videoUrl} />
      ) : (
        <Box
          sx={{
            width: '100%',
            aspectRatio: '16 / 9',
            borderRadius: '20px',
            bgcolor: '#090909',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            px: 3,
          }}
        >
          <Typography sx={{ color: 'grey.400', textAlign: 'center' }}>
            Welcome video coming soon. You can finish setup below.
          </Typography>
        </Box>
      )}

      <OnboardingNavButtons
        onBack={onBack}
        primaryLabel={getButtonText()}
        onPrimary={onComplete}
        isSubmitting={isSubmitting}
        disabled={onboardingStatus === 'completed'}
      />
    </Box>
  );
}
