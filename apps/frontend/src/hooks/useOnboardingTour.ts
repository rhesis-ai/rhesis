'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useOnboarding } from '@/contexts/OnboardingContext';

/**
 * Hook to auto-trigger tours based on URL params
 * Usage: Add ?tour=tourId to URL to auto-start a tour
 */
export function useOnboardingTour(tourId?: string) {
  const searchParams = useSearchParams();
  const { startTour } = useOnboarding();

  useEffect(() => {
    const tourParam = searchParams.get('tour');

    // If tour param in URL matches this page's tour, start it
    if (tourParam && tourId && tourParam === tourId) {
      // Small delay to ensure DOM is ready
      const timeout = setTimeout(() => {
        startTour(tourId);
      }, 500);

      return () => clearTimeout(timeout);
    }
  }, [searchParams, tourId, startTour]);
}
