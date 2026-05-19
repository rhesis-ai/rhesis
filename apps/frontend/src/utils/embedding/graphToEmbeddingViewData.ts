import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';

export interface EmbeddingViewLabel {
  x: number;
  y: number;
  text: string;
}

export interface EmbeddingViewData {
  x: Float32Array;
  y: Float32Array;
  category: Uint8Array;
  labels: EmbeddingViewLabel[];
  entityIds: string[];
  texts: string[];
  clusterNames: string[];
}

/** Map HDBSCAN cluster_index values to contiguous 0-based category indices for EmbeddingView. */
function buildCategoryIndexMap(clusterIndices: number[]): Map<number, number> {
  const unique = [...new Set(clusterIndices)].sort((a, b) => a - b);
  const map = new Map<number, number>();
  unique.forEach((clusterIndex, category) => {
    map.set(clusterIndex, category);
  });
  return map;
}

function clusterCentroid(
  graph: Scatter2DGraph,
  clusterIndex: number
): { x: number; y: number } | null {
  const members = graph.points.filter(p => p.cluster_index === clusterIndex);
  if (members.length === 0) {
    return null;
  }
  const sum = members.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), {
    x: 0,
    y: 0,
  });
  return { x: sum.x / members.length, y: sum.y / members.length };
}

export function graphToEmbeddingViewData(
  graph: Scatter2DGraph
): EmbeddingViewData | null {
  const { points } = graph;
  if (points.length === 0) {
    return null;
  }

  const n = points.length;
  const x = new Float32Array(n);
  const y = new Float32Array(n);
  const category = new Uint8Array(n);
  const entityIds: string[] = new Array(n);
  const texts: string[] = new Array(n);

  const categoryMap = buildCategoryIndexMap(points.map(p => p.cluster_index));

  const clusterLabelMap = new Map(
    graph.clusters.map(c => [c.cluster_index, c.label])
  );

  const clusterNames: string[] = new Array(n);

  for (let i = 0; i < n; i++) {
    const point = points[i];
    x[i] = point.x;
    y[i] = point.y;
    category[i] = categoryMap.get(point.cluster_index) ?? 0;
    entityIds[i] = point.entity_id;
    texts[i] = point.searchable_text;
    clusterNames[i] = clusterLabelMap.get(point.cluster_index) ?? '';
  }

  const labels: EmbeddingViewLabel[] = graph.clusters
    .map(cluster => {
      const centroid = clusterCentroid(graph, cluster.cluster_index);
      if (!centroid) {
        return null;
      }
      return {
        x: centroid.x,
        y: centroid.y,
        text: cluster.label,
      };
    })
    .filter((label): label is EmbeddingViewLabel => label !== null);

  return { x, y, category, labels, entityIds, texts, clusterNames };
}
