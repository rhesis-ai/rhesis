import { OnboardingProgress } from '@/types/onboarding';

const STORAGE_KEY = 'rhesis_onboarding_progress';

/**
 * Get the default onboarding progress state
 */
export function getDefaultProgress(): OnboardingProgress {
  return {
    projectCreated: false,
    endpointSetup: false,
    usersInvited: false,
    testCasesCreated: false,
    dismissed: false,
    lastUpdated: Date.now(),
  };
}

/**
 * Load onboarding progress from localStorage
 */
export function loadProgress(): OnboardingProgress {
  if (typeof window === 'undefined') {
    return getDefaultProgress();
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        ...getDefaultProgress(),
        ...parsed,
      };
    }
  } catch (error) {
    console.error('Failed to load onboarding progress:', error);
  }

  return getDefaultProgress();
}

/**
 * Save onboarding progress to localStorage
 */
export function saveProgress(progress: OnboardingProgress): void {
  if (typeof window === 'undefined') return;

  try {
    const toSave = {
      ...progress,
      lastUpdated: Date.now(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
  } catch (error) {
    console.error('Failed to save onboarding progress:', error);
  }
}

/**
 * Calculate completion percentage
 */
export function calculateCompletionPercentage(
  progress: OnboardingProgress
): number {
  const steps = [
    progress.projectCreated,
    progress.endpointSetup,
    progress.usersInvited,
    progress.testCasesCreated,
  ];

  const completed = steps.filter(Boolean).length;
  return Math.round((completed / steps.length) * 100);
}

/**
 * Check if onboarding is complete
 */
export function isOnboardingComplete(progress: OnboardingProgress): boolean {
  return (
    progress.projectCreated &&
    progress.endpointSetup &&
    progress.testCasesCreated
  );
}

/**
 * Clear onboarding progress
 */
export function clearProgress(): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Failed to clear onboarding progress:', error);
  }
}
