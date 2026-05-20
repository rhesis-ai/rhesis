import {
  buildEmbeddingChartColorConfig,
  UNASSIGNED_COLOR_LABEL,
} from '../embeddingColorBy';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';

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
      searchable_text: 'one',
      x: 0,
      y: 0,
    },
    {
      embedding_id: 'e2',
      entity_id: 't2',
      entity_type: 'Test',
      cluster_index: 0,
      searchable_text: 'two',
      x: 1,
      y: 0,
    },
    {
      embedding_id: 'e3',
      entity_id: 't3',
      entity_type: 'Test',
      cluster_index: 1,
      searchable_text: 'three',
      x: 5,
      y: 5,
    },
  ],
};

const sampleTests: TestDetail[] = [
  {
    id: 't1',
    created_at: '',
    updated_at: '',
    behavior: { id: 'b1', name: 'Helpful' },
    category: { id: 'c1', name: 'Support' },
    topic: { id: 'tp1', name: 'Refunds' },
  },
  {
    id: 't2',
    created_at: '',
    updated_at: '',
    behavior: { id: 'b1', name: 'Helpful' },
    category: { id: 'c2', name: 'Billing' },
    topic: { id: 'tp2', name: 'Invoices' },
  },
  {
    id: 't3',
    created_at: '',
    updated_at: '',
    behavior: { id: 'b2', name: 'Strict' },
  },
];

describe('buildEmbeddingChartColorConfig', () => {
  it('returns cluster labels in cluster mode', () => {
    const config = buildEmbeddingChartColorConfig(
      sampleGraph,
      sampleTests,
      'cluster'
    );
    expect(config).not.toBeNull();
    expect(config?.labels).toHaveLength(2);
    expect(config?.viewMode).toBe('density');
    expect(config?.legend.some(l => l.label === 'Safety')).toBe(true);
  });

  it('colors by behavior with unassigned bucket', () => {
    const config = buildEmbeddingChartColorConfig(
      sampleGraph,
      sampleTests,
      'behavior'
    );
    expect(config).not.toBeNull();
    expect(config?.viewMode).toBe('points');
    expect(config?.labels).toBeNull();
    expect(config?.category.length).toBe(3);
    expect(config?.legend.find(l => l.label === 'Helpful')?.count).toBe(2);
    expect(config?.legend.find(l => l.label === 'Strict')?.count).toBe(1);
  });

  it('colors by category', () => {
    const config = buildEmbeddingChartColorConfig(
      sampleGraph,
      sampleTests,
      'category'
    );
    expect(config?.legend.map(l => l.label)).toEqual(
      expect.arrayContaining(['Support', 'Billing'])
    );
  });

  it('assigns unassigned when test metadata is missing', () => {
    const config = buildEmbeddingChartColorConfig(sampleGraph, [], 'topic');
    expect(config?.category.every(c => c === 0)).toBe(true);
    expect(config?.legend).toEqual([
      {
        label: UNASSIGNED_COLOR_LABEL,
        color: '#9e9e9e',
        count: 3,
      },
    ]);
  });
});
