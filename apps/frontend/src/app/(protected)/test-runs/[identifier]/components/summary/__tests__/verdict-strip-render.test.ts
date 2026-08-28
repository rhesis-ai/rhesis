import type { CellState } from '../verdict-model';
import type { RunClockFrame } from '../run-clock';
import {
  paintStrip,
  shouldBin,
  describeStrip,
  alphaFor,
  failRingAlpha,
} from '../verdict-strip-render';

type Call = { method: string; args: unknown[] };

function fakeContext(): {
  ctx: CanvasRenderingContext2D;
  calls: Call[];
} {
  const calls: Call[] = [];
  const ctx = {
    clearRect: jest.fn((...args: unknown[]) =>
      calls.push({ method: 'clearRect', args })
    ),
    save: jest.fn(),
    restore: jest.fn(),
    scale: jest.fn(),
    beginPath: jest.fn((...args: unknown[]) =>
      calls.push({ method: 'beginPath', args })
    ),
    roundRect: jest.fn((...args: unknown[]) =>
      calls.push({ method: 'roundRect', args })
    ),
    rect: jest.fn((...args: unknown[]) => calls.push({ method: 'rect', args })),
    fill: jest.fn((...args: unknown[]) => calls.push({ method: 'fill', args })),
    stroke: jest.fn((...args: unknown[]) =>
      calls.push({ method: 'stroke', args })
    ),
    fillRect: jest.fn((...args: unknown[]) =>
      calls.push({ method: 'fillRect', args })
    ),
    strokeRect: jest.fn((...args: unknown[]) =>
      calls.push({ method: 'strokeRect', args })
    ),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    globalAlpha: 1,
  } as unknown as CanvasRenderingContext2D;
  return { ctx, calls };
}

const palette: Record<CellState, { color: string; alpha: number }> = {
  pending: { color: '#ccc', alpha: 1 },
  passed: { color: '#0f0', alpha: 1 },
  failed: { color: '#f00', alpha: 1 },
  scored: { color: '#ff0', alpha: 1 },
  error: { color: '#f00', alpha: 1 },
  na: { color: '#999', alpha: 0.5 },
  generating: { color: '#fb0', alpha: 0.3 },
  evaluating: { color: '#fb0', alpha: 0.85 },
};

/**
 * A run still in flight, so no completion transition is in play.
 *
 * `wall` defaults to `clock`, which is the 1x case. Pass it separately to
 * cover a catch-up, where run time outpaces real time.
 */
function runningFrame(clock = 0, wall = clock): RunClockFrame {
  return { clock, t: clock, sinceComplete: -Infinity, isTerminal: false, wall };
}

function completedFrame(sinceComplete: number): RunClockFrame {
  return {
    clock: 100,
    t: 100,
    sinceComplete,
    isTerminal: true,
    wall: 100,
  };
}

describe('shouldBin', () => {
  it('does not bin when width per cell is at least the minimum', () => {
    // 300px / 100 cells = 3px/cell, at the default 3px minimum
    expect(shouldBin(100, 300)).toBe(false);
  });

  it('bins once width per cell drops below the minimum', () => {
    // 300px / 101 cells < 3px/cell
    expect(shouldBin(101, 300)).toBe(true);
  });

  it('is width-aware: a narrower strip bins sooner than a wide one', () => {
    const cellCount = 100;
    // 230px (Numbers+shape) gives 2.3px/cell -> bins
    expect(shouldBin(cellCount, 230)).toBe(true);
    // 900px (Detail, wide 1fr) gives 9px/cell -> does not bin
    expect(shouldBin(cellCount, 900)).toBe(false);
  });

  it('never bins zero cells', () => {
    expect(shouldBin(0, 300)).toBe(false);
  });

  it('respects a custom minimum cell width', () => {
    expect(shouldBin(50, 100, 1)).toBe(false); // 2px/cell >= 1px min
    expect(shouldBin(150, 100, 1)).toBe(true); // 0.67px/cell < 1px min
  });
});

describe('paintStrip', () => {
  it('paints per-cell at correct x offsets, with rounded corners', () => {
    const { ctx, calls } = fakeContext();
    const cells: CellState[] = ['passed', 'failed', 'pending'];
    paintStrip(ctx, {
      width: 72,
      height: 20,
      dpr: 1,
      cells,
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    const roundRectCalls = calls.filter(c => c.method === 'roundRect');
    const fillCalls = calls.filter(c => c.method === 'fill');
    expect(roundRectCalls).toHaveLength(3);
    expect(fillCalls).toHaveLength(3);
    expect(roundRectCalls[0].args[0]).toBe(0);
    expect(roundRectCalls[1].args[0]).toBe(24);
    expect(roundRectCalls[2].args[0]).toBe(48);
    // Radius is clamped to half the smaller dimension, never a raw magic
    // number bigger than the cell itself.
    for (const call of roundRectCalls) {
      expect(call.args[4]).toBeLessThanOrEqual(20 / 2);
    }
  });

  it('fills the full width when there are few cells', () => {
    const { ctx, calls } = fakeContext();
    paintStrip(ctx, {
      width: 200,
      height: 20,
      dpr: 1,
      cells: ['passed'],
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    const roundRectCalls = calls.filter(c => c.method === 'roundRect');
    expect(roundRectCalls).toHaveLength(1);
    // A single cell has no gap, so it draws at the strip's full width --
    // no fixed cap left to clamp it and cluster it at the left edge.
    expect(roundRectCalls[0].args[2]).toBe(200);
  });

  it('divides the width evenly, with a 1px gap, across a handful of cells', () => {
    const { ctx, calls } = fakeContext();
    const cells: CellState[] = [
      'passed',
      'passed',
      'failed',
      'passed',
      'failed',
    ];
    paintStrip(ctx, {
      width: 200,
      height: 20,
      dpr: 1,
      cells,
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    const roundRectCalls = calls.filter(c => c.method === 'roundRect');
    expect(roundRectCalls).toHaveLength(5);
    // drawWidth = 200 / 5 = 40; cellWidth = 40 - 1 (gap) = 39.
    for (const call of roundRectCalls) {
      expect(call.args[2]).toBe(39);
    }
    // Cells are evenly spaced across the full width, not clustered at the start.
    const xs = roundRectCalls.map(c => c.args[0]);
    expect(xs).toEqual([0, 40, 80, 120, 160]);
  });

  it('clamps the corner radius to half the smaller dimension for a thin cell', () => {
    const { ctx, calls } = fakeContext();
    // 40 cells in 40px -> 1px-wide cells, well under the 2px radius.
    const cells: CellState[] = Array(40).fill('passed');
    paintStrip(ctx, {
      width: 40,
      height: 20,
      dpr: 1,
      cells,
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    const roundRectCalls = calls.filter(c => c.method === 'roundRect');
    for (const call of roundRectCalls) {
      const [, , w, h, radius] = call.args as number[];
      expect(radius).toBeLessThanOrEqual(Math.min(w, h) / 2);
    }
  });

  it('falls back to a square-cornered rect when roundRect is unsupported', () => {
    const { ctx, calls } = fakeContext();
    // Simulate an environment without the CanvasRenderingContext2D.roundRect
    // method (a real fallback path, not just an implementation detail).
    delete (ctx as unknown as Record<string, unknown>).roundRect;

    paintStrip(ctx, {
      width: 100,
      height: 20,
      dpr: 1,
      cells: ['passed'],
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    expect(calls.filter(c => c.method === 'roundRect')).toHaveLength(0);
    expect(calls.filter(c => c.method === 'rect')).toHaveLength(1);
    expect(calls.filter(c => c.method === 'fill')).toHaveLength(1);
  });

  it('strokes (not fills) rounded corners for error cells', () => {
    const { ctx, calls } = fakeContext();
    paintStrip(ctx, {
      width: 100,
      height: 20,
      dpr: 1,
      cells: ['error'],
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    const strokeCalls = calls.filter(c => c.method === 'stroke');
    const fillCalls = calls.filter(c => c.method === 'fill');
    const roundRectCalls = calls.filter(c => c.method === 'roundRect');
    expect(roundRectCalls).toHaveLength(1);
    expect(strokeCalls).toHaveLength(1);
    expect(fillCalls).toHaveLength(0);
  });

  it('bails on zero width', () => {
    const { ctx, calls } = fakeContext();
    paintStrip(ctx, {
      width: 0,
      height: 20,
      dpr: 1,
      cells: ['passed'],
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    expect(calls.filter(c => c.method === 'roundRect')).toHaveLength(0);
    expect(calls.filter(c => c.method === 'fill')).toHaveLength(0);
    expect(calls.filter(c => c.method === 'stroke')).toHaveLength(0);
  });

  it('scales by DPR', () => {
    const { ctx } = fakeContext();
    paintStrip(ctx, {
      width: 100,
      height: 20,
      dpr: 2,
      cells: ['passed'],
      palette,
      binned: false,
      frame: runningFrame(),
      reducedMotion: false,
    });

    expect(ctx.scale).toHaveBeenCalledWith(2, 2);
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 200, 40);
  });

  it('uses binned path for >250 cells', () => {
    const { ctx, calls } = fakeContext();
    const cells: CellState[] = Array(300).fill('passed');
    paintStrip(ctx, {
      width: 100,
      height: 20,
      dpr: 1,
      cells,
      palette,
      binned: true,
      frame: runningFrame(),
      reducedMotion: false,
    });

    const fillCalls = calls.filter(c => c.method === 'fillRect');
    // Binned mode: one fill per pixel column, not per cell
    expect(fillCalls.length).toBeLessThan(cells.length);
    expect(fillCalls.length).toBe(100);
  });
});

describe('describeStrip', () => {
  it('describes a strip with no failures', () => {
    const cells: CellState[] = ['passed', 'passed', 'pending'];
    expect(describeStrip('ASI02', cells)).toBe('ASI02: 2 of 3 tests passed.');
  });

  it('describes a single failure by 1-indexed position', () => {
    const cells: CellState[] = [
      'passed',
      'passed',
      'passed',
      'passed',
      'passed',
      'failed',
    ];
    expect(describeStrip('ASI02', cells)).toBe(
      'ASI02: 5 of 6 tests passed. Failure at test 6.'
    );
  });

  it('lists up to 5 failures by position', () => {
    const cells: CellState[] = [
      'failed',
      'passed',
      'failed',
      'passed',
      'failed',
    ];
    expect(describeStrip('ASI02', cells)).toBe(
      'ASI02: 2 of 5 tests passed. Failures at tests 1, 3, 5.'
    );
  });

  it('truncates beyond 5 failures to 3 examples and a count of the rest', () => {
    // 25 tests, 12 of them failed -- matches the spec's own example shape
    // ("...failures at tests 6, 15, 24 and 9 others.").
    const cells: CellState[] = Array(25).fill('passed');
    for (const pos of [6, 15, 24, 1, 2, 3, 4, 5, 7, 8, 9, 10]) {
      cells[pos - 1] = 'failed';
    }

    const result = describeStrip('ASI02', cells);
    // describeStrip lists failures in strip order (ascending position), so
    // the first 3 encountered are 1, 2, 3, not the spec's illustrative
    // 6/15/24 -- the truncation shape (3 examples + "and N others") matches.
    expect(result).toContain('Failures at tests 1, 2, 3 and 9 others.');
  });

  it('treats error states as failures', () => {
    const cells: CellState[] = ['passed', 'error'];
    expect(describeStrip('ASI02', cells)).toBe(
      'ASI02: 1 of 2 tests passed. Failure at test 2.'
    );
  });

  it('handles an empty strip', () => {
    expect(describeStrip('ASI02', [])).toBe('ASI02: no tests.');
  });
});

describe('alphaFor in-flight pulses', () => {
  // The two in-flight states must be tellable apart by pulse alone, so their
  // alpha bands are required never to overlap at any point in either cycle.
  it('keeps the generating and evaluating bands disjoint', () => {
    let genMax = -Infinity;
    let evalMin = Infinity;
    for (let clock = 0; clock < 10; clock += 0.01) {
      const frame = runningFrame(clock);
      genMax = Math.max(
        genMax,
        alphaFor('generating', 0, palette, frame, false)
      );
      evalMin = Math.min(
        evalMin,
        alphaFor('evaluating', 0, palette, frame, false)
      );
    }
    expect(genMax).toBeLessThan(evalMin);
  });

  it('keeps generating dimmer than a resolved cell', () => {
    for (let clock = 0; clock < 5; clock += 0.05) {
      const alpha = alphaFor(
        'generating',
        0,
        palette,
        runningFrame(clock),
        false
      );
      expect(alpha).toBeLessThan(palette.passed.alpha);
    }
  });

  it('oscillates rather than holding steady', () => {
    const samples = new Set<number>();
    for (let clock = 0; clock < 2; clock += 0.05) {
      samples.add(
        Math.round(
          alphaFor('generating', 0, palette, runningFrame(clock), false) * 1000
        )
      );
    }
    expect(samples.size).toBeGreaterThan(5);
  });

  it('pulses evaluating faster than generating', () => {
    const zeroCrossings = (state: CellState) => {
      let crossings = 0;
      let previous = alphaFor(state, 0, palette, runningFrame(0), false);
      for (let clock = 0.01; clock < 4; clock += 0.01) {
        const current = alphaFor(state, 0, palette, runningFrame(clock), false);
        const base = palette[state].alpha;
        if (previous < base !== current < base) crossings++;
        previous = current;
      }
      return crossings;
    };
    expect(zeroCrossings('evaluating')).toBeGreaterThan(
      zeroCrossings('generating')
    );
  });

  // Without a per-column phase offset every in-flight cell pulses in unison
  // and the row reads as a flashing warning light instead of a travelling wave.
  it('offsets the pulse by column', () => {
    const frame = runningFrame(1.2);
    const first = alphaFor('generating', 0, palette, frame, false);
    const later = alphaFor('generating', 5, palette, frame, false);
    expect(first).not.toBeCloseTo(later, 3);
  });

  // Catching up runs the clock at REPLAY_RATE. Driving the pulse from run
  // time made it oscillate that many times faster, which is the flicker seen
  // when reloading a long-running run.
  it('keeps the pulse on real time while the clock is catching up', () => {
    const realSeconds = 0.4;
    // Same moment on screen, but run time has advanced 10x.
    const normal = alphaFor(
      'evaluating',
      0,
      palette,
      runningFrame(realSeconds, realSeconds),
      false
    );
    const replaying = alphaFor(
      'evaluating',
      0,
      palette,
      runningFrame(realSeconds * 10, realSeconds),
      false
    );
    expect(replaying).toBeCloseTo(normal, 6);
  });

  it('never leaves the 0..1 alpha range', () => {
    for (let clock = 0; clock < 5; clock += 0.02) {
      for (const state of ['generating', 'evaluating'] as CellState[]) {
        const alpha = alphaFor(state, 3, palette, runningFrame(clock), false);
        expect(alpha).toBeGreaterThanOrEqual(0);
        expect(alpha).toBeLessThanOrEqual(1);
      }
    }
  });
});

describe('alphaFor completion transition', () => {
  it('fades passed cells once the run lands', () => {
    const during = alphaFor('passed', 0, palette, runningFrame(1), false);
    const settled = alphaFor('passed', 0, palette, completedFrame(1), false);
    expect(settled).toBeLessThan(during);
  });

  it('eases the fade rather than snapping', () => {
    const start = alphaFor('passed', 0, palette, completedFrame(0), false);
    const middle = alphaFor('passed', 0, palette, completedFrame(0.2), false);
    const end = alphaFor('passed', 0, palette, completedFrame(0.4), false);
    expect(middle).toBeLessThan(start);
    expect(end).toBeLessThan(middle);
  });

  it('leaves failed cells at full strength, so contrast lands on them', () => {
    const before = alphaFor('failed', 0, palette, runningFrame(1), false);
    const after = alphaFor('failed', 0, palette, completedFrame(2), false);
    expect(after).toBe(before);
  });

  it('rings failures once, then stops', () => {
    expect(failRingAlpha(completedFrame(0), false)).toBeGreaterThan(0);
    expect(failRingAlpha(completedFrame(0.7), false)).toBeGreaterThan(0);
    expect(failRingAlpha(completedFrame(1.5), false)).toBe(0);
  });

  it('does not ring while the run is still going', () => {
    expect(failRingAlpha(runningFrame(5), false)).toBe(0);
  });

  it('fades the ring out over its lifetime', () => {
    expect(failRingAlpha(completedFrame(1.2), false)).toBeLessThan(
      failRingAlpha(completedFrame(0.2), false)
    );
  });
});

describe('alphaFor under reduced motion', () => {
  it('holds in-flight states flat', () => {
    const first = alphaFor('generating', 0, palette, runningFrame(0.3), true);
    const second = alphaFor('generating', 0, palette, runningFrame(2.9), true);
    expect(first).toBe(second);
  });

  it('still separates the two in-flight states by brightness', () => {
    const frame = runningFrame(1);
    expect(alphaFor('generating', 0, palette, frame, true)).toBeLessThan(
      alphaFor('evaluating', 0, palette, frame, true)
    );
  });

  it('snaps the completion fade instead of easing it', () => {
    const atStart = alphaFor('passed', 0, palette, completedFrame(0), true);
    const later = alphaFor('passed', 0, palette, completedFrame(0.4), true);
    expect(atStart).toBe(later);
  });

  it('suppresses the failure ring entirely', () => {
    expect(failRingAlpha(completedFrame(0.1), true)).toBe(0);
  });

  // Colour still changes as verdicts land: that is information, not decoration.
  it('keeps resolved states at their palette colour', () => {
    expect(alphaFor('failed', 0, palette, runningFrame(1), true)).toBe(
      palette.failed.alpha
    );
  });
});
