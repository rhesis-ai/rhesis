import React from 'react';
import { render } from '@/test-utils';
import RunClockProvider, { useRunClock } from '../RunClockProvider';
import type { RunClockFrame } from '../run-clock';

let mockReducedMotion = false;
jest.mock('@/hooks/useReducedMotion', () => ({
  useReducedMotion: () => mockReducedMotion,
}));

let rafCallbacks: Array<(t: number) => void> = [];
let rafIdCounter = 0;
const originalRAF = globalThis.requestAnimationFrame;
const originalCAF = globalThis.cancelAnimationFrame;

beforeEach(() => {
  rafCallbacks = [];
  rafIdCounter = 0;
  globalThis.requestAnimationFrame = jest.fn((cb: (t: number) => void) => {
    rafCallbacks.push(cb);
    return ++rafIdCounter;
  });
  globalThis.cancelAnimationFrame = jest.fn();
  mockReducedMotion = false;
});

afterEach(() => {
  globalThis.requestAnimationFrame = originalRAF;
  globalThis.cancelAnimationFrame = originalCAF;
});

function flushFrames(count: number) {
  for (let i = 0; i < count; i++) {
    const cbs = [...rafCallbacks];
    rafCallbacks = [];
    for (const cb of cbs) cb(performance.now());
  }
}

function TestConsumer({
  onFrame,
  onText,
}: {
  onFrame: (frame: RunClockFrame) => void;
  onText: (frame: RunClockFrame) => void;
}) {
  const clock = useRunClock();
  React.useEffect(() => {
    const unsubFrame = clock.subscribeFrame(onFrame);
    const unsubText = clock.subscribeText(onText);
    return () => {
      unsubFrame();
      unsubText();
    };
  }, [clock, onFrame, onText]);
  return null;
}

describe('RunClockProvider', () => {
  it('fires text subscribers at 1/4 frame rate', () => {
    const frameCb = jest.fn();
    const textCb = jest.fn();

    render(
      <RunClockProvider active={true}>
        <TestConsumer onFrame={frameCb} onText={textCb} />
      </RunClockProvider>
    );

    // Initial subscription triggers maybeStart -> one rAF queued
    flushFrames(4);

    // Frame fires every tick, text fires every 4th
    expect(frameCb.mock.calls.length).toBeGreaterThanOrEqual(4);
    // Text fires on frames where frameCount % 4 === 0
    expect(textCb.mock.calls.length).toBeGreaterThanOrEqual(1);
    expect(textCb.mock.calls.length).toBeLessThan(frameCb.mock.calls.length);
  });

  it('does not start rAF loop when reduced motion is on', () => {
    mockReducedMotion = true;
    const frameCb = jest.fn();
    const textCb = jest.fn();

    render(
      <RunClockProvider active={true}>
        <TestConsumer onFrame={frameCb} onText={textCb} />
      </RunClockProvider>
    );

    // No rAF should have been queued (only the initial from subscribe -> maybeStart guards)
    expect(rafCallbacks).toHaveLength(0);
  });

  it('poke fires one frame synchronously', () => {
    const frameCb = jest.fn();
    const textCb = jest.fn();
    let clockRef: ReturnType<typeof useRunClock> | null = null;

    /** The clock captured during render, or a thrown failure if Capturer
     *  never ran. A plain `clockRef!` read here would be a non-null
     *  assertion, and a local guard cannot work: in this scope TypeScript
     *  narrows clockRef to its `null` initializer, since the only assignment
     *  is inside Capturer. Reads inside this function use the declared type. */
    const requireClock = () => {
      if (!clockRef) {
        throw new Error('useRunClock was never captured during render');
      }
      return clockRef;
    };

    function Capturer() {
      clockRef = useRunClock();
      React.useEffect(() => {
        // Read the captured clock once and guard, rather than asserting
        // non-null twice; useRunClock() above assigns it during render.
        const clock = clockRef;
        if (!clock) return;
        const unsubFrame = clock.subscribeFrame(frameCb);
        const unsubText = clock.subscribeText(textCb);
        return () => {
          unsubFrame();
          unsubText();
        };
      }, []);
      return null;
    }

    render(
      <RunClockProvider active={false}>
        <Capturer />
      </RunClockProvider>
    );

    frameCb.mockClear();
    textCb.mockClear();

    requireClock().poke();

    expect(frameCb).toHaveBeenCalledTimes(1);
    expect(textCb).toHaveBeenCalledTimes(1);
  });

  it('does not start loop when inactive', () => {
    const frameCb = jest.fn();
    const textCb = jest.fn();

    render(
      <RunClockProvider active={false}>
        <TestConsumer onFrame={frameCb} onText={textCb} />
      </RunClockProvider>
    );

    expect(rafCallbacks).toHaveLength(0);
  });
});
