import { UUID } from 'crypto';
import { TestSet } from './test-set';
import { Endpoint } from './endpoint';

/**
 * Enum for tracking the source of metrics used in a test execution.
 * Must match the backend MetricsSource enum in schemas/test_set.py
 */
export enum MetricsSource {
  REQUIREMENT = 'requirement',
  TEST_SET = 'test_set',
  EXECUTION_TIME = 'execution_time',
}

/**
 * Helper to get display label for MetricsSource
 */
export function getMetricsSourceLabel(source: MetricsSource | string): string {
  switch (source) {
    case MetricsSource.REQUIREMENT:
      return 'Requirement';
    case MetricsSource.TEST_SET:
      return 'Test Set';
    case MetricsSource.EXECUTION_TIME:
      return 'Execution-Time';
    default:
      return 'Unknown';
  }
}

/**
 * Execution metric stored in test configuration attributes
 */
export interface ExecutionMetric {
  id: string;
  name: string;
  scope?: string[];
}

/**
 * Typed test configuration attributes
 */
export interface TestConfigurationAttributes {
  execution_mode?: 'Parallel' | 'Sequential';
  metrics?: ExecutionMetric[];
  metrics_source?: MetricsSource;
  [key: string]: unknown;
}

// Test Configuration interfaces
export interface TestConfigurationBase {
  endpoint_id: UUID;
  test_set_id: UUID;
  user_id: UUID;
  attributes?: TestConfigurationAttributes;
}

export interface TestConfigurationCreate extends Omit<
  TestConfigurationBase,
  'user_id'
> {
  user_id?: UUID;
}

export type TestConfigurationUpdate = Partial<TestConfigurationBase>;

export interface TestConfiguration extends TestConfigurationBase {
  id: UUID;
}

export interface TestConfigurationDetail extends TestConfiguration {
  endpoint?: Endpoint;
  test_set?: TestSet;
}
