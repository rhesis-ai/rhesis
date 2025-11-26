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
import { driver, Driver } from 'driver.js';
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

const OnboardingContext = createContext<OnboardingContextValue | undefined>(
  undefined
);

interface OnboardingProviderProps {
  children: React.ReactNode;
}

export function OnboardingProvider({ children }: OnboardingProviderProps) {
  const { data: session } = useSession();
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

  // Sync with database when session is available
  useEffect(() => {
    const loadInitialProgress = async () => {
      // Load from database if user is authenticated
      if (session?.session_token && !dbLoadedRef.current) {
        try {
          const dbProgress = await loadProgressFromDatabase(
            session.session_token
          );

          // Get current progress (already loaded from localStorage in initial state)
          setProgress(currentProgress => {
            // Merge local and remote progress (once complete = always complete)
            const mergedProgress = mergeProgress(currentProgress, dbProgress);

            // Update localStorage with merged progress
            saveProgress(mergedProgress);

            // Sync merged progress back to DB if there were any changes
            if (JSON.stringify(mergedProgress) !== JSON.stringify(dbProgress)) {
              syncProgressToDatabase(
                session.session_token,
                mergedProgress
              ).catch(error => {
                console.error('Error syncing progress to database:', error);
              });
            }

            return mergedProgress;
          });

          dbLoadedRef.current = true;
        } catch (error) {
          console.error('Error loading progress from database:', error);
          // Continue with localStorage data on error
        }
      }
    };

    loadInitialProgress();
  }, [session?.session_token]);

  // Save progress to localStorage and debounced sync to database
  useEffect(() => {
    if (progress.lastUpdated > 0) {
      // Save to localStorage immediately
      saveProgress(progress);

      // Debounced sync to database (5 seconds after last change)
      if (session?.session_token) {
        const sessionToken = session.session_token; // Capture value for closure
        // Clear any existing timeout
        if (syncTimeoutRef.current) {
          clearTimeout(syncTimeoutRef.current);
        }

        // Set new timeout for database sync
        syncTimeoutRef.current = setTimeout(() => {
          syncProgressToDatabase(sessionToken, progress).catch(error => {
            console.error('Error syncing progress to database:', error);
          });
        }, 5000); // 5 second debounce
      }
    }

    // Cleanup timeout on unmount
    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, [progress, session?.session_token]);

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
            onHighlighted: (element: Element | undefined, stepObj: any) => {
              // Mark step complete if it has __markComplete property
              if ((stepObj as any).__markComplete) {
                const stepId = (stepObj as any).__markComplete;
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
                  onNextClick: (element: Element | undefined) => {
                    // Dispatch custom event to open modal (more reliable than clicking disabled button)
                    window.dispatchEvent(new Event('tour-open-test-modal'));
                    setTimeout(() => {
                      driverInstance.moveNext();
                    }, 400);
                  },
                },
                onHighlighted: (element: Element | undefined, stepObj: any) => {
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
    if (session?.session_token) {
      const sessionToken = session.session_token;
      try {
        await syncProgressToDatabase(sessionToken, progress);
      } catch (error) {
        console.error('Error forcing sync to database:', error);
      }
    }
  }, [session?.session_token, progress]);

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
