'use client';

import * as React from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  ReportDetail,
  ReportResultRule,
  ReportUpdate,
} from '@/utils/api-client/interfaces/report';
import RunsStep from '../../components/create/RunsStep';
import RequirementsStep from '../../components/create/RequirementsStep';
import {
  useEndpointRuns,
  useRequirementOptions,
} from '../../components/create/useReportPickerData';

interface DrawerProps {
  report: ReportDetail;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

function sameSet(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every(id => b.includes(id));
}

function useSave(
  report: ReportDetail,
  onSaved: () => Promise<void>,
  onClose: () => void
) {
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | undefined>();
  const save = async (body: ReportUpdate) => {
    setSaving(true);
    setError(undefined);
    try {
      await new ApiClientFactory()
        .getReportsClient()
        .updateReport(report.id, body);
      await onSaved();
      onClose();
    } catch {
      setError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };
  return { save, saving, error };
}

export function EditRunsDrawer({ report, onClose, onSaved }: DrawerProps) {
  const initial = report.test_run_ids.map(String);
  const [selected, setSelected] = React.useState<string[]>(initial);
  const [rule, setRule] = React.useState<ReportResultRule>(report.result_rule);
  const { runs, loading, failed } = useEndpointRuns(report.endpoint_id);
  const { save, saving, error } = useSave(report, onSaved, onClose);

  return (
    <BaseDrawer
      open
      onClose={onClose}
      title="Test runs in this report"
      width="75%"
      onSave={() => void save({ test_run_ids: selected, result_rule: rule })}
      saveButtonText="Save"
      saveDisabled={
        selected.length === 0 ||
        (sameSet(selected, initial) && rule === report.result_rule)
      }
      loading={saving}
      error={error ?? (failed ? 'Failed to load test runs' : undefined)}
    >
      <RunsStep
        runs={runs}
        loading={loading}
        selected={selected}
        onChange={setSelected}
        rule={rule}
        onRuleChange={setRule}
      />
    </BaseDrawer>
  );
}

export function EditRequirementsDrawer({
  report,
  onClose,
  onSaved,
}: DrawerProps) {
  const initial = report.requirement_ids.map(String);
  const [selected, setSelected] = React.useState<string[]>(initial);
  const { requirements, tested, loading, failed } = useRequirementOptions(
    report.test_run_ids.map(String)
  );
  const { save, saving, error } = useSave(report, onSaved, onClose);

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
      />
    </BaseDrawer>
  );
}
