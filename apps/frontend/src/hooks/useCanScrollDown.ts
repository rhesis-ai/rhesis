'use client';

import { type RefObject, useEffect, useState } from 'react';

/**
 * Whether `ref`'s element has content hidden below its visible area. Tracks
 * scrolling and size changes of the element and its direct children (e.g. a
 * section expanding), so it stays right without polling.
 */
export function useCanScrollDown(ref: RefObject<HTMLElement | null>): boolean {
  const [canScrollDown, setCanScrollDown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      // 1px slack: fractional scaling can leave scrollTop just short of the end.
      setCanScrollDown(el.scrollHeight - el.scrollTop - el.clientHeight > 1);
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

  return canScrollDown;
}
