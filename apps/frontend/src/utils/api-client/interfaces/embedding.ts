export interface ScatterPoint2D {
  entity_id: string;
  cluster_index: number;
  searchable_text: string;
  x: number;
  y: number;
}

export interface Cluster {
  cluster_index: number;
  label: string;
}

export interface Scatter2DGraph {
  computed_at: string;
  clusters: Cluster[];
  points: ScatterPoint2D[];
}

export type EmbeddingGraphGetResponse =
  | { status: 'pending' }
  | { status: 'ready'; graph: Scatter2DGraph };
