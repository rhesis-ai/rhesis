import { OnboardingProgress } from '@/types/onboarding';
import { ApiClientFactory } from './api-client/client-factory';
import { OnboardingProgress as BackendOnboardingProgress } from './api-client/interfaces/user';

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

/**
 * Convert frontend OnboardingProgress (camelCase) to backend format (snake_case)
 */
function toBackendFormat(
  progress: OnboardingProgress
): BackendOnboardingProgress {
  return {
    project_created: progress.projectCreated,
    endpoint_setup: progress.endpointSetup,
    users_invited: progress.usersInvited,
    test_cases_created: progress.testCasesCreated,
    dismissed: progress.dismissed,
    last_updated: new Date(progress.lastUpdated).toISOString(),
  };
}

/**
 * Convert backend OnboardingProgress (snake_case) to frontend format (camelCase)
 */
function toFrontendFormat(
  backendProgress: BackendOnboardingProgress
): OnboardingProgress {
  return {
    projectCreated: backendProgress.project_created || false,
    endpointSetup: backendProgress.endpoint_setup || false,
    usersInvited: backendProgress.users_invited || false,
    testCasesCreated: backendProgress.test_cases_created || false,
    dismissed: backendProgress.dismissed || false,
    lastUpdated: backendProgress.last_updated
      ? new Date(backendProgress.last_updated).getTime()
      : Date.now(),
  };
}

/**
 * Load onboarding progress from the database
 */
export async function loadProgressFromDatabase(
  sessionToken: string
): Promise<OnboardingProgress> {
  try {
    const usersClient = new ApiClientFactory(sessionToken).getUsersClient();
    const settings = await usersClient.getUserSettings();

    if (settings.onboarding) {
      return toFrontendFormat(settings.onboarding);
    }

    return getDefaultProgress();
  } catch (error) {
    console.error('Error loading onboarding progress from database:', error);
    return getDefaultProgress();
  }
}

/**
 * Save onboarding progress to the database
 */
export async function syncProgressToDatabase(
  sessionToken: string,
  progress: OnboardingProgress
): Promise<boolean> {
  try {
    const usersClient = new ApiClientFactory(sessionToken).getUsersClient();
    await usersClient.updateUserSettings({
      onboarding: toBackendFormat(progress),
    });
    return true;
  } catch (error) {
    console.error('Error syncing onboarding progress to database:', error);
    return false;
  }
}

/**
 * Merge local and remote onboarding progress.
 * Strategy: Once a step is complete, it stays complete (OR operation).
 */
export function mergeProgress(
  local: OnboardingProgress,
  remote: OnboardingProgress
): OnboardingProgress {
  return {
    projectCreated: local.projectCreated || remote.projectCreated,
    endpointSetup: local.endpointSetup || remote.endpointSetup,
    usersInvited: local.usersInvited || remote.usersInvited,
    testCasesCreated: local.testCasesCreated || remote.testCasesCreated,
    dismissed: local.dismissed || remote.dismissed,
    lastUpdated: Math.max(local.lastUpdated, remote.lastUpdated),
  };
}
