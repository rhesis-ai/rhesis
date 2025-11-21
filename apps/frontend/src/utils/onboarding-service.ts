import { ApiClientFactory } from './api-client/client-factory';
import { OnboardingProgress } from './api-client/interfaces/user';

const STORAGE_KEY = 'onboardingProgress';

export interface OnboardingState extends OnboardingProgress {
  // All fields from OnboardingProgress are optional
}

/**
 * Get onboarding progress from localStorage
 */
export function getLocalProgress(): OnboardingState {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Error reading onboarding progress from localStorage:', error);
  }

  return {};
}

/**
 * Save onboarding progress to localStorage
 */
export function saveLocalProgress(progress: OnboardingState): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  } catch (error) {
    console.error('Error saving onboarding progress to localStorage:', error);
  }
}

/**
 * Clear onboarding progress from localStorage
 */
export function clearLocalProgress(): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Error clearing onboarding progress from localStorage:', error);
  }
}

/**
 * Load onboarding progress from the database
 */
export async function loadProgressFromDatabase(
  sessionToken: string
): Promise<OnboardingState> {
  try {
    const usersClient = new ApiClientFactory(sessionToken).getUsersClient();
    const settings = await usersClient.getUserSettings();
    return settings.onboarding || {};
  } catch (error) {
    console.error('Error loading onboarding progress from database:', error);
    return {};
  }
}

/**
 * Save onboarding progress to the database
 */
export async function syncProgressToDatabase(
  sessionToken: string,
  progress: OnboardingState
): Promise<boolean> {
  try {
    const usersClient = new ApiClientFactory(sessionToken).getUsersClient();
    await usersClient.updateUserSettings({
      onboarding: {
        ...progress,
        last_updated: new Date().toISOString(),
      },
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
  local: OnboardingState,
  remote: OnboardingState
): OnboardingState {
  return {
    project_created: local.project_created || remote.project_created || false,
    endpoint_setup: local.endpoint_setup || remote.endpoint_setup || false,
    users_invited: local.users_invited || remote.users_invited || false,
    test_cases_created:
      local.test_cases_created || remote.test_cases_created || false,
    dismissed: local.dismissed || remote.dismissed || false,
    last_updated:
      local.last_updated && remote.last_updated
        ? local.last_updated > remote.last_updated
          ? local.last_updated
          : remote.last_updated
        : local.last_updated || remote.last_updated,
  };
}

/**
 * Check if all onboarding steps are completed
 */
export function isOnboardingComplete(progress: OnboardingState): boolean {
  return !!(
    progress.project_created &&
    progress.endpoint_setup &&
    progress.users_invited &&
    progress.test_cases_created
  );
}

/**
 * Check if onboarding has been dismissed
 */
export function isOnboardingDismissed(progress: OnboardingState): boolean {
  return progress.dismissed || false;
}

/**
 * Get completion percentage (0-100)
 */
export function getCompletionPercentage(progress: OnboardingState): number {
  const steps = [
    progress.project_created,
    progress.endpoint_setup,
    progress.users_invited,
    progress.test_cases_created,
  ];

  const completed = steps.filter(Boolean).length;
  return Math.round((completed / steps.length) * 100);
}
