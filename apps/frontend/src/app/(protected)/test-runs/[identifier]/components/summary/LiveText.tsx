'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import { useRunClock } from './RunClockProvider';
import type { RunClockFrame } from './run-clock';

interface LiveTextProps {
  render: (frame: RunClockFrame) => string;
  className?: string;
}

function LiveTextInner({ render, className }: LiveTextProps) {
  const spanRef = useRef<HTMLSpanElement>(null);
  const renderRef = useRef(render);
  renderRef.current = render;
  const clock = useRunClock();

  const update = useCallback((frame: RunClockFrame) => {
    const span = spanRef.current;
    if (!span) return;
    const text = renderRef.current(frame);
    if (span.textContent !== text) {
      span.textContent = text;
    }
  }, []);

  useEffect(() => {
    return clock.subscribeText(update);
  }, [clock, update]);

  // Initial render.
  useEffect(() => {
    clock.poke();
  }, [clock]);

  return <span ref={spanRef} className={className} />;
}

const LiveText = React.memo(LiveTextInner);
LiveText.displayName = 'LiveText';
export default LiveText;
