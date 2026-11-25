'use client';

import { useEffect, useState } from 'react';
import { Autocomplete, Box, Button, TextField } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import BaseDrawer from '@/components/common/BaseDrawer';
import RunDrawerScheduleSection from '@/components/common/run-drawer/RunDrawerScheduleSection';
import {
  defaultScheduleForm,
  toScheduleSpec,
  type ScheduleForm,
} from '@/components/common/run-drawer/schedule-form';
import { testSetKeys } from '@/constants/query-keys';
import { useEndpoints } from '@/hooks/useEndpoints';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { getApiErrorMessage } from '@/utils/error-utils';
import { useNotifications } from '@/components/common/NotificationContext';
import { useScheduleActions } from './useSchedules';

interface Props {
  open: boolean;
  /** A day picked on the calendar (YYYY-MM-DD); the form starts on it. */
  initialDate?: string | null;
  onClose: () => void;
  /** Open the full run drawer in schedule mode, carrying these fields over. */
  onMoreOptions: (form: ScheduleForm) => void;
}

interface Option {
  id: string;
  name: string;
}

/** The short way to schedule: test set, endpoint, when. Everything else uses defaults. */
export default function ScheduleCreateDrawer({
  open,
  initialDate,
  onClose,
  onMoreOptions,
}: Props) {
  const actions = useScheduleActions();
  const notifications = useNotifications();
  const [form, setForm] = useState<ScheduleForm>(() => defaultScheduleForm());
  const [testSet, setTestSet] = useState<Option | null>(null);
  const [endpoint, setEndpoint] = useState<Option | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const base = defaultScheduleForm();
    setForm(initialDate ? { ...base, repeat: false, date: initialDate } : base);
    setTestSet(null);
    setEndpoint(null);
    setError(null);
  }, [open, initialDate]);

  const testSets = useQuery({
    queryKey: testSetKeys.list('schedule-create', 0, 100),
    queryFn: () =>
      new ApiClientFactory().getTestSetsClient().getTestSets({ limit: 100 }),
    enabled: open,
  });
  const endpoints = useEndpoints({ limit: 100 }, open);
  const testSetOptions: Option[] = (testSets.data?.data ?? []).map(t => ({
    id: String(t.id),
    name: t.name,
  }));
  const endpointOptions: Option[] = (endpoints.data ?? []).map(e => ({
    id: String(e.id),
    name: e.name,
  }));
  const sdk =
    (endpoints.data ?? []).find(e => String(e.id) === endpoint?.id)
      ?.connection_type === 'SDK';

  const save = async () => {
    if (!testSet || !endpoint) return;
    setSaving(true);
    setError(null);
    try {
      const created = await new ApiClientFactory()
        .getTestRunSchedulesClient()
        .create({
          test_set_id: testSet.id,
          endpoint_id: endpoint.id,
          schedule: toScheduleSpec(form),
        });
      await actions.refresh();
      notifications.show(`Scheduled ${created[0]?.name ?? testSet.name}`, {
        severity: 'success',
      });
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not create the schedule'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="New schedule"
      loading={saving}
      onSave={save}
      saveButtonText="Schedule"
      saveDisabled={!testSet || !endpoint || Boolean(previewError)}
      error={error}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Autocomplete
          options={testSetOptions}
          value={testSet}
          onChange={(_, value) => setTestSet(value)}
          getOptionLabel={option => option.name}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          loading={testSets.isLoading}
          renderInput={params => (
            <TextField {...params} label="Test set" required />
          )}
        />
        <Autocomplete
          options={endpointOptions}
          value={endpoint}
          onChange={(_, value) => setEndpoint(value)}
          getOptionLabel={option => option.name}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          loading={endpoints.isLoading}
          renderInput={params => (
            <TextField {...params} label="Endpoint" required />
          )}
        />
        <RunDrawerScheduleSection
          form={form}
          onChange={setForm}
          onPreviewError={setPreviewError}
          showName
          sdkEndpoint={sdk}
        />
        <Box>
          <Button onClick={() => onMoreOptions(form)}>
            More options (metrics, models, tags)
          </Button>
        </Box>
      </Box>
    </BaseDrawer>
  );
}
