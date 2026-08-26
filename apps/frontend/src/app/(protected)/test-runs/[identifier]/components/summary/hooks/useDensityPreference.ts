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

export function isDensityMode(value: unknown): value is DensityMode {
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
  /** Identifies which run this hook instance is currently showing. Next.js
   *  reuses this component across a client-side navigation between two
   *  `/test-runs/[identifier]` pages (e.g. the "jump to the new run after a
   *  rerun" redirect) instead of remounting it -- without re-keying off
   *  this, a `forceDensity` seed already consumed for the previous run
   *  would silently no-op for the new one. */
  testRunId: string;
  /** Seeds `stored` for this run only -- e.g. a `?density=` param from a
   *  "just launched this run, go watch it" redirect. Applied once per
   *  `testRunId` and never persisted, so it wins over an existing stored
   *  preference for this run without overriding it for future ones. A
   *  later explicit choice via setDensity persists normally, same as
   *  always. */
  forceDensity?: DensityMode | null;
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
 * per-run auto-settle target, which beats the run-state default. The
 * auto-settle timer is never written to storage, so it never counts as an
 * explicit choice. `forceDensity` seeds `stored` itself once per run (so it
 * shares stored's priority) without persisting -- a redirect-driven "go
 * watch this run" request, not a preference.
 */
export function useDensityPreference({
  isTerminal,
  testRunId,
  forceDensity,
}: UseDensityPreferenceOptions): UseDensityPreferenceReturn {
  // Starts null on both server and client's first render to avoid a
  // hydration mismatch, then loads on the client before paint -- same
  // pattern as useGridStateStorage.ts.
  const [stored, setStoredState] = useState<DensityMode | null>(null);
  const [autoSettled, setAutoSettled] = useState<DensityMode | null>(null);
  const wasRunningRef = useRef(false);

  // Which run this hook was last initialized for -- re-keying on testRunId
  // (not a bare "did this ever run" flag) is what makes this correct when
  // the component is reused across runs instead of remounted: it re-seeds
  // `stored` for the new run and drops the previous run's auto-settle
  // state, which would otherwise still read as settled on a run that just
  // started.
  const initializedForRunId = useRef<string | undefined>(undefined);
  useLayoutEffect(() => {
    if (initializedForRunId.current === testRunId) return;
    initializedForRunId.current = testRunId;
    // Seeds `stored` directly, bypassing saveStored -- wins for this run
    // without touching the persisted preference other runs read.
    setStoredState(forceDensity ?? loadStored());
    setAutoSettled(null);
    wasRunningRef.current = false;
  }, [testRunId, forceDensity]);

  const setDensity = useCallback((mode: DensityMode) => {
    setStoredState(mode);
    saveStored(mode);
  }, []);

  // Only for a run that transitions from running to terminal while this
  // page is open (wasRunningRef distinguishes that from "already terminal
  // on mount", where the run-state default is already correct with no
  // transition needed). Because `stored` always wins below, an explicit
  // choice -- before or after this fires -- makes it a no-op.
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
