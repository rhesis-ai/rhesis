'use client';

import { useCallback, useMemo, useRef } from 'react';
import {
  EmbeddingView,
  type DataPoint,
  type OverlayProxy,
} from 'embedding-atlas/react';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import { graphToEmbeddingViewData } from '@/utils/embedding/graphToEmbeddingViewData';

const VIEW_HEIGHT = 560;
const HOVER_PIXEL_RADIUS = 8;

// Suppress the component's built-in tooltip — we have no tooltip of our own either.
class EmptyTooltip {
  constructor(_node: HTMLDivElement, _props: { tooltip: DataPoint }) {}
  update(_props: { tooltip: DataPoint }) {}
  destroy() {}
}

interface EmbeddingAtlasViewProps {
  graph: Scatter2DGraph;
  onPointSelect?: (entityId: string) => void;
  onPointHover?: (entityId: string | null) => void;
}

export default function EmbeddingAtlasView({
  graph,
  onPointSelect,
  onPointHover,
}: EmbeddingAtlasViewProps) {
  const viewData = useMemo(() => graphToEmbeddingViewData(graph), [graph]);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const proxyRef = useRef<OverlayProxy | null>(null);

  const OverlayCapture = useMemo(() => {
    return class {
      constructor(_node: HTMLDivElement, props: { proxy: OverlayProxy }) {
        proxyRef.current = props.proxy;
      }
      update(props: { proxy: OverlayProxy }) {
        proxyRef.current = props.proxy;
      }
      destroy() {
        proxyRef.current = null;
      }
    };
  }, []);

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
        customTooltip={EmptyTooltip}
        customOverlay={OverlayCapture}
        querySelection={querySelection}
        onSelection={handleSelection}
      />
    </div>
  );
}
