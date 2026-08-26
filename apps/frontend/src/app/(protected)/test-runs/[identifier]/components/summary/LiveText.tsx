'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import { useRunClock } from './RunClockProvider';

interface LiveTextProps {
  render: (t: number) => string;
  className?: string;
}

function LiveTextInner({ render, className }: LiveTextProps) {
  const spanRef = useRef<HTMLSpanElement>(null);
  const renderRef = useRef(render);
  renderRef.current = render;
  const clock = useRunClock();

  const update = useCallback((t: number) => {
    const span = spanRef.current;
    if (!span) return;
    const text = renderRef.current(t);
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
