import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

/** 'Low temp v2'; undefined for a run without an experiment. */
export function experimentLabel(
  experiment:
    | { name?: string | null; version?: string | null }
    | null
    | undefined
): string | undefined {
  if (!experiment) return undefined;
  return (
    [experiment.name, experiment.version].filter(Boolean).join(' ') || undefined
  );
}

/** The experiment a listed run took its parameters from, read from its snapshot. */
export function runExperimentLabel(run: TestRunDetail): string | undefined {
  if (!run.experiment_id) return undefined;
  const name = run.attributes?.parameter_experiment_name;
  const version = run.attributes?.parameter_version;
  return experimentLabel({
    name: typeof name === 'string' ? name : 'Experiment',
    version: typeof version === 'string' ? version : undefined,
  });
}
