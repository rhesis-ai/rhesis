import { UUID } from 'crypto';
import { UserReference, Organization, Status } from './tests';
import { Tag } from './tag';

// Metric interfaces
export interface MetricResult {
  score: number | string;
  reason: string;
  backend: string;
  threshold?: number;
  reference_score?: string;
  description: string;
  is_successful: boolean;
}

export interface TestMetrics {
  metrics: {
    [key: string]: MetricResult;
  };
  execution_time: number;
}

export interface TestOutput {
  output: string;
  context: string[];
  session_id: string;
}

// Test Configuration interfaces
export interface TestSet {
  id: UUID;
  name: string;
  description: string;
  short_description: string;
  slug: string;
  status_id: UUID;
  tags: Tag[];
  license_type_id: UUID;
  attributes: {
    topics: UUID[];
    metadata: Record<string, any>;
    behaviors: UUID[];
    use_cases: UUID[];
    categories: UUID[];
  };
  user_id: UUID;
  owner_id?: UUID;
  assignee_id?: UUID;
  priority?: number;
  is_published: boolean;
  organization_id: UUID;
  visibility: string;
}

export interface Endpoint {
  id: UUID;
  name: string;
  description: string;
  protocol: string;
  url: string;
  auth?: any;
  environment: string;
  config_source: string;
  openapi_spec_url?: string;
  openapi_spec?: any;
  llm_suggestions?: any;
  method: string;
  endpoint_path: string;
  request_headers: Record<string, string>;
  query_params?: any;
  request_body_template: Record<string, any>;
  input_mappings?: any;
  response_format: string;
  response_mappings: Record<string, string>;
  validation_rules?: any;
  project_id: UUID;
  status_id?: UUID;
  user_id?: UUID;
  organization_id: UUID;
}

export interface TestConfiguration {
  id: UUID;
  test_set: TestSet;
  endpoint: Endpoint;
  user_id: UUID;
  organization_id: UUID;
  status_id?: UUID;
}

export interface TestRun {
  id: UUID;
  name?: string;
  user_id: UUID;
  organization_id: UUID;
  status_id: UUID;
  attributes: {
    task_id: UUID;
    started_at: string;
    task_state: string;
    configuration_id: UUID;
  };
  tags: Tag[];
}

export interface TestReference {
  id: UUID;
  user_id: UUID;
  organization_id: UUID;
  status_id: UUID;
  tags: Tag[];
}

// Base interface for test results
export interface TestResultBase {
  test_configuration_id: UUID;
  test_run_id?: UUID;
  prompt_id?: UUID;
  test_id?: UUID;
  status_id?: UUID;
  test_metrics?: TestMetrics;
  test_output?: TestOutput;
  user_id?: UUID;
  organization_id?: UUID;
}

export interface TestResultCreate extends TestResultBase {}

export interface TestResultUpdate extends Partial<TestResultBase> {}

export interface TestResult extends TestResultBase {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface TestResultDetail extends TestResult {
  user?: UserReference;
  organization?: Organization;
  status?: Status;
  test_configuration?: TestConfiguration;
  test_run?: TestRun;
  test?: TestReference;
  tags?: Tag[];
  comments?: Array<{
    id: UUID;
    content: string;
    user_id: UUID;
    user_name: string;
    created_at: string;
    updated_at: string;
    emojis?: Record<string, Array<{ user_id: string; user_name: string }>>;
  }>;
  tasks?: Array<{
    id: UUID;
    title: string;
    description?: string;
    status_id?: UUID;
    assignee_id?: UUID;
    due_date?: string;
    completed_at?: string;
    created_at: string;
    updated_at: string;
  }>;
  counts?: {
    comments: number;
    tasks: number;
  };
}

// Comprehensive stats interfaces based on API documentation
export interface PassFailStats {
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}

export interface MetricPassRates {
  [metricName: string]: PassFailStats;
}

export interface BehaviorPassRates {
  [behaviorName: string]: PassFailStats;
}

export interface CategoryPassRates {
  [categoryName: string]: PassFailStats;
}

export interface TopicPassRates {
  [topicName: string]: PassFailStats;
}

export interface TimelineDataPoint {
  date: string;
  overall: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  };
  metrics?: Record<
    string,
    {
      total: number;
      passed: number;
      failed: number;
      pass_rate: number;
    }
  >;
}

export interface TestRunSummaryItem {
  id: UUID;
  name?: string;
  created_at?: string;
  total_tests?: number;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  started_at?: string;
  overall?: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  };
  metrics?: Record<
    string,
    {
      total: number;
      passed: number;
      failed: number;
      pass_rate: number;
    }
  >;
}

export interface TestResultsStatsMetadata {
  mode: string;
  total_test_results: number;
  total_test_runs: number;
  start_date: string;
  end_date: string;
  period?: string;
  organization_id: UUID;
  test_run_id?: UUID | null;
  available_metrics?: string[];
  available_behaviors?: string[];
  available_categories?: string[];
  available_topics?: string[];
}

// Main comprehensive stats interface
export interface TestResultsStats {
  // Core pass/fail statistics
  overall_pass_rates?: PassFailStats;

  // Metric-level analysis
  metric_pass_rates?: MetricPassRates;

  // Dimensional analysis
  behavior_pass_rates?: BehaviorPassRates;
  category_pass_rates?: CategoryPassRates;
  topic_pass_rates?: TopicPassRates;

  // Time-based analysis
  timeline?: TimelineDataPoint[];

  // Test run comparison
  test_run_summary?: TestRunSummaryItem[];

  // Metadata
  metadata: TestResultsStatsMetadata;
}

// Legacy interface for backward compatibility
export interface TestResultStatsDimensionBreakdown {
  dimension: string;
  total: number;
  breakdown: Record<string, number>;
}

export interface TestResultStatsHistorical {
  period: string;
  start_date: string;
  end_date: string;
  monthly_counts: Record<string, number>;
}

export interface TestResultStats {
  total: number;
  stats: {
    user: TestResultStatsDimensionBreakdown;
    status: TestResultStatsDimensionBreakdown;
    organization: TestResultStatsDimensionBreakdown;
    [key: string]: TestResultStatsDimensionBreakdown;
  };
  metadata: {
    generated_at: string;
    organization_id: UUID;
    entity_type: string;
  };
  history?: TestResultStatsHistorical;
}
