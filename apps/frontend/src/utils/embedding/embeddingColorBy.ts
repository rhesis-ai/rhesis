import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import {
  graphToEmbeddingViewData,
  type EmbeddingViewData,
  type EmbeddingViewLabel,
} from './graphToEmbeddingViewData';

export type EmbeddingColorBy = 'cluster' | 'behavior' | 'category' | 'topic';

export const EMBEDDING_COLOR_BY_OPTIONS: {
  value: EmbeddingColorBy;
  label: string;
}[] = [
  { value: 'cluster', label: 'Cluster' },
  { value: 'behavior', label: 'Behavior' },
  { value: 'category', label: 'Category' },
  { value: 'topic', label: 'Topic' },
];

export const UNASSIGNED_COLOR_LABEL = 'Unassigned';

/** Gray for tests missing the selected dimension. */
export const UNASSIGNED_COLOR = '#9e9e9e';

/** Distinct colors for categorical dimensions (index 1+). */
export const EMBEDDING_CATEGORY_PALETTE = [
  '#1976d2',
  '#2e7d32',
  '#ed6c02',
  '#9c27b0',
  '#d32f2f',
  '#0288d1',
  '#558b2f',
  '#7b1fa2',
  '#c2185b',
  '#00838f',
  '#5d4037',
  '#455a64',
  '#f57c00',
  '#512da8',
  '#00796b',
  '#ad1457',
] as const;

/** Uint8 max; index 0 reserved for unassigned / overflow bucket. */
const MAX_NAMED_CATEGORIES = 254;

const OTHER_COLOR = '#757575';

export interface EmbeddingColorLegendEntry {
  label: string;
  color: string;
  count: number;
}

export interface EmbeddingChartColorConfig {
  category: Uint8Array;
  categoryColors: string[];
  labels: EmbeddingViewLabel[] | null;
  legend: EmbeddingColorLegendEntry[];
  viewMode: 'points' | 'density';
}

function paletteColor(index: number): string {
  return EMBEDDING_CATEGORY_PALETTE[index % EMBEDDING_CATEGORY_PALETTE.length];
}

function getDimensionValue(
  test: TestDetail | undefined,
  colorBy: EmbeddingColorBy
): string | null {
  if (!test) return null;
  switch (colorBy) {
    case 'behavior':
      return test.behavior?.name ?? null;
    case 'category':
      return test.category?.name ?? null;
    case 'topic':
      return test.topic?.name ?? null;
    default:
      return null;
  }
}

function buildClusterLegend(
  graph: Scatter2DGraph
): EmbeddingColorLegendEntry[] {
  const countByCluster = new Map<number, number>();
  for (const point of graph.points) {
    countByCluster.set(
      point.cluster_index,
      (countByCluster.get(point.cluster_index) ?? 0) + 1
    );
  }

  const uniqueIndices = [
    ...new Set(graph.points.map(p => p.cluster_index)),
  ].sort((a, b) => a - b);

  return uniqueIndices
    .map((clusterIndex, i) => {
      const cluster = graph.clusters.find(
        c => c.cluster_index === clusterIndex
      );
      const isNoise = clusterIndex === -1;
      return {
        label:
          cluster?.label ??
          (isNoise ? 'Unclustered' : `Cluster ${clusterIndex}`),
        color: isNoise ? UNASSIGNED_COLOR : paletteColor(i),
        count: countByCluster.get(clusterIndex) ?? 0,
      };
    })
    .filter(entry => entry.count > 0);
}

function buildClusterColorConfig(
  graph: Scatter2DGraph,
  baseViewData: EmbeddingViewData
): EmbeddingChartColorConfig {
  const maxCategoryIndex = baseViewData.category.reduce(
    (max, c) => Math.max(max, c),
    0
  );
  const categoryColors: string[] = [];
  for (let i = 0; i <= maxCategoryIndex; i++) {
    const clusterIndex = [
      ...new Set(graph.points.map(p => p.cluster_index)),
    ].sort((a, b) => a - b)[i];
    categoryColors.push(
      clusterIndex === -1 ? UNASSIGNED_COLOR : paletteColor(i)
    );
  }

  return {
    category: baseViewData.category,
    categoryColors,
    labels: baseViewData.labels,
    legend: buildClusterLegend(graph),
    viewMode: 'density',
  };
}

function buildMetadataColorConfig(
  graph: Scatter2DGraph,
  tests: TestDetail[],
  colorBy: EmbeddingColorBy
): EmbeddingChartColorConfig {
  const testsById = new Map(tests.map(t => [t.id, t]));
  const valueCounts = new Map<string, number>();

  for (const point of graph.points) {
    const raw = getDimensionValue(testsById.get(point.entity_id), colorBy);
    const key = raw?.trim() || UNASSIGNED_COLOR_LABEL;
    valueCounts.set(key, (valueCounts.get(key) ?? 0) + 1);
  }

  const namedValues = [...valueCounts.keys()]
    .filter(k => k !== UNASSIGNED_COLOR_LABEL)
    .sort((a, b) => a.localeCompare(b));

  let valuesForIndex = namedValues;
  let otherCount = 0;
  if (namedValues.length > MAX_NAMED_CATEGORIES) {
    valuesForIndex = namedValues.slice(0, MAX_NAMED_CATEGORIES - 1);
    otherCount = namedValues
      .slice(MAX_NAMED_CATEGORIES - 1)
      .reduce((sum, name) => sum + (valueCounts.get(name) ?? 0), 0);
  }

  const indexByValue = new Map<string, number>();
  indexByValue.set(UNASSIGNED_COLOR_LABEL, 0);
  valuesForIndex.forEach((name, i) => {
    indexByValue.set(name, i + 1);
  });
  const otherIndex = valuesForIndex.length + 1;
  if (otherCount > 0) {
    indexByValue.set('Other', otherIndex);
  }

  const category = new Uint8Array(graph.points.length);
  for (let i = 0; i < graph.points.length; i++) {
    const point = graph.points[i];
    const raw = getDimensionValue(testsById.get(point.entity_id), colorBy);
    const key = raw?.trim() || UNASSIGNED_COLOR_LABEL;
    if (key === UNASSIGNED_COLOR_LABEL) {
      category[i] = 0;
    } else if (indexByValue.has(key)) {
      category[i] = indexByValue.get(key)!;
    } else {
      category[i] = otherIndex;
    }
  }

  const maxIndex = category.reduce((max, c) => Math.max(max, c), 0);
  const categoryColors: string[] = [UNASSIGNED_COLOR];
  for (let i = 1; i <= maxIndex; i++) {
    categoryColors.push(paletteColor(i - 1));
  }
  if (otherCount > 0) {
    categoryColors[otherIndex] = OTHER_COLOR;
  }

  const legend: EmbeddingColorLegendEntry[] = [];
  const unassignedCount = valueCounts.get(UNASSIGNED_COLOR_LABEL) ?? 0;
  if (unassignedCount > 0) {
    legend.push({
      label: UNASSIGNED_COLOR_LABEL,
      color: UNASSIGNED_COLOR,
      count: unassignedCount,
    });
  }
  valuesForIndex.forEach((name, i) => {
    legend.push({
      label: name,
      color: paletteColor(i),
      count: valueCounts.get(name) ?? 0,
    });
  });
  if (otherCount > 0) {
    legend.push({
      label: 'Other',
      color: OTHER_COLOR,
      count: otherCount,
    });
  }

  return {
    category,
    categoryColors,
    labels: null,
    legend,
    viewMode: 'points',
  };
}

export function buildEmbeddingChartColorConfig(
  graph: Scatter2DGraph,
  tests: TestDetail[],
  colorBy: EmbeddingColorBy
): EmbeddingChartColorConfig | null {
  const baseViewData = graphToEmbeddingViewData(graph);
  if (!baseViewData) return null;

  if (colorBy === 'cluster') {
    return buildClusterColorConfig(graph, baseViewData);
  }
  return buildMetadataColorConfig(graph, tests, colorBy);
}

/** Base coordinates and entity ids — shared across color-by modes. */
export function getEmbeddingBaseViewData(
  graph: Scatter2DGraph
): EmbeddingViewData | null {
  return graphToEmbeddingViewData(graph);
}
