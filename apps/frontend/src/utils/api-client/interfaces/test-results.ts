import { UUID } from 'crypto';
import { Status } from './tests';
import { Tag } from './tag';
import { FileResponse } from './file';
import type { WithPermittedActions } from '@/types/affordances';
import type { Execution, Verdict } from '@/constants/outcomes';

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

/**
 * One required/prohibited behaviour from a test's evaluation contract, and whether the
 * target complied with it. Present only when the goal metric used contract-based scoring
 * (see schemas/evaluation_contract.py) rather than scoring the raw goal text directly.
 */
export interface BehaviorVerdict {
  behavior: string;
  kind: 'required' | 'prohibited';
  complied: boolean;
  evidence: string;
  relevant_turns: number[];
}

export interface GoalEvaluation {
  all_criteria_met: boolean;
  reason: string;
  evidence: string[];
  criteria_evaluations: CriterionEvaluation[];
  /** Whether the interpreted contract read this test as adversarial. Contract-scored only. */
  adversarial?: boolean;
  /** Per-behaviour verdicts. Present only for contract-based scoring. */
  behavior_verdicts?: BehaviorVerdict[];
  behaviors_total?: number;
  behaviors_complied?: number;
  behaviors_violated?: number;
  violated_behaviors?: string[];
  /**
   * The evaluation contract used to score this run, echoed alongside the verdicts (see
   * schemas/evaluation_contract.py). Present only for contract-based scoring.
   */
  contract?: {
    adversarial: boolean;
    required_behavior: string[];
    prohibited_behavior: string[];
    simulated_user_objective: string;
  };
}

export interface TestOutput {
  // Single-turn fields.
  // Optional because a failed invocation may produce no model answer at all; read it
  // through getEndpointFailure() (utils/endpoint-failure.ts) rather than assuming a string.
  output?: string;
  context?: string[];
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
  /**
   * Why this result has no metrics and reports Error. Two unrelated writers set it:
   * a multi-turn contract that was stale or too ambiguous to score against
   * (evaluate_multi_turn_metrics / resolve_multi_turn_contract), and a failed
   * invocation, where it holds the same text as `output`.
   */
  error?: string;

  /**
   * Invoker failure detail, present when the target rejected or never answered the call.
   * Written by every invoker via ErrorResponse, and by the batch path's error records.
   * `error_type` is the discriminator: `http_error` for a 4xx/5xx, or an invoker-specific
   * category such as `sdk_timeout` / `network_error` that carries no status code.
   * Read these through getEndpointFailure() rather than individually.
   */
  error_type?: string;
  status_code?: number;
  reason?: string;
  /** The target's own response body, which is usually where the real reason is. */
  response_content?: string;
  /** Pre-existing rows only: the WebSocket invoker used to write the body here. */
  response_body?: string;
  response_headers?: Record<string, unknown>;
  request?: Record<string, unknown>;

  /** Multi-turn: the invoker error is nested in the first turn's tool message. */
  history?: PenelopeTurn[];
}

/**
 * One entry of a Penelope trace's `history`. Only the parts the UI reads are typed: the
 * first `send_message_to_target` interaction is where a multi-turn endpoint failure is
 * recorded, and nothing else in the frontend had been reaching into it.
 */
export interface PenelopeTurn {
  target_interaction?: {
    tool_name?: string;
    tool_message?: {
      content?: string | Record<string, unknown>;
    };
  };
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
  // Source of truth for pass/fail/error -- see constants/outcomes.ts and the
  // backend's app/outcomes.py. Always present; `verdict` is set only when
  // `execution === 'ok'`.
  execution: Execution;
  verdict: Verdict | null;
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
