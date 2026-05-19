'use client';

import { useCallback, useMemo, useRef } from 'react';
import { alpha, useTheme } from '@mui/material/styles';
import {
  EmbeddingView,
  type DataPoint,
  type OverlayProxy,
} from 'embedding-atlas/react';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import {
  graphToEmbeddingViewData,
  type EmbeddingViewData,
} from '@/utils/embedding/graphToEmbeddingViewData';

const VIEW_HEIGHT = 560;
const HOVER_PIXEL_RADIUS = 8;
const HIGHLIGHT_RING_SIZE = 14;

/** Props we pass to customOverlay; embedding-atlas merges in `proxy` at runtime. */
type HighlightOverlayStaticProps = {
  highlightedEntityId: string | null;
  viewData: EmbeddingViewData;
};

type HighlightOverlayProps = HighlightOverlayStaticProps & {
  proxy: OverlayProxy;
};

function updateHighlightRing(
  ring: HTMLDivElement,
  proxy: OverlayProxy | null,
  highlightedEntityId: string | null,
  viewData: EmbeddingViewData
) {
  if (!proxy || !highlightedEntityId) {
    ring.style.display = 'none';
    return;
  }
  const index = viewData.entityIds.indexOf(highlightedEntityId);
  if (index < 0) {
    ring.style.display = 'none';
    return;
  }
  const screen = proxy.location(viewData.x[index], viewData.y[index]);
  ring.style.display = 'block';
  ring.style.left = `${screen.x}px`;
  ring.style.top = `${screen.y}px`;
}

// Suppress the component's built-in tooltip — we have no tooltip of our own either.
class EmptyTooltip {
  constructor(_node: HTMLDivElement, _props: { tooltip: DataPoint }) {}
  update(_props: { tooltip: DataPoint }) {}
  destroy() {}
}

interface EmbeddingAtlasViewProps {
  graph: Scatter2DGraph;
  highlightedEntityId?: string | null;
  onPointSelect?: (entityId: string) => void;
  onPointHover?: (entityId: string | null) => void;
}

export default function EmbeddingAtlasView({
  graph,
  highlightedEntityId = null,
  onPointSelect,
  onPointHover,
}: EmbeddingAtlasViewProps) {
  const theme = useTheme();
  const highlightRingShadow = alpha(theme.palette.primary.main, 0.25);
  const viewData = useMemo(() => graphToEmbeddingViewData(graph), [graph]);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const proxyRef = useRef<OverlayProxy | null>(null);

  const highlightedPoint = useMemo((): DataPoint | null => {
    if (!highlightedEntityId || !viewData) return null;
    const index = viewData.entityIds.indexOf(highlightedEntityId);
    if (index < 0) return null;
    return {
      x: viewData.x[index],
      y: viewData.y[index],
      category: viewData.category[index],
      text: viewData.texts[index],
      identifier: highlightedEntityId,
    };
  }, [highlightedEntityId, viewData]);

  const customOverlay = useMemo(() => {
    if (!viewData) return undefined;
    return {
      class: class HighlightOverlay {
        private ring: HTMLDivElement;

        constructor(node: HTMLDivElement, props: HighlightOverlayProps) {
          proxyRef.current = props.proxy;
          node.style.position = 'absolute';
          node.style.inset = '0';
          node.style.pointerEvents = 'none';
          node.style.overflow = 'hidden';

          this.ring = document.createElement('div');
          this.ring.style.position = 'absolute';
          this.ring.style.width = `${HIGHLIGHT_RING_SIZE}px`;
          this.ring.style.height = `${HIGHLIGHT_RING_SIZE}px`;
          this.ring.style.marginLeft = `-${HIGHLIGHT_RING_SIZE / 2}px`;
          this.ring.style.marginTop = `-${HIGHLIGHT_RING_SIZE / 2}px`;
          this.ring.style.borderRadius = '50%';
          this.ring.style.border =
            '2px solid var(--mui-palette-primary-main, #1976d2)';
          this.ring.style.boxShadow = `0 0 0 2px ${highlightRingShadow}`;
          this.ring.style.display = 'none';
          node.appendChild(this.ring);

          updateHighlightRing(
            this.ring,
            props.proxy,
            props.highlightedEntityId,
            props.viewData
          );
        }

        update(props: HighlightOverlayProps) {
          proxyRef.current = props.proxy;
          updateHighlightRing(
            this.ring,
            props.proxy,
            props.highlightedEntityId,
            props.viewData
          );
        }

        destroy() {
          proxyRef.current = null;
        }
      },
      props: {
        highlightedEntityId,
        viewData,
      } satisfies HighlightOverlayStaticProps,
    };
  }, [highlightedEntityId, viewData, highlightRingShadow]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!viewData || !proxyRef.current || !wrapperRef.current) return;

      const rect = wrapperRef.current.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const proxy = proxyRef.current;

      let bestIndex = -1;
      let bestDist = Infinity;
      for (let i = 0; i < viewData.x.length; i++) {
        const screen = proxy.location(viewData.x[i], viewData.y[i]);
        const dist = Math.hypot(screen.x - px, screen.y - py);
        if (dist < bestDist && dist <= HOVER_PIXEL_RADIUS) {
          bestDist = dist;
          bestIndex = i;
        }
      }

      onPointHover?.(bestIndex >= 0 ? viewData.entityIds[bestIndex] : null);
    },
    [viewData, onPointHover]
  );

  // Kept for click-to-navigate.
  const querySelection = useCallback(
    async (
      x: number,
      y: number,
      unitDistance: number
    ): Promise<DataPoint | null> => {
      if (!viewData) return null;
      const threshold = unitDistance * 10;
      let bestIndex = -1;
      let bestDist = Infinity;
      for (let i = 0; i < viewData.x.length; i++) {
        const dist = Math.hypot(viewData.x[i] - x, viewData.y[i] - y);
        if (dist < bestDist && dist <= threshold) {
          bestDist = dist;
          bestIndex = i;
        }
      }
      if (bestIndex < 0) return null;
      return {
        x: viewData.x[bestIndex],
        y: viewData.y[bestIndex],
        category: viewData.category[bestIndex],
        text: viewData.texts[bestIndex],
        identifier: viewData.entityIds[bestIndex],
      };
    },
    [viewData]
  );

  const handleSelection = useCallback(
    (selection: DataPoint[] | null) => {
      if (!selection?.length || !onPointSelect) return;
      const identifier = selection[0]?.identifier;
      if (identifier != null) onPointSelect(String(identifier));
    },
    [onPointSelect]
  );

  if (!viewData) return null;

  return (
    <div
      ref={wrapperRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => onPointHover?.(null)}
    >
      <EmbeddingView
        data={{
          x: viewData.x as Float32Array<ArrayBuffer>,
          y: viewData.y as Float32Array<ArrayBuffer>,
          category: viewData.category as Uint8Array<ArrayBuffer>,
        }}
        labels={viewData.labels}
        width={null}
        height={VIEW_HEIGHT}
        config={{
          autoLabelEnabled: false,
          mode: 'density',
          colorScheme: 'light',
        }}
        tooltip={highlightedPoint}
        customTooltip={EmptyTooltip}
        customOverlay={customOverlay}
        querySelection={querySelection}
        onSelection={handleSelection}
      />
    </div>
  );
}
