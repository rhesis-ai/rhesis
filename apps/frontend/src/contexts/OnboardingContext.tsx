'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { driver, type Driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';
import { OnboardingContextValue, OnboardingProgress } from '@/types/onboarding';
import {
  loadProgress,
  saveProgress,
  calculateCompletionPercentage,
  isOnboardingComplete,
  getDefaultProgress,
  loadProgressFromDatabase,
  syncProgressToDatabase,
  mergeProgress,
} from '@/utils/onboarding-service';
import { getTourSteps, driverConfig } from '@/config/onboarding-tours';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

const OnboardingContext = createContext<OnboardingContextValue | undefined>(
  undefined
);

/**
 * Stable identity of the meaningful progress fields, excluding the
 * `lastUpdated` timestamp. Used to detect whether progress has genuinely
 * changed versus what the database already holds, so we don't PATCH
 * `/users/settings` for no-op timestamp differences.
 */
function progressKey(progress: OnboardingProgress): string {
  return JSON.stringify([
    progress.projectCreated,
    progress.endpointSetup,
    progress.usersInvited,
    progress.testCasesCreated,
    progress.dismissed,
  ]);
}

interface OnboardingProviderProps {
  children: React.ReactNode;
}

export function OnboardingProvider({ children }: OnboardingProviderProps) {
  const { data: session, status } = useSession();
  const queryClient = useQueryClient();
  const userScope = session?.user?.id ?? '';
  // Initialize with localStorage data immediately to avoid flash
  const [progress, setProgress] = useState<OnboardingProgress>(() => {
    // Load synchronously during initialization to prevent flash
    if (typeof window !== 'undefined') {
      return loadProgress();
    }
    return getDefaultProgress();
  });
  const [activeTour, setActiveTour] = useState<string | null>(null);
  const [driverInstance, setDriverInstance] = useState<Driver | null>(null);
  const activeTourRef = useRef<string | null>(null);
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const dbLoadedRef = useRef(false);
  // Set synchronously the moment the initial load begins so a concurrent
  // invocation (React Strict Mode double-invokes effects in development) is
  // blocked before its first await, rather than racing into a second load +
  // duplicate PATCH. Distinct from `dbLoadedRef`, which flips only once the
  // load *completes* and gates the debounced writer below.
  const loadStartedRef = useRef(false);
  // Comparable key of the progress last persisted to the database. The
  // debounced writer compares against this so it only PATCHes when progress
  // genuinely differs from what the server already holds.
  const lastSyncedRef = useRef<string | null>(null);

  // Load from database once when session becomes available, merge with
  // localStorage, and sync differences back in a single round-trip.
  useEffect(() => {
    // /users/settings requires an organization; a user mid-onboarding (before
    // the org-attach step) has none yet, and the fetch would 403.
    if (
      !isAuthenticated(status) ||
      !session?.user?.organization_id ||
      loadStartedRef.current
    ) {
      return;
    }
    loadStartedRef.current = true;

    const loadInitialProgress = async () => {
      try {
        const dbProgress = await loadProgressFromDatabase(
          queryClient,
          userScope
        );

        setProgress(currentProgress => {
          const mergedProgress = mergeProgress(currentProgress, dbProgress);
          saveProgress(mergedProgress);

          const mergedKey = progressKey(mergedProgress);
          // Record the state the database will hold once this reconciliation
          // completes. Setting it optimistically (rather than after the PATCH
          // resolves) keeps the debounced writer from firing a duplicate PATCH
          // for the merged state on the next render.
          lastSyncedRef.current = mergedKey;

          if (mergedKey !== progressKey(dbProgress)) {
            syncProgressToDatabase(
              queryClient,
              userScope,
              mergedProgress
            ).catch(error => {
              console.error('Error syncing progress to database:', error);
            });
          }

          return mergedProgress;
        });
      } catch (error) {
        console.error('Error loading progress from database:', error);
      } finally {
        // Gate the debounced writer only after the load completes, so it never
        // fires against pre-merge local state mid-load.
        dbLoadedRef.current = true;
      }
    };

    loadInitialProgress();
  }, [session?.user?.organization_id, queryClient, userScope, status]);

  // Persist user-initiated progress changes: save to localStorage
  // immediately and debounce-sync to the database. Skips until the
  // initial DB load is complete to avoid redundant writes.
  useEffect(() => {
    if (progress.lastUpdated <= 0) return;

    saveProgress(progress);

    if (!dbLoadedRef.current || !isAuthenticated(status)) return;

    // Skip the write when progress already matches what the database holds.
    // This suppresses the redundant PATCH the initial load's merge would
    // otherwise trigger, and any re-render that doesn't change progress.
    const key = progressKey(progress);
    if (key === lastSyncedRef.current) return;

    if (syncTimeoutRef.current) {
      clearTimeout(syncTimeoutRef.current);
    }

    syncTimeoutRef.current = setTimeout(() => {
      lastSyncedRef.current = key;
      syncProgressToDatabase(queryClient, userScope, progress).catch(error => {
        console.error('Error syncing progress to database:', error);
      });
    }, 5000);

    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, [progress, queryClient, userScope, status]);

  // Initialize driver.js instance
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const instance = driver({
        ...driverConfig,
        onDestroyed: () => {
          // Clean up tour state
          setActiveTour(null);
          activeTourRef.current = null;
        },
      });
      setDriverInstance(instance);

      // Clear activeTour on mount in case it's stuck from a previous session
      setActiveTour(null);
      activeTourRef.current = null;

      return () => {
        instance.destroy();
      };
    }
  }, []);

  const markStepComplete = useCallback(
    (stepId: keyof Omit<OnboardingProgress, 'dismissed' | 'lastUpdated'>) => {
      setProgress(prev => ({
        ...prev,
        [stepId]: true,
        lastUpdated: Date.now(),
      }));
    },
    []
  );

  const dismissOnboarding = useCallback(() => {
    setProgress(prev => ({
      ...prev,
      dismissed: true,
      lastUpdated: Date.now(),
    }));
  }, []);

  const resetOnboarding = useCallback(() => {
    const defaultProgress = getDefaultProgress();
    setProgress(defaultProgress);
    saveProgress(defaultProgress);
  }, []);

  const startTour = useCallback(
    (tourId: string) => {
      try {
        if (!driverInstance) {
          console.error('Driver instance not initialized');
          return;
        }

        const state = driverInstance.getState();
        if (state.isInitialized) return;

        const steps = getTourSteps(tourId);
        if (steps.length === 0) {
          console.error(`No tour steps found for tourId: ${tourId}`);
          return;
        }

        setActiveTour(tourId);
        activeTourRef.current = tourId;

        // Enhance steps with tour-specific behavior
        const enhancedSteps = steps.map((step, index) => {
          // Add completion tracking to steps marked with __markComplete
          const stepWithCompletion = {
            ...step,
            onHighlighted: (
              element: Element | undefined,
              stepObj: DriveStep
            ) => {
              // Mark step complete if it has __markComplete property
              const stepWithMark = stepObj as DriveStep & {
                __markComplete?: keyof Omit<
                  OnboardingProgress,
                  'dismissed' | 'lastUpdated'
                >;
              };
              if (stepWithMark.__markComplete) {
                const stepId = stepWithMark.__markComplete;
                setProgress(prev => {
                  const updated = {
                    ...prev,
                    [stepId]: true,
                    lastUpdated: Date.now(),
                  };
                  saveProgress(updated);
                  return updated;
                });
              }
              // Call original onHighlighted if it exists
              if (step.onHighlighted) {
                step.onHighlighted(element, stepObj, {
                  config: driverInstance.getConfig(),
                  state: driverInstance.getState(),
                  driver: driverInstance,
                });
              }
            },
          };

          // For testCases tour
          if (tourId === 'testCases') {
            if (index === 0) {
              // Step 0: When "Next" is clicked, open the modal via custom event AND advance to next step
              return {
                ...stepWithCompletion,
                popover: {
                  ...stepWithCompletion.popover,
                  onNextClick: (_element: Element | undefined) => {
                    // Dispatch custom event to open modal (more reliable than clicking disabled button)
                    window.dispatchEvent(new Event('tour-open-test-modal'));
                    setTimeout(() => {
                      driverInstance.moveNext();
                    }, 400);
                  },
                },
                onHighlighted: (
                  element: Element | undefined,
                  stepObj: DriveStep
                ) => {
                  // Disable scrolling during first step
                  document.body.style.overflow = 'hidden';
                  // Call original onHighlighted if it exists
                  if (stepWithCompletion.onHighlighted) {
                    stepWithCompletion.onHighlighted(element, stepObj);
                  }
                },
                onDeselected: () => {
                  // Re-enable scrolling when leaving first step
                  document.body.style.overflow = '';
                },
              };
            }

            if (index === 1) {
              // Step 1: Handle back button to close modal
              return {
                ...stepWithCompletion,
                popover: {
                  ...stepWithCompletion.popover,
                  onPrevClick: () => {
                    const dialog = document.querySelector(
                      '[data-tour="test-generation-modal"]'
                    )?.parentElement?.parentElement as HTMLElement;
                    if (dialog) {
                      const closeButton = dialog.querySelector(
                        '.MuiDialogTitle-root .MuiIconButton-root'
                      ) as HTMLButtonElement;
                      if (closeButton) {
                        closeButton.click();
                      }
                    }
                    setTimeout(() => {
                      driverInstance.movePrevious();
                    }, 400);
                  },
                },
                // Close modal when tour ends
                onDeselected: () => {
                  const state = driverInstance.getState();
                  if (!state.isInitialized) {
                    setTimeout(() => {
                      const dialog = document.querySelector(
                        '[data-tour="test-generation-modal"]'
                      )?.parentElement?.parentElement as HTMLElement;
                      if (dialog) {
                        const closeButton = dialog.querySelector(
                          '.MuiDialogTitle-root .MuiIconButton-root'
                        ) as HTMLButtonElement;
                        if (closeButton) {
                          closeButton.click();
                        }
                      }
                    }, 100);
                  }
                },
              };
            }
          }

          return stepWithCompletion;
        });

        driverInstance.setSteps(enhancedSteps);
        driverInstance.drive();
      } catch (error) {
        console.error('Error starting onboarding tour:', error);
        // Clean up state on error
        setActiveTour(null);
        activeTourRef.current = null;
      }
    },
    [driverInstance]
  );

  const moveToNextStep = useCallback(() => {
    if (!driverInstance) return;
    driverInstance.moveNext();
  }, [driverInstance]);

  const closeTour = useCallback(() => {
    if (!driverInstance) return;
    driverInstance.destroy();
  }, [driverInstance]);

  const forceSyncToDatabase = useCallback(async () => {
    if (isAuthenticated(status) && session?.user?.organization_id) {
      try {
        await syncProgressToDatabase(queryClient, userScope, progress);
      } catch (error) {
        console.error('Error forcing sync to database:', error);
      }
    }
  }, [
    session?.user?.organization_id,
    progress,
    queryClient,
    userScope,
    status,
  ]);

  const isComplete = isOnboardingComplete(progress);
  const completionPercentage = calculateCompletionPercentage(progress);

  const value: OnboardingContextValue = {
    progress,
    isComplete,
    completionPercentage,
    markStepComplete,
    dismissOnboarding,
    resetOnboarding,
    startTour,
    activeTour,
    moveToNextStep,
    closeTour,
    forceSyncToDatabase,
  };

  return (
    <OnboardingContext.Provider value={value}>
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const context = useContext(OnboardingContext);
  if (context === undefined) {
    throw new Error('useOnboarding must be used within an OnboardingProvider');
  }
  return context;
}
