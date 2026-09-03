import {
  advanceClock,
  clockRate,
  clockTarget,
  initialClock,
  isSettled,
  toFrame,
  animationStretch,
  LAG_SECONDS,
  REPLAY_RATE,
  MAX_FRAME_DT,
  MAX_JOIN_REPLAY_SECONDS,
  SETTLE_TAIL,
  MIN_ANIMATION_SECONDS,
  TERMINAL_CATCHUP_RATE,
} from '../run-clock';

describe('clockTarget', () => {
  // The lag buffer is what turns already-elapsed timestamps back into future
  // events, so they play out smoothly instead of snapping in on each refetch.
  it('trails the server by the lag buffer while running', () => {
    expect(
      clockTarget({ serverElapsed: 30, runDuration: null, isTerminal: false })
    ).toBe(30 - LAG_SECONDS);
  });

  it('never targets a negative time at the very start of a run', () => {
    expect(
      clockTarget({ serverElapsed: 0.5, runDuration: null, isTerminal: false })
    ).toBe(0);
  });

  it('targets the run end once finished, so the strip catches up', () => {
    expect(
      clockTarget({ serverElapsed: 40, runDuration: 38, isTerminal: true })
    ).toBe(38);
  });

  it('falls back to elapsed when a finished run has no duration', () => {
    expect(
      clockTarget({ serverElapsed: 40, runDuration: null, isTerminal: true })
    ).toBe(40);
  });

  it('has no target when the server has not reported elapsed time', () => {
    expect(
      clockTarget({ serverElapsed: null, runDuration: null, isTerminal: false })
    ).toBeNull();
  });
});

describe('clockRate', () => {
  it('replays fast when far behind, for a run joined mid-flight', () => {
    expect(clockRate(0, 40, false)).toBe(REPLAY_RATE);
  });

  it('runs at real time once caught up', () => {
    expect(clockRate(20, 20, false)).toBe(1);
  });

  it('nudges rather than jumping when slightly behind', () => {
    const rate = clockRate(20, 21, false);
    expect(rate).toBeGreaterThan(1);
    expect(rate).toBeLessThan(REPLAY_RATE);
  });

  // Rewinding the clock would flicker cells backwards through states they
  // already left, so drift is corrected by easing off instead.
  it('slows rather than rewinding when ahead', () => {
    const rate = clockRate(25, 20, false);
    expect(rate).toBeLessThan(1);
    expect(rate).toBeGreaterThan(0);
  });

  it('catches up more gently on a finished run than a live replay', () => {
    expect(clockRate(0, 40, true)).toBeLessThan(clockRate(0, 40, false));
  });

  it('holds real time when there is no target', () => {
    expect(clockRate(10, null, false)).toBe(1);
  });

  // A run that finished in under MIN_ANIMATION_SECONDS would otherwise
  // resolve via TERMINAL_CATCHUP_RATE almost instantly -- animationStretch
  // caps the rate so the fill-in stays perceptible.
  it('caps the terminal catch-up rate for a very short run', () => {
    const short = 0.5;
    const rate = clockRate(0, short, true, short);
    expect(rate).toBeLessThan(1);
    expect(rate).toBeCloseTo(short / MIN_ANIMATION_SECONDS, 5);
  });

  it('does not cap a normal-length run', () => {
    expect(clockRate(0, 40, true, 40)).toBe(TERMINAL_CATCHUP_RATE);
  });

  it('caps every branch uniformly, not just the far-behind one', () => {
    const short = 0.2;
    // A tiny drift would normally resolve at NUDGE_AHEAD (1.15) or 1; both
    // must still be capped below the stretch rate for a run this short.
    expect(clockRate(0.05, 0.2, true, short)).toBeLessThanOrEqual(
      short / MIN_ANIMATION_SECONDS + 1e-9
    );
  });

  it('never speeds up a short run above its stretch rate once running', () => {
    const short = 0.5;
    expect(clockRate(0.4, short, true, short)).toBeLessThanOrEqual(1);
  });
});

describe('advanceClock', () => {
  const live = { serverElapsed: 10, runDuration: null, isTerminal: false };

  it('advances by dt at real time', () => {
    const next = advanceClock({ clock: 8, rate: 1 }, 0.016, live);
    expect(next.clock).toBeCloseTo(8.016, 5);
  });

  // A backgrounded tab returns with a huge delta; integrating it whole would
  // make the frontier leap across the strip.
  it('clamps a huge delta from a backgrounded tab', () => {
    const next = advanceClock({ clock: 0, rate: 1 }, 45, live);
    expect(next.clock).toBeLessThanOrEqual(MAX_FRAME_DT * REPLAY_RATE);
  });

  it('never moves backwards', () => {
    let state = { clock: 30, rate: 1 };
    for (let i = 0; i < 50; i++) {
      const next = advanceClock(state, 0.016, live);
      expect(next.clock).toBeGreaterThanOrEqual(state.clock);
      state = next;
    }
  });

  it('ignores a negative delta', () => {
    expect(advanceClock({ clock: 5, rate: 1 }, -3, live).clock).toBe(5);
  });

  // Joining a run in progress: replay from the start, then settle into step
  // with the server, holding the lag buffer's distance behind it.
  it('replays up to the server and then tracks it at the lag distance', () => {
    let state = { clock: 0, rate: 1 };
    let elapsed = 40;
    const dt = 0.016;
    for (let i = 0; i < 4000; i++) {
      elapsed += dt; // the run keeps going while we catch up
      state = advanceClock(state, dt, {
        serverElapsed: elapsed,
        runDuration: null,
        isTerminal: false,
      });
    }
    expect(elapsed - state.clock).toBeCloseTo(LAG_SECONDS, 0);
  });

  it('does not stall when it has drifted ahead of a stalled server', () => {
    // If updates stop arriving the clock eases off but keeps moving, so the
    // pulse never freezes mid-cycle.
    const first = advanceClock({ clock: 20, rate: 1 }, 0.016, live);
    expect(first.clock).toBeGreaterThan(20);
    expect(first.rate).toBeLessThan(1);
  });
});

describe('toFrame', () => {
  it('clamps t to the run duration while clock runs on', () => {
    const frame = toFrame(45, 38, true);
    expect(frame.clock).toBe(45);
    expect(frame.t).toBe(38);
  });

  it('reports time since completion', () => {
    expect(toFrame(40, 38, true).sinceComplete).toBe(2);
  });

  it('reports a negative sinceComplete while still running', () => {
    expect(toFrame(20, null, false).sinceComplete).toBeLessThan(0);
  });

  it('leaves t unclamped when the duration is unknown', () => {
    expect(toFrame(20, null, false).t).toBe(20);
  });
});

describe('isSettled', () => {
  it('is never settled while the run is going', () => {
    expect(isSettled(1000, 38, false)).toBe(false);
  });

  it('is unsettled until the completion transition has played', () => {
    expect(isSettled(38.5, 38, true)).toBe(false);
  });

  it('settles once the fade and ring have expired', () => {
    expect(isSettled(38 + SETTLE_TAIL, 38, true)).toBe(true);
  });
});

describe('initialClock', () => {
  // Replaying a finished run unasked would present old work as if it were
  // happening now.
  it('starts a completed run already settled', () => {
    const clock = initialClock(38, true);
    expect(isSettled(clock, 38, true)).toBe(true);
  });

  it('starts a live run from the beginning, so it can replay', () => {
    expect(initialClock(null, false)).toBe(0);
  });

  it('still replays a short run from zero', () => {
    // 12s elapsed is well inside the join window, so nothing is skipped.
    expect(initialClock(null, false, 12)).toBe(0);
  });

  // A run that has been going a long time -- or one wedged in Running --
  // would otherwise replay its whole history at REPLAY_RATE on every single
  // page load.
  it('joins near the present rather than replaying hours of history', () => {
    const elapsed = 3600;
    const clock = initialClock(null, false, elapsed);
    const target = clockTarget({
      serverElapsed: elapsed,
      runDuration: null,
      isTerminal: false,
    });
    expect(target).not.toBeNull();
    expect(target === null ? 0 : target - clock).toBe(MAX_JOIN_REPLAY_SECONDS);
  });

  it('bounds the catch-up to a few seconds of real time', () => {
    const elapsed = 3600;
    const clock = initialClock(null, false, elapsed);
    const target = clockTarget({
      serverElapsed: elapsed,
      runDuration: null,
      isTerminal: false,
    });
    const realSeconds = ((target ?? 0) - clock) / REPLAY_RATE;
    expect(realSeconds).toBeLessThanOrEqual(5);
  });
});

describe('animationStretch', () => {
  it('does not stretch a run long enough to watch', () => {
    expect(animationStretch(30)).toBe(1);
  });

  it('stretches a run that would otherwise be over instantly', () => {
    expect(animationStretch(0.5)).toBeLessThan(1);
  });

  it('leaves an unknown duration alone', () => {
    expect(animationStretch(null)).toBe(1);
  });

  it('stretches to at least the minimum watchable duration', () => {
    const duration = 0.3;
    expect(duration / animationStretch(duration)).toBeCloseTo(
      MIN_ANIMATION_SECONDS,
      5
    );
  });
});
