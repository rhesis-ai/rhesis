import { useState, useEffect } from 'react';

function normalizeFormValue(value: string | undefined | null): string {
  return (value || '').trim();
}

function compareFormData<T extends Record<string, any>>(
  current: T,
  initial: T
): boolean {
  const keys = Object.keys(current) as Array<keyof T>;

  return keys.some(key => {
    const currentValue = current[key];
    const initialValue = initial[key];

    if (typeof currentValue === 'string' || typeof initialValue === 'string') {
      return (
        normalizeFormValue(currentValue) !== normalizeFormValue(initialValue)
      );
    }

    return currentValue !== initialValue;
  });
}

interface UseFormChangeDetectionOptions<T> {
  initialData: T;
  currentData: T;
}

interface UseFormChangeDetectionReturn {
  hasChanges: boolean;
  resetChanges: () => void;
}

export function useFormChangeDetection<T extends Record<string, any>>({
  initialData,
  currentData,
}: UseFormChangeDetectionOptions<T>): UseFormChangeDetectionReturn {
  const [trackedInitialData, setTrackedInitialData] = useState<T>(initialData);

  useEffect(() => {
    setTrackedInitialData(initialData);
  }, [JSON.stringify(initialData)]);

  const hasChanges = compareFormData(currentData, trackedInitialData);

  const resetChanges = () => {
    setTrackedInitialData(currentData);
  };

  return {
    hasChanges,
    resetChanges,
  };
}
