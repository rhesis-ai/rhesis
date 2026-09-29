import { UUID } from 'crypto';
import type { AnnotationSummaryEntry } from './annotation';
import { Status } from './tests';
import { Tag } from './tag';
import { FileResponse } from './file';
import type { WithPermittedActions } from '@/types/affordances';
import type { Execution, Verdict } from '@/constants/outcomes';

// Override marker added by backend when a human annotation changes a metric or turn value
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
  /** null when the metric could not reach a verdict (inconclusive). */
  is_successful: boolean | null;
  override?: OverrideMarker;
  /** Set when the metric could not be evaluated. */
  error?: string;
  /** Turns of a multi-turn conversation the judge based its verdict on. */
  relevant_turns?: number[];
  /** Goal Achievement's breakdown, when this result came from a re-score. */
  criteria_evaluations?: CriterionEvaluation[];
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

/**
 * One Goal Achievement criterion and whether the target met it. Contract-scored runs judge the
 * contract's criteria (see schemas/evaluation_contract.py); goal-only runs judge criteria the
 * judge derived from the goal, which are always `required`.
 */
export interface CriterionEvaluation {
  criterion: string;
  kind: 'required' | 'prohibited';
  met: boolean;
  evidence: string;
  relevant_turns: number[];
}

export interface GoalEvaluation {
  all_criteria_met: boolean;
  reason: string;
  evidence: string[];
  criteria_evaluations: CriterionEvaluation[];
  criteria_total?: number;
  criteria_met?: number;
  criteria_failed?: number;
  failed_criteria?: string[];
  /** Whether the interpreted contract read this test as adversarial. Contract-scored only. */
  adversarial?: boolean;
  /**
   * The evaluation contract used to score this run, echoed alongside the criteria (see
   * schemas/evaluation_contract.py). Present only for contract-based scoring.
   */
  contract?: {
    adversarial: boolean;
    required_criteria: string[];
    prohibited_criteria: string[];
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
   * Why this result has no metrics and reports Error. Two unrelated writers set it, with
   * two different types, so narrow before using it as text:
   *
   * - A failed invocation stores the invoker's boolean flag (`true`), with the human text
   *   in `output`/`message`. Read those, or `getEndpointFailure()`, for the reason.
   * - A multi-turn contract that was stale or too ambiguous to score against stores prose
   *   (evaluate_multi_turn_metrics / resolve_multi_turn_contract).
   */
  error?: string | boolean;

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
  test_output?: TestOutput;
}

export type TestResultCreate = TestResultBase;

export type TestResultUpdate = Partial<TestResultBase>;

export interface TestResult extends TestResultBase, WithPermittedActions {
  id: UUID;
  created_at: string;
  updated_at: string;
  /** Newest entity-level annotation, embedded so grids stay synchronous. */
  last_annotation?: AnnotationSummaryEntry;
  /** False when the newest entity-level annotation disagrees with automation. */
  matches_annotation?: boolean;
  /** Newest annotation per target, keyed `target_type` or `target_type:reference`. */
  annotation_summary?: Record<string, AnnotationSummaryEntry>;
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
