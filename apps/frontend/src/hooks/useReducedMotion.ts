import { useEffect, useState } from 'react';
import { useAccessibilityMode } from '@/hooks/useAccessibilityMode';

/**
 * True when the OS asks for reduced motion, or when accessibility mode is on:
 * there, animations stop so nothing moves on its own (WCAG 2.2.2).
 */
export function useReducedMotion(): boolean {
  const accessibilityMode = useAccessibilityMode();
  const [reduced, setReduced] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced || accessibilityMode;
}
