'use client';

import { type RefObject, useEffect, useState } from 'react';

interface ScrollEdges {
  canScrollUp: boolean;
  canScrollDown: boolean;
}

/**
 * Whether `ref`'s element has content hidden above or below its visible area.
 * Tracks scrolling and size changes of the element and its direct children
 * (e.g. a section expanding), so it stays right without polling.
 */
export function useScrollEdges(
  ref: RefObject<HTMLElement | null>
): ScrollEdges {
  const [edges, setEdges] = useState<ScrollEdges>({
    canScrollUp: false,
    canScrollDown: false,
  });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      // 1px slack: fractional scaling can leave scrollTop just short of an end.
      const canScrollUp = el.scrollTop > 1;
      const canScrollDown =
        el.scrollHeight - el.scrollTop - el.clientHeight > 1;
      setEdges(prev =>
        prev.canScrollUp === canScrollUp && prev.canScrollDown === canScrollDown
          ? prev
          : { canScrollUp, canScrollDown }
      );
    };

    const resizeObserver =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update);
    const observeAll = () => {
      if (!resizeObserver) return;
      resizeObserver.disconnect();
      resizeObserver.observe(el);
      Array.from(el.children).forEach(child => resizeObserver.observe(child));
    };
    observeAll();

    // Children come and go (e.g. sidebar collapse swaps the brand block).
    const mutationObserver =
      typeof MutationObserver === 'undefined'
        ? null
        : new MutationObserver(() => {
            observeAll();
            update();
          });
    mutationObserver?.observe(el, { childList: true });

    el.addEventListener('scroll', update, { passive: true });
    update();

    return () => {
      el.removeEventListener('scroll', update);
      resizeObserver?.disconnect();
      mutationObserver?.disconnect();
    };
  }, [ref]);

  return edges;
}
