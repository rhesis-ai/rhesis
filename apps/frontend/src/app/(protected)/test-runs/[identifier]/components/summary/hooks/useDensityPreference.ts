'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import type { DensityMode } from '../summary-tokens';

const STORAGE_KEY = 'runSummary.metricTableDensity';
const AUTO_SETTLE_DELAY_MS = 1500;

function isDensityMode(value: unknown): value is DensityMode {
  return value === 'numbers' || value === 'shape' || value === 'detail';
}

function loadStored(): DensityMode | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return isDensityMode(raw) ? raw : null;
  } catch {
    return null;
  }
}

function saveStored(mode: DensityMode): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // Unavailable (private mode, quota) -- the choice just won't survive
    // a reload this session.
  }
}

interface UseDensityPreferenceOptions {
  isTerminal: boolean;
}

interface UseDensityPreferenceReturn {
  density: DensityMode;
  setDensity: (mode: DensityMode) => void;
}

/**
 * A user-level preference (not per-run), scoped to this component --
 * `runSummary.metricTableDensity`, not a general "density" setting other
 * pages might reuse differently.
 *
 * Three tiers, `stored` always winning: an explicit choice (persisted
 * immediately by setDensity, every DensityControl click) beats a one-shot
 * session-only auto-settle target, which beats the run-state default. The
 * auto-settle timer is never written to storage, so it never counts as an
 * explicit choice.
 */
export function useDensityPreference({
  isTerminal,
}: UseDensityPreferenceOptions): UseDensityPreferenceReturn {
  // Starts null on both server and client's first render to avoid a
  // hydration mismatch, then loads on the client before paint -- same
  // pattern as useGridStateStorage.ts.
  const [stored, setStoredState] = useState<DensityMode | null>(null);
  useLayoutEffect(() => {
    setStoredState(loadStored());
  }, []);

  const [autoSettled, setAutoSettled] = useState<DensityMode | null>(null);

  const setDensity = useCallback((mode: DensityMode) => {
    setStoredState(mode);
    saveStored(mode);
  }, []);

  // Only for a run that transitions from running to terminal while this
  // page is open (wasRunningRef distinguishes that from "already terminal
  // on mount", where the run-state default is already correct with no
  // transition needed). Because `stored` always wins below, an explicit
  // choice -- before or after this fires -- makes it a no-op.
  const wasRunningRef = useRef(false);
  useEffect(() => {
    if (!isTerminal) {
      wasRunningRef.current = true;
      return;
    }
    if (!wasRunningRef.current) return;
    const t = setTimeout(() => setAutoSettled('shape'), AUTO_SETTLE_DELAY_MS);
    return () => clearTimeout(t);
  }, [isTerminal]);

  const density = stored ?? autoSettled ?? (isTerminal ? 'shape' : 'detail');

  return { density, setDensity };
}
