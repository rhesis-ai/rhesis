import type { CellState } from '../verdict-model';
import { paintStrip, shouldBin, describeStrip } from '../verdict-strip-render';

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
  inFlight: { color: '#ccc', alpha: 0.8 },
};

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
  it('paints per-cell at correct x offsets', () => {
    const { ctx, calls } = fakeContext();
    const cells: CellState[] = ['passed', 'failed', 'pending'];
    paintStrip(ctx, {
      width: 72,
      height: 20,
      dpr: 1,
      cells,
      palette,
      binned: false,
    });

    const fillCalls = calls.filter(c => c.method === 'fillRect');
    expect(fillCalls).toHaveLength(3);
    expect(fillCalls[0].args[0]).toBe(0);
    expect(fillCalls[1].args[0]).toBe(24);
    expect(fillCalls[2].args[0]).toBe(48);
  });

  it('caps cell width at 24px', () => {
    const { ctx, calls } = fakeContext();
    paintStrip(ctx, {
      width: 200,
      height: 20,
      dpr: 1,
      cells: ['passed'],
      palette,
      binned: false,
    });

    const fillCalls = calls.filter(c => c.method === 'fillRect');
    expect(fillCalls).toHaveLength(1);
    // drawWidth = min(24, 200/1) = 24; cellWidth = max(1, 24-0) = 24
    expect(fillCalls[0].args[2]).toBe(24);
  });

  it('uses strokeRect for error cells', () => {
    const { ctx, calls } = fakeContext();
    paintStrip(ctx, {
      width: 100,
      height: 20,
      dpr: 1,
      cells: ['error'],
      palette,
      binned: false,
    });

    const strokeCalls = calls.filter(c => c.method === 'strokeRect');
    const fillCalls = calls.filter(c => c.method === 'fillRect');
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
    });

    expect(calls.filter(c => c.method === 'fillRect')).toHaveLength(0);
    expect(calls.filter(c => c.method === 'strokeRect')).toHaveLength(0);
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
