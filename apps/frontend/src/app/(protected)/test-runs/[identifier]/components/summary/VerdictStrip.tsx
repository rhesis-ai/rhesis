'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import type { CellState } from './verdict-model';
import { useVerdictPalette, GEOMETRY, DURATIONS } from './summary-tokens';
import { paintStrip, shouldBin } from './verdict-strip-render';
import { useRunClock } from './RunClockProvider';
import type { RunClockFrame } from './run-clock';
import { useReducedMotion } from '@/hooks/useReducedMotion';

interface VerdictStripProps {
  /**
   * Cell states at a given moment. A function rather than an array so every
   * frame re-derives state from the run's timing -- there is no per-cell
   * animation state to drift out of sync with the data.
   */
  cellsAt: (t: number) => CellState[];
  dataVersion: number;
  height?: number;
  /** Text equivalent for the canvas, e.g. from describeStrip(). */
  ariaLabel: string;
  onBinnedChange?: (binned: boolean) => void;
}

function VerdictStripInner({
  cellsAt,
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

  const cellsAtRef = useRef(cellsAt);
  cellsAtRef.current = cellsAt;
  const paletteRef = useRef(palette);
  paletteRef.current = palette;
  const reducedMotionRef = useRef(reducedMotion);
  reducedMotionRef.current = reducedMotion;

  const paint = useCallback((frame: RunClockFrame) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { width, height: h } = sizeRef.current;
    if (width <= 0 || h <= 0) return;

    const dpr = window.devicePixelRatio || 1;
    const pxW = Math.round(width * dpr);
    const pxH = Math.round(h * dpr);
    if (canvas.width !== pxW) canvas.width = pxW;
    if (canvas.height !== pxH) canvas.height = pxH;

    const cells = cellsAtRef.current(frame.t);

    const binned = shouldBin(cells.length, width);
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
      cells,
      palette: paletteRef.current,
      binned,
      frame,
      reducedMotion: reducedMotionRef.current,
    });
  }, []);

  useEffect(() => {
    return clock.subscribeFrame(paint);
  }, [clock, paint]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    // Height comes from the observed box, not the prop: during the density
    // morph the CSS height is mid-transition, and sizing the canvas to the
    // target instead would stretch it for the length of the morph.
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height: observed } = entry.contentRect;
        sizeRef.current = { width, height: observed };
        clock.poke();
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [clock]);

  // Repaint when the data behind cellsAt changes.
  useEffect(() => {
    clock.poke();
  }, [cellsAt, clock]);

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
