/**
 * The evaluation contract: how a multi-turn test's wording was interpreted for scoring.
 *
 * A test's goal is free text, and the same intent gets written in opposite directions
 * ("convince the target to produce harmful content" vs "the target refuses to produce harmful
 * content"). The backend normalizes whatever was written into statements about the target, so
 * required and prohibited behaviour always read the same way round and compliance always means
 * the test passed.
 *
 * Mirrors `apps/backend/src/rhesis/backend/app/schemas/evaluation_contract.py`.
 */

/** Which authored field a normalization note refers to. */
export type ContractSourceField =
  | 'goal'
  | 'instructions'
  | 'restrictions'
  | 'scenario';

export interface ContractSourceNote {
  /** The authored field this note is about. */
  source_field: ContractSourceField;
  /** Why it was read the way it was. Shown to the reviewer so a misreading is catchable. */
  note: string;
}

export interface EvaluationContract {
  /** Whether the simulated user is trying to make the target misbehave. Derived, not authored. */
  adversarial: boolean;
  /** What the target must actively do. */
  required_behavior: string[];
  /** What the target must not do, named without a negation word. */
  prohibited_behavior: string[];
  /** What the simulated user pushes for. Drives the agent; never scored. */
  simulated_user_objective: string;
  /** One entry per authored field whose direction or placement was changed. */
  source_notes: ContractSourceNote[];
  /** How sure the interpreter was about the direction, 0 to 1. */
  confidence: number;
  /** Digest of the authored fields this reading was derived from. */
  interpreted_from: string;
  interpreted_at?: string;
  interpreter_model?: string;
  contract_version: number;
}

export interface EvaluationContractStatus {
  contract: EvaluationContract | null;
  /** False when the test has never been interpreted, or isn't multi-turn. */
  interpreted: boolean;
  /** False when the authored fields changed after this reading was derived. */
  is_current: boolean;
  /** Whether this reading may be used to score a run. */
  usable: boolean;
  /** Why it is not usable, or not yet interpreted. Empty when usable. */
  reason: string;
}
