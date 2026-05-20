import { graphToEmbeddingViewData } from '../graphToEmbeddingViewData';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';

const sampleGraph: Scatter2DGraph = {
  computed_at: '2026-01-01T00:00:00Z',
  clusters: [
    { cluster_index: 0, label: 'Safety', size: 2 },
    { cluster_index: 1, label: 'Finance', size: 1 },
  ],
  points: [
    {
      embedding_id: 'e1',
      entity_id: 't1',
      entity_type: 'Test',
      cluster_index: 0,
      searchable_text: 'prompt one',
      x: 0,
      y: 0,
    },
    {
      embedding_id: 'e2',
      entity_id: 't2',
      entity_type: 'Test',
      cluster_index: 0,
      searchable_text: 'prompt two',
      x: 1,
      y: 0,
    },
    {
      embedding_id: 'e3',
      entity_id: 't3',
      entity_type: 'Test',
      cluster_index: 1,
      searchable_text: 'prompt three',
      x: 5,
      y: 5,
    },
    {
      embedding_id: 'e4',
      entity_id: 't4',
      entity_type: 'Test',
      cluster_index: -1,
      searchable_text: 'noise',
      x: -2,
      y: -2,
    },
  ],
};

describe('graphToEmbeddingViewData', () => {
  it('returns null for empty points', () => {
    expect(
      graphToEmbeddingViewData({
        computed_at: '2026-01-01T00:00:00Z',
        clusters: [],
        points: [],
      })
    ).toBeNull();
  });

  it('maps coordinates and categories', () => {
    const result = graphToEmbeddingViewData(sampleGraph);
    expect(result).not.toBeNull();
    if (!result) {
      return;
    }
    expect(result.x.length).toBe(4);
    expect(result.y[0]).toBe(0);
    expect(result.entityIds[2]).toBe('t3');
    expect(result.texts[0]).toBe('prompt one');
  });

  it('builds cluster labels at centroids', () => {
    const result = graphToEmbeddingViewData(sampleGraph);
    expect(result).not.toBeNull();
    if (!result) {
      return;
    }
    expect(result.labels).toHaveLength(2);
    const safety = result.labels.find(l => l.text === 'Safety');
    expect(safety).toEqual({ x: 0.5, y: 0, text: 'Safety' });
  });
});
