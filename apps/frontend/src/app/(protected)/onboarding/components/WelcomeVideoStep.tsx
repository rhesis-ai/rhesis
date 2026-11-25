'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import OnboardingStepHeader from './OnboardingStepHeader';
import OnboardingNavButtons from './OnboardingNavButtons';
import OnboardingVideoPlayer from './OnboardingVideoPlayer';
import {
  ONBOARDING_STEPS,
  finishButtonLabel,
  type OnboardingStatus,
} from './onboarding-steps';

interface WelcomeVideoStepProps {
  onComplete: () => void;
  onBack: () => void;
  isSubmitting?: boolean;
  onboardingStatus: OnboardingStatus;
  videoUrl: string;
}

export default function WelcomeVideoStep({
  onComplete,
  onBack,
  isSubmitting = false,
  onboardingStatus,
  videoUrl,
}: WelcomeVideoStepProps) {
  const step = ONBOARDING_STEPS[3];

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

      <OnboardingVideoPlayer videoUrl={videoUrl} />

      <OnboardingNavButtons
        onBack={onBack}
        primaryLabel={finishButtonLabel(onboardingStatus)}
        onPrimary={onComplete}
        isSubmitting={isSubmitting}
        disabled={onboardingStatus === 'completed'}
      />
    </Box>
  );
}
