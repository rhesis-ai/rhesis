import type { CellState } from './verdict-model';
import type { RunClockFrame } from './run-clock';

export type VerdictPalette = Record<
  CellState,
  { color: string; alpha: number }
>;

export interface StripPaintOptions {
  width: number;
  height: number;
  dpr: number;
  cells: CellState[];
  palette: VerdictPalette;
  binned: boolean;
  frame: RunClockFrame;
  reducedMotion: boolean;
}

const CELL_MAX_WIDTH = 24;
const CELL_BORDER_RADIUS = 2;
const MIN_CELL_WIDTH = 3;

/**
 * Pulse rates, in radians/second. Generation is a slow, calm breath; the
 * evaluation tail is urgent. Two rates rather than one so the phase a column
 * is in is legible from the corner of the eye, without reading colour.
 */
const GENERATING_FREQ = 4;
const EVALUATING_FREQ = 9;

/**
 * Oscillation depth, as a fraction of each state's base alpha. Generating
 * swings wide and stays dim; evaluating barely swings and stays bright, so
 * the two bands never overlap and the state is unambiguous at any instant of
 * the cycle.
 */
const GENERATING_DEPTH = 0.66;
const EVALUATING_DEPTH = 0.17;

/**
 * Phase lag per column. Without it every in-flight cell pulses in unison and
 * the row flashes like a warning light; with it the pulse travels rightward,
 * the same direction the frontier moves.
 */
const COLUMN_PHASE_LAG = 0.35;

/** Flat alphas under reduced motion, as fractions of the base. */
const REDUCED_GENERATING = 1.15;
const REDUCED_EVALUATING = 1;

/** Passed cells drop to ~76% alpha as a run lands (the spec's 0.42 -> 0.32),
 *  moving contrast onto the failures in a run that mostly passed. */
const PASS_SETTLE_FACTOR = 0.32 / 0.42;
const PASS_SETTLE_SECONDS = 0.4;

/** One "look here" moment: failures ring once as the run completes. */
const FAIL_RING_SECONDS = 1.4;
const FAIL_RING_ALPHA = 0.9;
const FAIL_RING_WIDTH = 1.4;
const FAIL_RING_INSET = 1.5;

const MAX_LISTED_FAILURES = 5;
const TRUNCATED_FAILURE_EXAMPLES = 3;

function easeOutCubic(x: number): number {
  return 1 - Math.pow(1 - x, 3);
}

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x;
}

// Rounds a cell's corners when the canvas supports it (broadly available;
// falls back to a square corner on an environment that doesn't). Radius is
// clamped to half the smaller dimension so a thin sliver never blobs out
// into an ellipse.
function tracePerCellShape(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  radius: number = CELL_BORDER_RADIUS
): void {
  ctx.beginPath();
  const r = Math.max(0, Math.min(radius, w / 2, h / 2));
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, w, h, r);
  } else {
    ctx.rect(x, y, w, h);
  }
}

/**
 * Alpha for one cell this frame: the palette's base, modulated by the pulse
 * while in flight and by the completion fade once the run has landed.
 */
export function alphaFor(
  state: CellState,
  columnIndex: number,
  palette: VerdictPalette,
  frame: RunClockFrame,
  reducedMotion: boolean
): number {
  const base = palette[state].alpha;

  if (state === 'generating' || state === 'evaluating') {
    const isGenerating = state === 'generating';
    if (reducedMotion) {
      return base * (isGenerating ? REDUCED_GENERATING : REDUCED_EVALUATING);
    }
    const freq = isGenerating ? GENERATING_FREQ : EVALUATING_FREQ;
    const depth = isGenerating ? GENERATING_DEPTH : EVALUATING_DEPTH;
    // Wall time, not run time: the pulse says "this is in flight", which is
    // a property of the display. Driving it from `clock` made it oscillate
    // at REPLAY_RATE during a catch-up, reading as flicker.
    const phase = freq * frame.wall - COLUMN_PHASE_LAG * columnIndex;
    return clamp01(base * (1 + depth * Math.sin(phase)));
  }

  if (state === 'passed' && frame.sinceComplete >= 0) {
    const settle = reducedMotion
      ? 1
      : easeOutCubic(clamp01(frame.sinceComplete / PASS_SETTLE_SECONDS));
    return base * (1 - (1 - PASS_SETTLE_FACTOR) * settle);
  }

  return base;
}

/** Ring opacity for a just-failed cell, or 0 once the pulse has expired. */
export function failRingAlpha(
  frame: RunClockFrame,
  reducedMotion: boolean
): number {
  if (reducedMotion) return 0;
  const age = frame.sinceComplete;
  if (age < 0 || age >= FAIL_RING_SECONDS) return 0;
  return (1 - age / FAIL_RING_SECONDS) * FAIL_RING_ALPHA;
}

// Canvas is opaque to assistive tech, so this is the strip's only text
// equivalent. Test positions are 1-indexed (a human ordinal, not the raw id).
export function describeStrip(label: string, cells: CellState[]): string {
  const total = cells.length;
  if (total === 0) return `${label}: no tests.`;

  const passed = cells.filter(c => c === 'passed').length;
  const failurePositions: number[] = [];
  cells.forEach((c, i) => {
    if (c === 'failed' || c === 'error') failurePositions.push(i + 1);
  });

  const summary = `${label}: ${passed} of ${total} tests passed.`;
  if (failurePositions.length === 0) return summary;

  if (failurePositions.length === 1) {
    return `${summary} Failure at test ${failurePositions[0]}.`;
  }
  if (failurePositions.length <= MAX_LISTED_FAILURES) {
    return `${summary} Failures at tests ${failurePositions.join(', ')}.`;
  }
  const shown = failurePositions.slice(0, TRUNCATED_FAILURE_EXAMPLES);
  const rest = failurePositions.length - shown.length;
  return `${summary} Failures at tests ${shown.join(', ')} and ${rest} others.`;
}

// Width-aware: a narrower strip (e.g. the 230px Numbers+shape strip) crosses
// into binning at a lower cell count than a wide one (e.g. Detail's 1fr) --
// that's correct, not a bug. Below MIN_CELL_WIDTH a per-cell strip
// degenerates into a hairline with no visible gap between cells anyway.
export function shouldBin(
  cellCount: number,
  widthPx: number,
  minCellPx: number = MIN_CELL_WIDTH
): boolean {
  return cellCount > 0 && widthPx / cellCount < minCellPx;
}

export function paintStrip(
  ctx: CanvasRenderingContext2D,
  opts: StripPaintOptions
): void {
  const { width, height, dpr, cells, binned } = opts;
  if (width <= 0 || height <= 0 || cells.length === 0) return;

  ctx.clearRect(0, 0, width * dpr, height * dpr);
  ctx.save();
  ctx.scale(dpr, dpr);

  if (binned) {
    paintBinned(ctx, opts);
  } else {
    paintPerCell(ctx, opts);
  }

  ctx.restore();
}

function paintPerCell(
  ctx: CanvasRenderingContext2D,
  opts: StripPaintOptions
): void {
  const { width, height, cells, palette, frame, reducedMotion } = opts;
  const drawWidth = Math.min(CELL_MAX_WIDTH, width / cells.length);
  const gap = cells.length > 1 ? 1 : 0;
  const cellWidth = Math.max(1, drawWidth - gap);
  const ringAlpha = failRingAlpha(frame, reducedMotion);

  for (let i = 0; i < cells.length; i++) {
    const state = cells[i];
    const entry = palette[state];
    const x = i * drawWidth;

    ctx.globalAlpha = alphaFor(state, i, palette, frame, reducedMotion);

    if (state === 'error') {
      ctx.strokeStyle = entry.color;
      ctx.lineWidth = 1;
      tracePerCellShape(ctx, x + 0.5, 0.5, cellWidth - 1, height - 1);
      ctx.stroke();
    } else {
      ctx.fillStyle = entry.color;
      tracePerCellShape(ctx, x, 0, cellWidth, height);
      ctx.fill();
    }

    if (ringAlpha > 0 && state === 'failed') {
      ctx.globalAlpha = ringAlpha;
      ctx.strokeStyle = entry.color;
      ctx.lineWidth = FAIL_RING_WIDTH;
      tracePerCellShape(
        ctx,
        x - FAIL_RING_INSET,
        -FAIL_RING_INSET,
        cellWidth + FAIL_RING_INSET * 2,
        height + FAIL_RING_INSET * 2,
        CELL_BORDER_RADIUS + 1
      );
      ctx.stroke();
    }
  }

  ctx.globalAlpha = 1;
}

function paintBinned(
  ctx: CanvasRenderingContext2D,
  opts: StripPaintOptions
): void {
  const { width, height, cells, palette, frame, reducedMotion } = opts;
  const binCount = Math.max(1, Math.floor(width));

  for (let col = 0; col < binCount; col++) {
    const startIdx = Math.floor((col / binCount) * cells.length);
    const endIdx = Math.floor(((col + 1) / binCount) * cells.length);
    if (startIdx >= endIdx) continue;

    // Pick the dominant state in this bin.
    const counts = new Map<CellState, number>();
    for (let i = startIdx; i < endIdx; i++) {
      counts.set(cells[i], (counts.get(cells[i]) ?? 0) + 1);
    }

    let dominant: CellState = 'pending';
    let maxCount = 0;
    for (const [state, count] of counts) {
      if (count > maxCount) {
        maxCount = count;
        dominant = state;
      }
    }

    // Bucket index drives the phase, so the frontier still reads as a
    // shimmering band a few buckets wide.
    ctx.globalAlpha = alphaFor(dominant, col, palette, frame, reducedMotion);
    ctx.fillStyle = palette[dominant].color;
    ctx.fillRect(col, 0, 1, height);
  }

  ctx.globalAlpha = 1;
}
