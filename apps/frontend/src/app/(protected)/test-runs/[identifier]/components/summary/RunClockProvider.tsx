'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
} from 'react';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import {
  advanceClock,
  clockTarget,
  initialClock,
  isSettled,
  toFrame,
  MAX_FRAME_DT,
  type ClockState,
  type ClockTargets,
  type RunClockFrame,
} from './run-clock';

type FrameCallback = (frame: RunClockFrame) => void;

interface RunClockContextValue {
  subscribeFrame(cb: FrameCallback): () => void;
  subscribeText(cb: FrameCallback): () => void;
  poke(): void;
}

const RunClockContext = createContext<RunClockContextValue | null>(null);

export function useRunClock(): RunClockContextValue {
  const ctx = useContext(RunClockContext);
  if (!ctx) throw new Error('useRunClock must be inside RunClockProvider');
  return ctx;
}

interface RunClockProviderProps {
  /** Whether the run is still going. */
  active: boolean;
  /** Seconds into the run per the server; drives lag reconciliation. */
  serverElapsed?: number | null;
  /** Total run length, once known. */
  runDuration?: number | null;
  children: React.ReactNode;
}

export default function RunClockProvider({
  active,
  serverElapsed = null,
  runDuration = null,
  children,
}: RunClockProviderProps) {
  const reducedMotion = useReducedMotion();
  const isTerminal = !active;

  const frameSubscribers = useRef(new Set<FrameCallback>());
  const textSubscribers = useRef(new Set<FrameCallback>());
  const rafId = useRef<number | null>(null);
  const frameCount = useRef(0);
  const lastTime = useRef<number | null>(null);

  // Latest targets, read inside the loop without re-creating it every poll.
  const targetsRef = useRef<ClockTargets>({
    serverElapsed,
    runDuration,
    isTerminal,
  });
  targetsRef.current = { serverElapsed, runDuration, isTerminal };

  // A run that had already finished when the page opened starts settled, so
  // an old run is never replayed as if it were happening now.
  const state = useRef<ClockState | null>(null);
  if (state.current === null) {
    state.current = {
      clock: initialClock(runDuration, isTerminal, serverElapsed),
      rate: 1,
    };
  }

  // Real seconds on screen. Kept apart from `clock`, which runs fast while
  // catching up, so the pulses keep a steady rhythm through a replay.
  const wall = useRef(0);

  const emit = useCallback((textToo: boolean) => {
    const { runDuration: dur, isTerminal: terminal } = targetsRef.current;
    const clock = state.current?.clock ?? 0;
    const frame = toFrame(clock, dur, terminal, wall.current);
    for (const cb of frameSubscribers.current) cb(frame);
    if (textToo) {
      for (const cb of textSubscribers.current) cb(frame);
    }
  }, []);

  const hasSubscribers = useCallback(
    () => frameSubscribers.current.size > 0 || textSubscribers.current.size > 0,
    []
  );

  const settled = useCallback(() => {
    const { runDuration: dur, isTerminal: terminal } = targetsRef.current;
    return isSettled(state.current?.clock ?? 0, dur, terminal);
  }, []);

  const tick = useCallback(
    (now: number) => {
      const previous = lastTime.current;
      lastTime.current = now;
      const dt = previous === null ? 0 : (now - previous) / 1000;

      // Same clamp advanceClock applies, minus the rate: a backgrounded tab
      // resumes its pulse where it left off instead of jumping.
      wall.current += Math.min(Math.max(dt, 0), MAX_FRAME_DT);

      if (state.current) {
        state.current = advanceClock(state.current, dt, targetsRef.current);
      }

      frameCount.current++;
      // Canvas repaints every frame; DOM text at ~15fps, since rewriting
      // counters at 60fps is wasted work and visibly jitters.
      emit(frameCount.current % 4 === 0);

      if (!reducedMotion && hasSubscribers() && !settled()) {
        rafId.current = requestAnimationFrame(tick);
      } else {
        rafId.current = null;
        lastTime.current = null;
      }
    },
    [emit, hasSubscribers, reducedMotion, settled]
  );

  const maybeStart = useCallback(() => {
    if (rafId.current !== null || reducedMotion || !hasSubscribers()) return;
    if (settled()) return;
    lastTime.current = null;
    rafId.current = requestAnimationFrame(tick);
  }, [hasSubscribers, reducedMotion, settled, tick]);

  /** Repaint now without advancing time -- for resize and density changes. */
  const poke = useCallback(() => {
    emit(true);
    maybeStart();
  }, [emit, maybeStart]);

  const subscribeFrame = useCallback(
    (cb: FrameCallback) => {
      frameSubscribers.current.add(cb);
      maybeStart();
      return () => {
        frameSubscribers.current.delete(cb);
      };
    },
    [maybeStart]
  );

  const subscribeText = useCallback(
    (cb: FrameCallback) => {
      textSubscribers.current.add(cb);
      maybeStart();
      return () => {
        textSubscribers.current.delete(cb);
      };
    },
    [maybeStart]
  );

  // Reduced motion still needs the final state painted, just not animated.
  useEffect(() => {
    if (!reducedMotion) return;
    const { runDuration: dur, isTerminal: terminal } = targetsRef.current;
    const target = clockTarget(targetsRef.current);
    if (state.current) {
      state.current = {
        clock: terminal ? initialClock(dur, true) : (target ?? 0),
        rate: 1,
      };
    }
    emit(true);
  }, [reducedMotion, emit, serverElapsed, runDuration, isTerminal]);

  // Restart when the run's shape changes (a new poll, or the run finishing):
  // a settled loop must wake up to play the completion transition.
  useEffect(() => {
    maybeStart();
  }, [maybeStart, serverElapsed, runDuration, isTerminal]);

  useEffect(() => {
    return () => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current);
        rafId.current = null;
      }
    };
  }, []);

  const value = useRef<RunClockContextValue>({
    subscribeFrame,
    subscribeText,
    poke,
  });
  value.current.subscribeFrame = subscribeFrame;
  value.current.subscribeText = subscribeText;
  value.current.poke = poke;

  return (
    <RunClockContext.Provider value={value.current}>
      {children}
    </RunClockContext.Provider>
  );
}
