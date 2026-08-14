import { UUID } from 'crypto';
import { Status } from './tests';
import { Tag } from './tag';
import { FileResponse } from './file';
import type { WithPermittedActions } from '@/types/affordances';

// Override marker added by backend when a human review changes a metric or turn value
export interface OverrideMarker {
  original_value: boolean;
}

// Metric interfaces
export interface MetricResult {
  score: number | string;
  reason: string;
  backend: string;
  threshold?: number;
  description: string;
  is_successful: boolean;
  override?: OverrideMarker;
}

export interface TestMetrics {
  metrics: {
    [key: string]: MetricResult;
  };
  execution_time: number;
}

// Penelope multi-turn conversation interfaces
export interface SentFile {
  filename: string;
  content_type?: string;
}

export interface ConversationTurn {
  turn: number;
  timestamp: string;
  penelope_reasoning: string;
  penelope_message: string;
  target_response: string;
  context?: unknown[];
  metadata?: Record<string, unknown>;
  tool_calls?: Array<Record<string, unknown>>;
  session_id: string;
  success: boolean;
  override?: OverrideMarker;
  penelope_files?: FileResponse[];
  /** Files sent to the target in this turn (filename + content_type only, populated by Penelope). */
  sent_files?: SentFile[] | null;
}

export interface CriterionEvaluation {
  criterion: string;
  met: boolean;
  evidence: string;
  reasoning: string;
  relevant_turns: number[];
}

export interface GoalEvaluation {
  all_criteria_met: boolean;
  reason: string;
  evidence: string[];
  criteria_evaluations: CriterionEvaluation[];
}

export interface TestOutput {
  // Single-turn fields
  output: string;
  context: string[];
  metadata?: Record<string, unknown>;

  // Multi-turn (Penelope) fields
  goal?: string;
  goal_achieved?: boolean;
  turns_used?: number;
  conversation_summary?: ConversationTurn[];
  goal_evaluation?: GoalEvaluation;
  stats?: {
    total_turns?: number;
  };
  // Multi-turn test configuration (this is where the actual config lives in test_output)
  test_configuration?: {
    goal?: string;
    max_turns?: number;
    instructions?: string;
    restrictions?: string | null;
    scenario?: string | null;
  };
  // Status field for multi-turn tests
  status?: 'success' | 'failure' | 'timeout' | 'error';
}

// Test Reviews interfaces

export const REVIEW_TARGET_TYPES = {
  TEST_RESULT: 'test_result',
  TURN: 'turn',
  METRIC: 'metric',
} as const;

export type ReviewTargetType =
  (typeof REVIEW_TARGET_TYPES)[keyof typeof REVIEW_TARGET_TYPES];

export const REVIEW_TARGET_LABELS: Record<ReviewTargetType, string> = {
  [REVIEW_TARGET_TYPES.TEST_RESULT]: 'Test Result',
  [REVIEW_TARGET_TYPES.TURN]: 'Turn',
  [REVIEW_TARGET_TYPES.METRIC]: 'Metric',
};

export interface ReviewUser {
  user_id: UUID;
  name: string;
}

export interface ReviewStatus {
  name: string;
}

export interface ReviewTarget {
  type: ReviewTargetType;
  reference: string | null;
}

export interface Review {
  review_id: UUID;
  status: ReviewStatus;
  user: ReviewUser;
  comments: string;
  created_at: string;
  updated_at: string;
  target: ReviewTarget;
  resolved?: boolean;
  permitted_actions?: string[];
}

export interface TestReviews {
  reviews: Review[];
}

export interface TestRun {
  id: UUID;
  name?: string;
}

// Reference interfaces for nested objects in TestReference
export interface PromptReference {
  id: UUID;
  nano_id?: string;
  content: string;
  expected_response?: string;
  counts?: {
    comments: number;
    tasks: number;
  };
}

export interface RequirementReference {
  id: UUID;
  name: string;
  description?: string;
}

export interface TestReference {
  id: UUID;
  prompt?: PromptReference;
  requirement?: RequirementReference;
}

// Base interface for test results
export interface TestResultBase {
  test_configuration_id: UUID;
  test_run_id?: UUID;
  prompt_id?: UUID;
  test_id?: UUID;
  test_metrics?: TestMetrics;
  test_reviews?: TestReviews;
  test_output?: TestOutput;
}

export type TestResultCreate = TestResultBase;

export type TestResultUpdate = Partial<TestResultBase>;

export interface ReviewSummaryEntry {
  target_type: string;
  reference: string | null;
  status: ReviewStatus;
  review_id: string;
}

export interface TestResult extends TestResultBase, WithPermittedActions {
  id: UUID;
  created_at: string;
  updated_at: string;
  last_review?: Review;
  matches_review?: boolean;
  review_summary?: Record<string, ReviewSummaryEntry>;
}

export interface TestResultDetail extends TestResult {
  status?: Status;
  test_run?: TestRun;
  test?: TestReference;
  tags?: Tag[];
  counts?: {
    comments: number;
    tasks: number;
  };
}

// Shared pass/fail counts used by Insights UI and test-run summary cards.
export interface PassFailStats {
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}
