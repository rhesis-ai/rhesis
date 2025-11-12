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

      const steps = getTourSteps(tourId);
      if (steps.length === 0) return;

      setActiveTour(tourId);
      driverInstance.setSteps(steps);
      driverInstance.drive();
    },
    [driverInstance]
  );

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
