'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
} from 'react';
import { useReducedMotion } from '@/hooks/useReducedMotion';

type FrameCallback = (t: number) => void;

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
  active: boolean;
  children: React.ReactNode;
}

export default function RunClockProvider({
  active,
  children,
}: RunClockProviderProps) {
  const reducedMotion = useReducedMotion();

  const frameSubscribers = useRef(new Set<FrameCallback>());
  const textSubscribers = useRef(new Set<FrameCallback>());
  const rafId = useRef<number | null>(null);
  const frameCount = useRef(0);

  const tick = useCallback(
    (t: number) => {
      frameCount.current++;
      for (const cb of frameSubscribers.current) cb(t);
      // Text subscribers fire at ~15fps (every 4th frame).
      if (frameCount.current % 4 === 0) {
        for (const cb of textSubscribers.current) cb(t);
      }
      if (
        active &&
        !reducedMotion &&
        (frameSubscribers.current.size > 0 || textSubscribers.current.size > 0)
      ) {
        rafId.current = requestAnimationFrame(tick);
      } else {
        rafId.current = null;
      }
    },
    [active, reducedMotion]
  );

  const maybeStart = useCallback(() => {
    if (
      rafId.current !== null ||
      !active ||
      reducedMotion ||
      (frameSubscribers.current.size === 0 &&
        textSubscribers.current.size === 0)
    )
      return;
    rafId.current = requestAnimationFrame(tick);
  }, [active, reducedMotion, tick]);

  const poke = useCallback(() => {
    const t = performance.now();
    for (const cb of frameSubscribers.current) cb(t);
    for (const cb of textSubscribers.current) cb(t);
  }, []);

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

  useEffect(() => {
    maybeStart();
    return () => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current);
        rafId.current = null;
      }
    };
  }, [maybeStart]);

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
