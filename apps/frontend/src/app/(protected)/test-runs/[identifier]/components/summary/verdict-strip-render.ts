import type { CellState } from './verdict-model';

export interface StripPaintOptions {
  width: number;
  height: number;
  dpr: number;
  cells: CellState[];
  palette: Record<CellState, { color: string; alpha: number }>;
  binned: boolean;
  animationProgress?: number;
}

const CELL_MAX_WIDTH = 24;
const CELL_BORDER_RADIUS = 2;
const MIN_CELL_WIDTH = 3;

// Rounds a cell's corners when the canvas supports it (broadly available;
// falls back to a square corner on an environment that doesn't). Radius is
// clamped to half the smaller dimension so a thin sliver never blobs out
// into an ellipse.
function tracePerCellShape(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number
): void {
  ctx.beginPath();
  const radius = Math.max(0, Math.min(CELL_BORDER_RADIUS, w / 2, h / 2));
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, w, h, radius);
  } else {
    ctx.rect(x, y, w, h);
  }
}

// Width-aware: a narrower strip (e.g. the 230px Numbers+shape strip) crosses
// into binning at a lower cell count than a wide one (e.g. Detail's 1fr) --
// that's correct, not a bug. Below MIN_CELL_WIDTH a per-cell strip
// degenerates into a hairline with no visible gap between cells anyway.
const MAX_LISTED_FAILURES = 5;
const TRUNCATED_FAILURE_EXAMPLES = 3;

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

  let summary = `${label}: ${passed} of ${total} tests passed.`;
  if (failurePositions.length === 0) return summary;

  if (failurePositions.length === 1) {
    summary += ` Failure at test ${failurePositions[0]}.`;
  } else if (failurePositions.length <= MAX_LISTED_FAILURES) {
    summary += ` Failures at tests ${failurePositions.join(', ')}.`;
  } else {
    const shown = failurePositions.slice(0, TRUNCATED_FAILURE_EXAMPLES);
    const rest = failurePositions.length - shown.length;
    summary += ` Failures at tests ${shown.join(', ')} and ${rest} others.`;
  }

  return summary;
}

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
  const { width, height, dpr, cells, palette, binned, animationProgress } =
    opts;
  if (width <= 0 || height <= 0 || cells.length === 0) return;

  ctx.clearRect(0, 0, width * dpr, height * dpr);
  ctx.save();
  ctx.scale(dpr, dpr);

  if (binned) {
    paintBinned(ctx, width, height, cells, palette, animationProgress);
  } else {
    paintPerCell(ctx, width, height, cells, palette, animationProgress);
  }

  ctx.restore();
}

function paintPerCell(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  cells: CellState[],
  palette: Record<CellState, { color: string; alpha: number }>,
  animationProgress?: number
): void {
  const drawWidth = Math.min(CELL_MAX_WIDTH, width / cells.length);
  const gap = cells.length > 1 ? 1 : 0;
  const cellWidth = Math.max(1, drawWidth - gap);

  for (let i = 0; i < cells.length; i++) {
    const state = cells[i];
    const entry = palette[state];
    const x = i * drawWidth;

    let alpha = entry.alpha;
    if (state === 'inFlight' && animationProgress !== undefined) {
      alpha *= 0.5 + 0.5 * Math.sin(animationProgress * Math.PI * 2);
    }

    ctx.globalAlpha = alpha;

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
  }

  ctx.globalAlpha = 1;
}

function paintBinned(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  cells: CellState[],
  palette: Record<CellState, { color: string; alpha: number }>,
  animationProgress?: number
): void {
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

    const entry = palette[dominant];
    let alpha = entry.alpha;
    if (dominant === 'inFlight' && animationProgress !== undefined) {
      alpha *= 0.5 + 0.5 * Math.sin(animationProgress * Math.PI * 2);
    }

    ctx.globalAlpha = alpha;
    ctx.fillStyle = entry.color;
    ctx.fillRect(col, 0, 1, height);
  }

  ctx.globalAlpha = 1;
}
