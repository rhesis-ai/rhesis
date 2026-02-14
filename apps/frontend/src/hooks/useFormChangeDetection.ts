import { useState, useEffect, useMemo } from 'react';

function normalizeFormValue(value: string | undefined | null): string {
  return (value || '').trim();
}

function compareFormData<
  T extends Record<string, string | number | boolean | undefined | null>,
>(current: T, initial: T): boolean {
  const keys = Object.keys(current) as Array<keyof T>;

  return keys.some(key => {
    const currentValue = current[key];
    const initialValue = initial[key];

    const isStringLike = (val: unknown): val is string | null | undefined =>
      typeof val === 'string' || val === null || val === undefined;

    if (isStringLike(currentValue) && isStringLike(initialValue)) {
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

export function useFormChangeDetection<
  T extends Record<string, string | number | boolean | undefined | null>,
>({
  initialData,
  currentData,
}: UseFormChangeDetectionOptions<T>): UseFormChangeDetectionReturn {
  const [trackedInitialData, setTrackedInitialData] = useState<T>(initialData);

  const initialDataString = useMemo(
    () => JSON.stringify(initialData),
    [initialData]
  );

  useEffect(() => {
    setTrackedInitialData(initialData);
  }, [initialDataString]);

  const hasChanges = compareFormData(currentData, trackedInitialData);

  const resetChanges = () => {
    setTrackedInitialData(currentData);
  };

  return {
    hasChanges,
    resetChanges,
  };
}
