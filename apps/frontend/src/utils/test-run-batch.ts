/**
 * Helper for fanning out a single "execute test set" intent into one
 * run per (test set × experiment) combination, grouped under a shared
 * ``batch_id`` so the resulting test runs can be discovered as a unit.
 *
 * Why fan-out instead of one parent run:
 * - Each run already owns its own status, results, and pass rate; a
 *   single row that hides N sub-runs would either lie about progress
 *   or require a new aggregating row type.
 * - The existing UI grid already displays many runs efficiently; with
 *   the ``batch_id`` stamped on each, filtering/grouping is additive
 *   instead of structural.
 *
 * The ``batch_*`` metadata rides through ``execution_options`` on the
 * request, lands on the test_configuration row, and is lifted onto
 * ``test_run.attributes`` by the worker (see
 * ``apps/backend/src/rhesis/backend/tasks/execution/run.py``). The
 * existing experiment fields (``experiment_id`` + ``experiment_version``)
 * keep their normal path through ``parameters_ref`` so the parameter
 * snapshot stays correct per run.
 */

import type { UUID } from 'crypto';
import type { TestSetsClient } from '@/utils/api-client/test-sets-client';
import type { TestRunsClient } from '@/utils/api-client/test-runs-client';
import { TagsClient } from '@/utils/api-client/tags-client';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import type { TagCreate } from '@/utils/api-client/interfaces/tag';
import { pollForTestRun } from '@/utils/test-run-utils';

export interface SelectedExperiment {
  /** Experiment UUID. */
  experiment_id: UUID | string;
  /** Display name carried for downstream UI / metadata, not for resolution. */
  experiment_name: string;
  /**
   * Version hash to pin. Required: the picker always resolves to a
   * concrete version (latest by default, or a user-pinned one, or the
   * newly-saved one when values were edited).
   */
  version: string;
}

export interface BatchRunMember {
  test_set_id: string;
  experiment: SelectedExperiment | null;
  /** Raw response from ``executeTestSet``. */
  result: unknown;
}

export interface BatchRunOutcome {
  batch_id: string;
  members: BatchRunMember[];
}

/**
 * Generate a UUIDv4-shaped batch identifier.
 *
 * Uses ``crypto.randomUUID`` when available (every browser the app
 * targets supports it; ``randomUUID`` requires a secure context, which
 * Next.js dev / production both provide). Falls back to a
 * timestamp-suffixed random string for non-secure local fixtures only.
 */
function generateBatchId(): string {
  if (
    typeof globalThis.crypto !== 'undefined' &&
    typeof globalThis.crypto.randomUUID === 'function'
  ) {
    return globalThis.crypto.randomUUID();
  }
  const rand = Math.random().toString(36).slice(2);
  return `batch_${Date.now().toString(36)}_${rand}`;
}

interface ExecuteBatchedTestRunsParams {
  testSetsClient: TestSetsClient;
  /** One or more test sets to execute. */
  testSetIds: string[];
  /** Target endpoint UUID. */
  endpointId: string;
  /**
   * Experiments selected in the picker. Empty array runs each test
   * set once with no experiment association (legacy behaviour).
   */
  selectedExperiments: SelectedExperiment[];
  /**
   * Attributes shared by every member of the batch (execution mode,
   * model overrides, metrics, scoring target, etc.). Per-member fields
   * (``experiment_id``, ``experiment_version``, ``batch_*``) are added
   * by this helper and must not be set by the caller.
   */
  baseAttributes: Record<string, unknown>;
}

/**
 * Fan out into one ``executeTestSet`` call per (test set × experiment).
 *
 * - When ``selectedExperiments`` is empty: one call per test set,
 *   experiment fields omitted, no ``batch_*`` metadata written.
 * - When ``selectedExperiments`` has one entry and ``testSetIds`` has
 *   one entry: a single call with experiment fields set, no
 *   ``batch_*`` metadata written (it's not a batch).
 * - Otherwise: every effective combination becomes its own run, all
 *   sharing a single ``batch_id`` and the full ``batch_experiments``
 *   list so each run can discover its siblings.
 *
 * Returns the shared ``batch_id`` (empty string when not a batch) and
 * the per-member responses. Errors propagate from the underlying
 * ``Promise.all`` so the caller's error handler observes the first
 * failure; partial successes are not silently swallowed.
 */
export async function executeBatchedTestRuns({
  testSetsClient,
  testSetIds,
  endpointId,
  selectedExperiments,
  baseAttributes,
}: ExecuteBatchedTestRunsParams): Promise<BatchRunOutcome> {
  if (testSetIds.length === 0) {
    return { batch_id: '', members: [] };
  }

  const expEntries: Array<SelectedExperiment | null> =
    selectedExperiments.length === 0
      ? [null]
      : (selectedExperiments as Array<SelectedExperiment | null>);

  const totalMembers = testSetIds.length * expEntries.length;
  const isBatch = totalMembers > 1;
  const batchId = isBatch ? generateBatchId() : '';

  const batchExperiments = isBatch
    ? selectedExperiments.map(exp => ({
        experiment_id: exp.experiment_id,
        experiment_name: exp.experiment_name,
        version: exp.version,
      }))
    : null;

  const plans: Array<{
    test_set_id: string;
    experiment: SelectedExperiment | null;
    attributes: Record<string, unknown>;
  }> = [];

  let index = 0;
  for (const test_set_id of testSetIds) {
    for (const exp of expEntries) {
      const memberAttributes: Record<string, unknown> = { ...baseAttributes };
      if (exp) {
        memberAttributes.experiment_id = exp.experiment_id;
        memberAttributes.experiment_version = exp.version;
      }
      if (isBatch) {
        memberAttributes.batch_id = batchId;
        memberAttributes.batch_size = totalMembers;
        memberAttributes.batch_index = index;
        if (batchExperiments) {
          memberAttributes.batch_experiments = batchExperiments;
        }
      }
      plans.push({
        test_set_id,
        experiment: exp,
        attributes: memberAttributes,
      });
      index += 1;
    }
  }

  const responses = await Promise.all(
    plans.map(plan =>
      testSetsClient.executeTestSet(
        plan.test_set_id,
        endpointId,
        plan.attributes
      )
    )
  );

  return {
    batch_id: batchId,
    members: plans.map((plan, i) => ({
      test_set_id: plan.test_set_id,
      experiment: plan.experiment,
      result: responses[i],
    })),
  };
}

interface AssignTagsToRunsParams {
  outcome: BatchRunOutcome;
  testRunsClient: TestRunsClient;
  sessionToken: string;
  tags: string[];
  organizationId: UUID | string;
  userId?: string;
}

export async function assignTagsToRuns({
  outcome,
  testRunsClient,
  sessionToken,
  tags,
  organizationId,
  userId,
}: AssignTagsToRunsParams): Promise<void> {
  if (tags.length === 0) return;

  const tagsClient = new TagsClient(sessionToken);

  for (const member of outcome.members) {
    const resultRecord = member.result as Record<string, unknown>;
    const testConfigurationId =
      (resultRecord?.test_configuration_id as string | undefined) ?? null;
    if (!testConfigurationId) continue;

    const testRun = await pollForTestRun(testRunsClient, testConfigurationId);
    if (!testRun) {
      console.warn(
        `Test run not found for configuration ${testConfigurationId}, tags will not be assigned`
      );
      continue;
    }

    for (const tagName of tags) {
      const tagPayload: TagCreate = {
        name: tagName,
        ...(organizationId && { organization_id: organizationId as UUID }),
        ...(userId && { user_id: userId as UUID }),
      };
      await tagsClient.assignTagToEntity(EntityType.TEST_RUN, testRun.id, tagPayload);
    }
  }
}
