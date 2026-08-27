/**
 * The animation clock's arithmetic, kept pure so it can be tested without
 * timers or a running rAF loop.
 *
 * Two separate quantities:
 *   `clock` -- continuous seconds since the animation began. Keeps advancing
 *              after the run ends, because the pulse oscillators read from it
 *              and would otherwise freeze mid-cycle on completion.
 *   `t`     -- `clock` clamped to the run's duration. Cell state derives from
 *              this, so nothing resolves past the end of the run.
 */

/**
 * How far behind the server the strip deliberately runs.
 *
 * Timing data always describes moments that have already passed: the server
 * reports a test started two seconds ago, not that it is starting now. Pinned
 * to server-now, every refetch would drop a batch of already-elapsed
 * timestamps at once and the frontier would advance in a staircase. Holding
 * the clock a little behind puts those moments back in the future, so they
 * play out at their true relative spacing. Same idea as a video jitter buffer.
 */
export const LAG_SECONDS = 2;

/** Catch-up rate when joining a run already in progress. */
export const REPLAY_RATE = 10;

/** Rate used to close the lag gap once a run finishes, so the strip settles promptly. */
export const TERMINAL_CATCHUP_RATE = 3;

/** Beyond this drift, jump rate rather than nudge. */
const REPLAY_THRESHOLD = 3;

/** Gentle corrections, so cells never appear to run backwards. */
const NUDGE_AHEAD = 1.15;
const NUDGE_BEHIND = 0.92;
const DRIFT_TOLERANCE = 0.3;

/** A backgrounded tab returns with a huge delta; integrate it in one step and
 *  the frontier would leap. */
export const MAX_FRAME_DT = 0.1;

/** Fade (~0.4s) plus the failure ring (~1.4s), with a little margin. */
export const SETTLE_TAIL = 2;

/** Very short runs would be over before they were seen. */
export const MIN_ANIMATION_SECONDS = 1.5;

export interface ClockState {
  clock: number;
  rate: number;
}

export interface ClockTargets {
  /** Seconds into the run as reported by the server, or null if unknown. */
  serverElapsed: number | null;
  /** Total run length once known. */
  runDuration: number | null;
  isTerminal: boolean;
}

/**
 * Where the clock is trying to be: a fixed lag behind the server while
 * running, and the run's end once it has finished.
 */
export function clockTarget(targets: ClockTargets): number | null {
  const { serverElapsed, runDuration, isTerminal } = targets;
  if (isTerminal) {
    if (runDuration !== null) return runDuration;
    return serverElapsed;
  }
  if (serverElapsed === null) return null;
  return Math.max(0, serverElapsed - LAG_SECONDS);
}

/**
 * Playback rate for this frame. Corrections are applied to the rate rather
 * than to `clock` itself: jumping the clock makes cells flicker backwards
 * through states they already left.
 *
 * For a run that finished in well under MIN_ANIMATION_SECONDS, every branch
 * below is capped at `animationStretch(runDuration)` -- a rate under 1 -- so
 * catching up to a tiny `runDuration` still takes long enough to be seen,
 * regardless of which branch would otherwise have fired.
 */
export function clockRate(
  clock: number,
  target: number | null,
  isTerminal: boolean,
  runDuration: number | null = null
): number {
  if (target === null) return 1;
  const drift = target - clock;

  let rate: number;
  if (drift > REPLAY_THRESHOLD) {
    rate = isTerminal ? TERMINAL_CATCHUP_RATE : REPLAY_RATE;
  } else if (drift > DRIFT_TOLERANCE) {
    rate = NUDGE_AHEAD;
  } else if (drift < -DRIFT_TOLERANCE) {
    rate = NUDGE_BEHIND;
  } else {
    rate = 1;
  }

  if (isTerminal && runDuration !== null) {
    const stretch = animationStretch(runDuration);
    if (stretch < 1) rate = Math.min(rate, stretch);
  }
  return rate;
}

/** Advance one frame. `dt` is clamped, so a stalled tab resumes rather than leaps. */
export function advanceClock(
  state: ClockState,
  dt: number,
  targets: ClockTargets
): ClockState {
  const target = clockTarget(targets);
  const rate = clockRate(
    state.clock,
    target,
    targets.isTerminal,
    targets.runDuration
  );
  const step = Math.min(Math.max(dt, 0), MAX_FRAME_DT) * rate;
  return { clock: state.clock + step, rate };
}

/** Run state derived from the clock, handed to every strip each frame. */
export interface RunClockFrame {
  clock: number;
  t: number;
  /** Seconds since the run finished; negative while it is still going. */
  sinceComplete: number;
  isTerminal: boolean;
}

export function toFrame(
  clock: number,
  runDuration: number | null,
  isTerminal: boolean
): RunClockFrame {
  const duration = runDuration ?? Infinity;
  return {
    clock,
    t: Math.min(clock, duration),
    sinceComplete: runDuration === null ? -Infinity : clock - runDuration,
    isTerminal,
  };
}

/**
 * True once the run is over and its completion transition has played out --
 * the point at which the rAF loop can stop and leave a static frame.
 */
export function isSettled(
  clock: number,
  runDuration: number | null,
  isTerminal: boolean
): boolean {
  if (!isTerminal) return false;
  if (runDuration === null) return true;
  return clock >= runDuration + SETTLE_TAIL;
}

/**
 * Where the clock starts. A run that was already finished when the page opened
 * renders settled -- there is no live process to convey, and replaying it
 * unasked would misrepresent an old run as happening now. A run still in
 * flight starts at zero and replays up to the present.
 */
export function initialClock(
  runDuration: number | null,
  isTerminal: boolean
): number {
  if (!isTerminal) return 0;
  return (runDuration ?? 0) + SETTLE_TAIL;
}

/**
 * Stretch a very short run so the fill is perceptible. Returns the factor to
 * divide timing values by; 1 for any run long enough to watch.
 */
export function animationStretch(runDuration: number | null): number {
  if (runDuration === null || runDuration <= 0) return 1;
  if (runDuration >= MIN_ANIMATION_SECONDS) return 1;
  return runDuration / MIN_ANIMATION_SECONDS;
}
