import type { UUID } from 'crypto';
import { lightTheme } from '@/styles/theme';
import { EntityType } from '@/types/entity-type';
import {
  buildEmbeddingChartColorConfig,
  getEmbeddingChartColors,
  UNASSIGNED_COLOR_LABEL,
} from '../embeddingColorBy';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';

const uuid = (n: number) =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

const sampleGraph: Scatter2DGraph = {
  computed_at: '2026-01-01T00:00:00Z',
  clusters: [
    { cluster_index: 0, label: 'Safety', size: 2 },
    { cluster_index: 1, label: 'Finance', size: 1 },
  ],
  points: [
    {
      embedding_id: 'e1',
      entity_id: uuid(1),
      entity_type: EntityType.TEST,
      cluster_index: 0,
      searchable_text: 'one',
      x: 0,
      y: 0,
    },
    {
      embedding_id: 'e2',
      entity_id: uuid(2),
      entity_type: EntityType.TEST,
      cluster_index: 0,
      searchable_text: 'two',
      x: 1,
      y: 0,
    },
    {
      embedding_id: 'e3',
      entity_id: uuid(3),
      entity_type: EntityType.TEST,
      cluster_index: 1,
      searchable_text: 'three',
      x: 5,
      y: 5,
    },
  ],
};

const sampleTests: TestDetail[] = [
  {
    id: uuid(1),
    created_at: '',
    updated_at: '',
    behavior: { id: uuid(101), name: 'Helpful' },
    category: { id: uuid(201), name: 'Support' },
    topic: { id: uuid(301), name: 'Refunds' },
  },
  {
    id: uuid(2),
    created_at: '',
    updated_at: '',
    behavior: { id: uuid(101), name: 'Helpful' },
    category: { id: uuid(202), name: 'Billing' },
    topic: { id: uuid(302), name: 'Invoices' },
  },
  {
    id: uuid(3),
    created_at: '',
    updated_at: '',
    behavior: { id: uuid(102), name: 'Strict' },
  },
];

const embeddingColors = getEmbeddingChartColors(lightTheme);

describe('buildEmbeddingChartColorConfig', () => {
  it('returns cluster labels in cluster mode', () => {
    const config = buildEmbeddingChartColorConfig(
      sampleGraph,
      sampleTests,
      'cluster',
      embeddingColors
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
      'behavior',
      embeddingColors
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
      'category',
      embeddingColors
    );
    expect(config?.legend.map(l => l.label)).toEqual(
      expect.arrayContaining(['Support', 'Billing'])
    );
  });

  it('assigns unassigned when test metadata is missing', () => {
    const config = buildEmbeddingChartColorConfig(
      sampleGraph,
      [],
      'topic',
      embeddingColors
    );
    expect(config?.category.every(c => c === 0)).toBe(true);
    expect(config?.legend).toEqual([
      {
        label: UNASSIGNED_COLOR_LABEL,
        color: embeddingColors.unassigned,
        count: 3,
      },
    ]);
  });
});
