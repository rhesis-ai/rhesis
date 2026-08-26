'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import type { CellState } from './verdict-model';
import { useVerdictPalette, GEOMETRY, DURATIONS } from './summary-tokens';
import { paintStrip, shouldBin } from './verdict-strip-render';
import { useRunClock } from './RunClockProvider';
import { useReducedMotion } from '@/hooks/useReducedMotion';

interface VerdictStripProps {
  cells: CellState[];
  dataVersion: number;
  height?: number;
  /** Text equivalent for the canvas, e.g. from describeStrip(). */
  ariaLabel: string;
  onBinnedChange?: (binned: boolean) => void;
}

function VerdictStripInner({
  cells,
  dataVersion: _dataVersion,
  height = GEOMETRY.stripHeight,
  ariaLabel,
  onBinnedChange,
}: VerdictStripProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const sizeRef = useRef({ width: 0, height: 0 });
  const palette = useVerdictPalette();
  const clock = useRunClock();
  const reducedMotion = useReducedMotion();
  const binnedRef = useRef(false);
  const onBinnedChangeRef = useRef(onBinnedChange);
  onBinnedChangeRef.current = onBinnedChange;

  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const paletteRef = useRef(palette);
  paletteRef.current = palette;

  const paint = useCallback((t: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { width, height: h } = sizeRef.current;
    if (width <= 0) return;

    const dpr = window.devicePixelRatio || 1;
    const pxW = Math.round(width * dpr);
    const pxH = Math.round(h * dpr);
    if (canvas.width !== pxW) canvas.width = pxW;
    if (canvas.height !== pxH) canvas.height = pxH;

    const binned = shouldBin(cellsRef.current.length, width);
    if (binned !== binnedRef.current) {
      binnedRef.current = binned;
      onBinnedChangeRef.current?.(binned);
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    paintStrip(ctx, {
      width,
      height: h,
      dpr,
      cells: cellsRef.current,
      palette: paletteRef.current,
      binned,
      animationProgress: (t % 1400) / 1400,
    });
  }, []);

  useEffect(() => {
    return clock.subscribeFrame(paint);
  }, [clock, paint]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        sizeRef.current = { width, height };
        clock.poke();
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [height, clock]);

  // Poke on cells change.
  useEffect(() => {
    clock.poke();
  }, [cells, clock]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height,
        transition: reducedMotion
          ? 'none'
          : `height ${DURATIONS.morph}ms ease-in-out`,
      }}
    >
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={ariaLabel}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
        }}
      />
    </div>
  );
}

const VerdictStrip = React.memo(VerdictStripInner);
VerdictStrip.displayName = 'VerdictStrip';
export default VerdictStrip;
