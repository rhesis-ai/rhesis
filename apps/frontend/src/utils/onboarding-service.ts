import { QueryClient } from '@tanstack/react-query';
import { OnboardingProgress } from '@/types/onboarding';
import { ApiClientFactory } from './api-client/client-factory';
import type {
  OnboardingProgress as BackendOnboardingProgress,
  OnboardingStatus,
} from './api-client/interfaces/user';
import {
  fetchUserSettings,
  writeUserSettingsCache,
} from '@/hooks/useUserSettings';

const STORAGE_KEY = 'rhesis_onboarding_progress';

/**
 * Get the default onboarding progress state
 */
export function getDefaultProgress(): OnboardingProgress {
  return {
    endpointSetup: false,
    agentTested: false,
    insightsReviewed: false,
    usersInvited: false,
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
 * Calculate completion percentage over the required steps. Inviting users is
 * optional, so it never moves the bar.
 */
export function calculateCompletionPercentage(
  progress: OnboardingProgress
): number {
  const steps = [
    progress.endpointSetup,
    progress.agentTested,
    progress.insightsReviewed,
  ];

  const completed = steps.filter(Boolean).length;
  return Math.round((completed / steps.length) * 100);
}

/**
 * OR the backend's data-derived status into local progress. A step the user
 * already completed locally is never turned back off.
 */
export function applyServerStatus(
  progress: OnboardingProgress,
  status: OnboardingStatus | undefined
): OnboardingProgress {
  if (!status) return progress;
  return {
    ...progress,
    endpointSetup: progress.endpointSetup || status.endpoint_setup,
    agentTested: progress.agentTested || status.agent_tested,
    usersInvited: progress.usersInvited || status.users_invited,
  };
}

/**
 * Check if onboarding is complete
 */
export function isOnboardingComplete(progress: OnboardingProgress): boolean {
  return (
    progress.endpointSetup && progress.agentTested && progress.insightsReviewed
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
    endpoint_setup: progress.endpointSetup,
    agent_tested: progress.agentTested,
    insights_reviewed: progress.insightsReviewed,
    users_invited: progress.usersInvited,
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
    endpointSetup: backendProgress.endpoint_setup || false,
    agentTested: backendProgress.agent_tested || false,
    insightsReviewed: backendProgress.insights_reviewed || false,
    usersInvited: backendProgress.users_invited || false,
    dismissed: backendProgress.dismissed || false,
    lastUpdated: backendProgress.last_updated
      ? new Date(backendProgress.last_updated).getTime()
      : Date.now(),
  };
}

/**
 * Load onboarding progress from the database. Joins the shared
 * `useUserSettings` cache so this doesn't duplicate a fetch already
 * in flight or already warm from another consumer.
 */
export async function loadProgressFromDatabase(
  queryClient: QueryClient,
  userScope: string
): Promise<OnboardingProgress> {
  try {
    const settings = await fetchUserSettings(queryClient, userScope);

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
 * Save onboarding progress to the database and write the result back into
 * the shared `useUserSettings` cache so other consumers see it immediately.
 */
export async function syncProgressToDatabase(
  queryClient: QueryClient,
  userScope: string,
  progress: OnboardingProgress
): Promise<boolean> {
  try {
    const usersClient = new ApiClientFactory().getUsersClient();
    const updated = await usersClient.updateUserSettings({
      onboarding: toBackendFormat(progress),
    });
    writeUserSettingsCache(queryClient, userScope, updated);
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
    endpointSetup: local.endpointSetup || remote.endpointSetup,
    agentTested: local.agentTested || remote.agentTested,
    insightsReviewed: local.insightsReviewed || remote.insightsReviewed,
    usersInvited: local.usersInvited || remote.usersInvited,
    dismissed: local.dismissed || remote.dismissed,
    lastUpdated: Math.max(local.lastUpdated, remote.lastUpdated),
  };
}
