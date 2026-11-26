/**
 * Starts one run per (test set × experiment version) through the server, which checks
 * every set and the quota for the whole group before any run starts. Runs of one group
 * share a ``batch_id`` (``test_run.attributes.batch_*``), so they can be found as a unit.
 */

import type { UUID } from 'crypto';
import type { TestRunsClient } from '@/utils/api-client/test-runs-client';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type {
  TestRunBatchCreate,
  TestRunBatchMember,
} from '@/utils/api-client/interfaces/test-run-batch';
import { TagsClient } from '@/utils/api-client/tags-client';
import { EntityType, type TagCreate } from '@/utils/api-client/interfaces/tag';

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
  /** The started run. */
  result: TestRunBatchMember;
}

export interface BatchRunOutcome {
  /** Empty when the group was a single run. */
  batch_id: string;
  members: BatchRunMember[];
}

interface ExecuteBatchedTestRunsParams {
  testRunsClient: TestRunsClient;
  /** The test sets to run; or `testSetTag` to run every set carrying a tag. */
  testSetIds?: string[];
  testSetTag?: string;
  endpointId: string;
  /** Each set runs once per experiment; empty runs each set once. */
  selectedExperiments: SelectedExperiment[];
  /**
   * Settings shared by every run (execution mode, models, metrics, scoring target, …),
   * in the shape the drawer builds them.
   */
  baseAttributes: Record<string, unknown>;
}

/** Splits the drawer's flat attributes into the request's run settings. */
function toRunSettings(
  attributes: Record<string, unknown>
): NonNullable<TestRunBatchCreate['run_settings']> {
  const {
    metrics,
    reference_test_run_id,
    execution_model_id,
    evaluation_model_id,
    tests_tagged,
    ...executionOptions
  } = attributes;
  return {
    execution_options: executionOptions,
    ...(Array.isArray(metrics) && metrics.length > 0
      ? {
          metrics: metrics as NonNullable<
            TestRunBatchCreate['run_settings']
          >['metrics'],
        }
      : {}),
    ...(typeof reference_test_run_id === 'string'
      ? { reference_test_run_id }
      : {}),
    ...(typeof execution_model_id === 'string' ? { execution_model_id } : {}),
    ...(typeof evaluation_model_id === 'string' ? { evaluation_model_id } : {}),
    ...(Array.isArray(tests_tagged) && tests_tagged.length > 0
      ? { tests_tagged: tests_tagged as string[] }
      : {}),
  };
}

/** Starts the group. Errors propagate: the server starts nothing when it refuses. */
export async function executeBatchedTestRuns({
  testRunsClient,
  testSetIds,
  testSetTag,
  endpointId,
  selectedExperiments,
  baseAttributes,
}: ExecuteBatchedTestRunsParams): Promise<BatchRunOutcome> {
  if (!testSetTag && (!testSetIds || testSetIds.length === 0)) {
    return { batch_id: '', members: [] };
  }

  const batch = await testRunsClient.startBatch({
    ...(testSetTag
      ? { test_set_tag: testSetTag }
      : { test_set_ids: testSetIds }),
    endpoint_id: endpointId,
    experiments: selectedExperiments.map(exp => ({
      experiment_id: String(exp.experiment_id),
      version: exp.version,
    })),
    run_settings: toRunSettings(baseAttributes),
  });

  return {
    batch_id: batch.batch_id ?? '',
    members: batch.members.map(member => ({
      test_set_id: member.test_set_id,
      experiment:
        selectedExperiments.find(
          exp =>
            String(exp.experiment_id) === member.experiment_id &&
            exp.version === member.version
        ) ?? null,
      result: member,
    })),
  };
}

/**
 * The one run an execute/re-run outcome started, for callers that redirect straight to
 * it. Null for a group of several runs (no single run to show) or when the run can't
 * be loaded; callers keep their previous behaviour then.
 */
export async function resolveSingleCreatedRun(
  outcome: BatchRunOutcome,
  testRunsClient: TestRunsClient
): Promise<TestRunDetail | null> {
  if (outcome.members.length !== 1) return null;
  const testRunId = outcome.members[0].result.test_run_id;
  if (!testRunId) return null;
  try {
    return await testRunsClient.getTestRun(testRunId);
  } catch {
    return null;
  }
}

/**
 * URL for the "go watch this run" redirect after an execute/rerun resolves
 * a single run -- Detail view, so the animation is visible immediately
 * instead of landing on whatever density the viewer last had stored. See
 * useDensityPreference's `forceDensity`. The one place this literal is
 * written, so both callers stay in sync if the target view ever changes.
 */
export function watchRunHref(testRunId: string): string {
  return `/test-runs/${testRunId}?density=detail`;
}

interface AssignTagsToRunsParams {
  outcome: BatchRunOutcome;
  tags: string[];
  organizationId: UUID | string;
  userId?: string;
}

export async function assignTagsToRuns({
  outcome,
  tags,
  organizationId,
  userId,
}: AssignTagsToRunsParams): Promise<void> {
  if (tags.length === 0) return;

  const tagsClient = new TagsClient();

  for (const member of outcome.members) {
    const testRunId = member.result.test_run_id;
    if (!testRunId) continue;

    for (const tagName of tags) {
      const tagPayload: TagCreate = {
        name: tagName,
        ...(organizationId && { organization_id: organizationId as UUID }),
        ...(userId && { user_id: userId as UUID }),
      };
      await tagsClient.assignTagToEntity(
        EntityType.TEST_RUN,
        testRunId,
        tagPayload
      );
    }
  }
}
