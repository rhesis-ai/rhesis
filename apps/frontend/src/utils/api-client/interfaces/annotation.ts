export type AnnotationSource = 'test_result' | 'trace';

export interface AnnotationStatus {
  status_id?: string;
  name?: string;
}

export interface AnnotationUser {
  user_id?: string;
  name?: string;
}

export interface AnnotationTarget {
  type?: string;
  reference?: string | null;
}

export interface AnnotationListItem {
  review_id: string;
  source: AnnotationSource;
  comments: string;
  created_at?: string | null;
  updated_at?: string | null;
  status: AnnotationStatus;
  user: AnnotationUser;
  target: AnnotationTarget;
  resolved?: boolean;
  test_result_id?: string | null;
  test_run_id?: string | null;
  trace_db_id?: string | null;
  trace_id?: string | null;
  project_id?: string | null;
  span_name?: string | null;
}

export interface AnnotationsQueryParams {
  skip?: number;
  limit?: number;
  source?: AnnotationSource;
  search?: string;
  resolved?: boolean;
  rating?: 'Pass' | 'Fail';
  target_type?: 'test_result' | 'trace' | 'metric' | 'turn';
}

export const ANNOTATION_SOURCE_LABELS: Record<AnnotationSource, string> = {
  test_result: 'Test Result',
  trace: 'Trace',
};

export const ANNOTATION_TARGET_LABELS: Record<string, string> = {
  test_result: 'Test Result',
  test: 'Test Result',
  trace: 'Trace',
  turn: 'Turn',
  metric: 'Metric',
};
