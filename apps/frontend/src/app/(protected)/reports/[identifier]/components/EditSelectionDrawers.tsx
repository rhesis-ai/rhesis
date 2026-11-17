'use client';

import * as React from 'react';
import { Stack } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import type {
  ReportDetail,
  ReportUpdate,
} from '@/utils/api-client/interfaces/report';
import RunsStep, {
  RunSourceSelect,
  type RunSource,
} from '@/components/reports/picker/RunsStep';
import RequirementsStep from '@/components/reports/picker/RequirementsStep';
import {
  useEndpointRuns,
  useRequirementOptions,
} from '@/components/reports/picker/useReportPickerData';
import { ReportReloadError } from './useReport';

interface DrawerProps {
  report: ReportDetail;
  onClose: () => void;
  update: (body: ReportUpdate) => Promise<void>;
}

function sameSet(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every(id => b.includes(id));
}

function useSave(
  update: (body: ReportUpdate) => Promise<void>,
  onClose: () => void
) {
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | undefined>();
  const save = async (body: ReportUpdate) => {
    setSaving(true);
    setError(undefined);
    try {
      await update(body);
      onClose();
    } catch (e) {
      setError(
        e instanceof ReportReloadError
          ? 'Saved, but the page could not reload. Refresh the page.'
          : 'Failed to save. Please try again.'
      );
    } finally {
      setSaving(false);
    }
  };
  return { save, saving, error };
}

export function EditRunsDrawer({ report, onClose, update }: DrawerProps) {
  const initialSource: RunSource = report.run_tag ? 'tag' : 'manual';
  const initial = report.test_run_ids.map(String);
  const [source, setSource] = React.useState<RunSource>(initialSource);
  // Switching a tag report to picking by hand starts from the runs the tag matched.
  const [selected, setSelected] = React.useState<string[]>(
    initialSource === 'tag' ? report.tagged_run_ids.map(String) : initial
  );
  const [tag, setTag] = React.useState(report.run_tag ?? '');
  const { runs, loading, failed, truncated } = useEndpointRuns(
    report.endpoint_id
  );
  const { save, saving, error } = useSave(update, onClose);

  const unchanged =
    source === initialSource &&
    (source === 'tag'
      ? tag.trim() === (report.run_tag ?? '')
      : sameSet(selected, initial));
  const empty = source === 'tag' ? !tag.trim() : selected.length === 0;

  return (
    <BaseDrawer
      open
      onClose={onClose}
      title="Test runs in this report"
      width="75%"
      onSave={() =>
        void save(
          source === 'tag'
            ? { run_tag: tag.trim() }
            : { run_tag: null, test_run_ids: selected }
        )
      }
      saveButtonText="Save"
      saveDisabled={empty || unchanged}
      loading={saving}
      error={error ?? (failed ? 'Failed to load test runs' : undefined)}
    >
      <Stack spacing={3}>
        <RunSourceSelect value={source} onChange={setSource} />
        <RunsStep
          source={source}
          runs={runs}
          loading={loading}
          selected={selected}
          onChange={setSelected}
          tag={tag}
          onTagChange={setTag}
          truncated={truncated}
        />
      </Stack>
    </BaseDrawer>
  );
}

export function EditRequirementsDrawer({
  report,
  onClose,
  update,
}: DrawerProps) {
  const initial = report.requirement_ids.map(String);
  const [selected, setSelected] = React.useState<string[]>(initial);
  const { requirements, tested, loading, failed, truncated } =
    useRequirementOptions(
      [...report.test_run_ids, ...report.tagged_run_ids].map(String)
    );
  const { save, saving, error } = useSave(update, onClose);

  return (
    <BaseDrawer
      open
      onClose={onClose}
      title="Requirements in this report"
      width="75%"
      onSave={() => void save({ requirement_ids: selected })}
      saveButtonText="Save"
      saveDisabled={sameSet(selected, initial)}
      loading={saving}
      error={error ?? (failed ? 'Failed to load requirements' : undefined)}
    >
      <RequirementsStep
        requirements={requirements}
        loading={loading}
        tested={tested}
        selected={selected}
        onChange={setSelected}
        truncated={truncated}
      />
    </BaseDrawer>
  );
}
