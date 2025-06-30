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
}

// Stats interfaces for test results
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