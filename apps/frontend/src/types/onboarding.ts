import { DriveStep } from 'driver.js';

/**
 * Onboarding progress state stored in localStorage
 */
export interface OnboardingProgress {
  projectCreated: boolean;
  endpointSetup: boolean;
  usersInvited: boolean;
  testCasesCreated: boolean;
  dismissed: boolean;
  lastUpdated: number;
}

/**
 * Individual onboarding step/checklist item
 */
export interface OnboardingStep {
  id: keyof Omit<OnboardingProgress, 'dismissed' | 'lastUpdated'>;
  title: string;
  description: string;
  optional?: boolean;
  targetPath: string;
  tourId: string;
  requiresProjects?: boolean;
}

/**
 * Type for marking step completion in tour steps
 */
export type OnboardingStepId = keyof Omit<
  OnboardingProgress,
  'dismissed' | 'lastUpdated'
>;

/**
 * Tour configuration for driver.js
 */
export interface TourConfig {
  id: string;
  steps: DriveStep[];
  onComplete?: () => void;
}

/**
 * Context value for onboarding
 */
export interface OnboardingContextValue {
  progress: OnboardingProgress;
  isComplete: boolean;
  completionPercentage: number;
  markStepComplete: (
    stepId: keyof Omit<OnboardingProgress, 'dismissed' | 'lastUpdated'>
  ) => void;
  dismissOnboarding: () => void;
  resetOnboarding: () => void;
  startTour: (tourId: string) => void;
  activeTour: string | null;
  moveToNextStep: () => void;
  closeTour: () => void;
}
