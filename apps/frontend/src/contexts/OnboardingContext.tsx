'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react';
import { driver, Driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { OnboardingContextValue, OnboardingProgress } from '@/types/onboarding';
import {
  loadProgress,
  saveProgress,
  calculateCompletionPercentage,
  isOnboardingComplete,
  getDefaultProgress,
} from '@/utils/onboarding-service';
import { getTourSteps, driverConfig } from '@/config/onboarding-tours';

const OnboardingContext = createContext<OnboardingContextValue | undefined>(
  undefined
);

interface OnboardingProviderProps {
  children: React.ReactNode;
}

export function OnboardingProvider({ children }: OnboardingProviderProps) {
  const [progress, setProgress] =
    useState<OnboardingProgress>(getDefaultProgress());
  const [activeTour, setActiveTour] = useState<string | null>(null);
  const [driverInstance, setDriverInstance] = useState<Driver | null>(null);
  const activeTourRef = useRef<string | null>(null);

  // Load progress from localStorage on mount
  useEffect(() => {
    const loaded = loadProgress();
    setProgress(loaded);
  }, []);

  // Save progress whenever it changes
  useEffect(() => {
    if (progress.lastUpdated > 0) {
      saveProgress(progress);
    }
  }, [progress]);

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
      if (!driverInstance) return;

      const state = driverInstance.getState();
      if (state.isInitialized) return;

      const steps = getTourSteps(tourId);
      if (steps.length === 0) return;

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
            // Step 0: When "Next" is clicked, click the button AND advance to next step
            return {
              ...stepWithCompletion,
              popover: {
                ...stepWithCompletion.popover,
                onNextClick: (element: Element | undefined) => {
                  if (element) {
                    (element as HTMLElement).click();
                  }
                  setTimeout(() => {
                    driverInstance.moveNext();
                  }, 400);
                },
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
