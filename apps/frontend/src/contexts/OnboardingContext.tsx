'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
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
          setActiveTour(null);
        },
      });
      setDriverInstance(instance);

      // Clear activeTour on mount in case it's stuck from a previous session
      setActiveTour(null);

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

      // Check if driver is already active
      const state = driverInstance.getState();
      if (state.isInitialized) return;

      const steps = getTourSteps(tourId);
      if (steps.length === 0) return;

      setActiveTour(tourId);

      // Enhance steps with tour-specific behavior
      const enhancedSteps = steps.map((step, index) => {
        // For project/endpoint tours: auto-close when button is clicked
        if ((tourId === 'project' || tourId === 'endpoint') && index === 0) {
          return {
            ...step,
            onHighlightStarted: (element: Element | undefined) => {
              if (element) {
                element.addEventListener('click', () => {
                  setTimeout(() => driverInstance.destroy(), 100);
                });
              }
            },
          };
        }

        // For testCases tour
        if (tourId === 'testCases') {
          if (index === 0) {
            // Step 0: When "Next" is clicked, click the button AND advance to next step
            // Per driver.js docs: when overriding onNextClick, you MUST call a driver method
            return {
              ...step,
              popover: {
                ...step.popover,
                onNextClick: (element: Element | undefined) => {
                  if (element) {
                    (element as HTMLElement).click();
                  }
                  // Wait for modal to open, then advance
                  setTimeout(() => {
                    driverInstance.moveNext();
                  }, 400);
                },
              },
            };
          }

          if (index === 1) {
            // Step 1: Override only onPrevClick to handle modal closing
            // For onNextClick (last step), let driver.js use default behavior (destroy)
            return {
              ...step,
              popover: {
                ...step.popover,
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
              // Add onDeselected to mark completion and close modal when tour ends
              onDeselected: () => {
                // Only run this when tour is being destroyed (not when going back)
                const state = driverInstance.getState();
                if (!state.isInitialized) {
                  // Tour is ending - mark complete and close modal
                  setProgress(prev => ({
                    ...prev,
                    testCasesCreated: true,
                    lastUpdated: Date.now(),
                  }));

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

        return step;
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
