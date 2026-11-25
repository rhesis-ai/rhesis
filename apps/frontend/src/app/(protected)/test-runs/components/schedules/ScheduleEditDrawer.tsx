'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import BaseDrawer from '@/components/common/BaseDrawer';
import { can } from '@/components/common/Can';
import RunDrawerScheduleSection from '@/components/common/run-drawer/RunDrawerScheduleSection';
import {
  formatRunTime,
  fromSchedule,
  toScheduleSpec,
  type ScheduleForm,
  changedFields,
} from '@/components/common/run-drawer/schedule-form';
import { Capability } from '@/constants/capabilities';
import {
  PAUSED_REASON,
  PAUSED_REASON_LABEL,
  SCHEDULE_SCOPE,
  SCHEDULE_STATUS,
  type ScheduleScope,
} from '@/constants/test-run-schedules';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { getApiErrorMessage } from '@/utils/error-utils';
import type { TestRunScheduleDetail } from '@/utils/api-client/interfaces/test-run-schedule';
import ScheduleScopeDialog, { type ScopeOption } from './ScheduleScopeDialog';
import ScheduleStatusChip from './ScheduleStatusChip';
import { useScheduleActions, useScheduleDetail } from './useSchedules';

dayjs.extend(utc);
dayjs.extend(timezone);

/** A run on the calendar: when the schedule put it, and when it runs now. */
export interface OccurrenceRef {
  original: string;
  at: string;
}

interface Props {
  scheduleId: string | null;
  occurrence?: OccurrenceRef | null;
  onClose: () => void;
  onTakeOver: (schedule: TestRunScheduleDetail) => void;
}

type DeleteScope = ScheduleScope | 'whole';

const BOTH_CHANGED =
  "Change the date of this run or the schedule's settings, not both. Undo one of them to save.";

export default function ScheduleEditDrawer({
  scheduleId,
  occurrence,
  onClose,
  onTakeOver,
}: Props) {
  const detail = useScheduleDetail(scheduleId);
  const schedule = detail.data;
  const actions = useScheduleActions();
  const [form, setForm] = useState<ScheduleForm | null>(null);
  const [moveDate, setMoveDate] = useState('');
  const [moveTime, setMoveTime] = useState('');
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [askScope, setAskScope] = useState(false);
  const [askDelete, setAskDelete] = useState(false);
  const [askDiscard, setAskDiscard] = useState(false);

  const initialForm = useMemo(
    () => (schedule ? fromSchedule(schedule) : null),
    [schedule]
  );
  const zone = schedule?.timezone ?? 'UTC';
  const occurrenceLocal = occurrence ? dayjs(occurrence.at).tz(zone) : null;

  // Fill the fields once per opened schedule or run. A refetch while open (after a save,
  // or the minute refresh) must not throw away what the person typed.
  const filledFor = useRef<string | null>(null);
  const filledWith = useRef<ScheduleForm | null>(null);
  const openKey = scheduleId
    ? `${scheduleId}|${occurrence?.original ?? ''}`
    : null;
  useEffect(() => {
    if (!openKey) {
      filledFor.current = null;
      return;
    }
    if (!initialForm) return;
    if (filledFor.current === openKey) {
      // Newer data arrived: take it, unless the person has started editing.
      if (form !== filledWith.current) return;
      filledWith.current = initialForm;
      setForm(initialForm);
      return;
    }
    filledFor.current = openKey;
    filledWith.current = initialForm;
    setForm(initialForm);
    setError(null);
    if (occurrenceLocal) {
      setMoveDate(occurrenceLocal.format('YYYY-MM-DD'));
      setMoveTime(occurrenceLocal.format('HH:mm'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on openKey on purpose
  }, [openKey, initialForm]);

  const repeating = Boolean(schedule?.cron);
  const editable = schedule ? can(schedule, Capability.TestRun.UPDATE) : false;
  const before = initialForm ? toScheduleSpec(initialForm) : null;
  const after = form ? toScheduleSpec(form) : null;
  const settingsChanged =
    before !== null &&
    after !== null &&
    JSON.stringify(before) !== JSON.stringify(after);
  const dateChanged =
    Boolean(occurrenceLocal) &&
    moveDate !== occurrenceLocal?.format('YYYY-MM-DD');
  const timeChanged =
    Boolean(occurrenceLocal) && moveTime !== occurrenceLocal?.format('HH:mm');
  const runChanged = repeating && occurrence && (dateChanged || timeChanged);
  const dirty = settingsChanged || Boolean(runChanged);
  const blockedByBoth = Boolean(runChanged) && dateChanged && settingsChanged;

  const moveTo = () =>
    dayjs
      .tz(`${moveDate} ${moveTime}`, 'YYYY-MM-DD HH:mm', zone)
      .utc()
      .toISOString();

  const finish = useCallback(async () => {
    await actions.refresh();
    setSaving(false);
    onClose();
  }, [actions, onClose]);

  const save = async (scope?: ScheduleScope) => {
    if (!schedule || !before || !after) return;
    const client = new ApiClientFactory().getTestRunSchedulesClient();
    setSaving(true);
    setError(null);
    try {
      if (occurrence && repeating && scope === SCHEDULE_SCOPE.ONE) {
        await client.editOccurrence(schedule.id, occurrence.original, scope, {
          move_to: moveTo(),
        });
      } else if (
        occurrence &&
        repeating &&
        scope === SCHEDULE_SCOPE.FOLLOWING
      ) {
        await client.editOccurrence(schedule.id, occurrence.original, scope, {
          ...changedFields(before, after),
          ...(timeChanged ? { move_to: moveTo() } : {}),
        });
      } else {
        await client.update(schedule.id, changedFields(before, after));
      }
      await finish();
    } catch (err) {
      setSaving(false);
      setError(getApiErrorMessage(err, 'Could not save the schedule.'));
    }
  };

  const handleSave = () => {
    if (occurrence && repeating && runChanged) {
      setAskScope(true);
      return;
    }
    if (occurrence && repeating && settingsChanged) {
      setAskScope(true);
      return;
    }
    void save();
  };

  const remove = async (scope: DeleteScope) => {
    if (!schedule) return;
    const client = new ApiClientFactory().getTestRunSchedulesClient();
    setAskDelete(false);
    setSaving(true);
    try {
      if (scope === 'whole' || !occurrence) {
        await client.remove(schedule.id);
      } else {
        await client.deleteOccurrence(schedule.id, occurrence.original, scope);
      }
      await finish();
    } catch (err) {
      setSaving(false);
      setError(getApiErrorMessage(err, 'Could not delete it.'));
    }
  };

  const requestClose = () => (dirty ? setAskDiscard(true) : onClose());

  const runLabel = occurrenceLocal?.format('ddd D MMM') ?? '';
  const scopeOptions: ScopeOption<ScheduleScope>[] = [
    {
      value: SCHEDULE_SCOPE.ONE,
      label: 'This run only',
      description: `Only the ${runLabel} run changes.`,
      disabledReason: settingsChanged
        ? 'Only the date and time can change for a single run.'
        : undefined,
    },
    {
      value: SCHEDULE_SCOPE.FOLLOWING,
      label: 'This and following runs',
      description: `From ${runLabel} on, every run uses the new settings. Runs that already happened keep theirs.`,
      disabledReason: dateChanged
        ? 'To change which days it runs, change Repeats.'
        : undefined,
    },
  ];
  const deleteOptions: ScopeOption<DeleteScope>[] =
    occurrence && repeating
      ? [
          {
            value: SCHEDULE_SCOPE.ONE,
            label: 'This run only',
            description: `Skip ${runLabel}. The schedule continues.`,
          },
          {
            value: SCHEDULE_SCOPE.FOLLOWING,
            label: 'This and following runs',
            description: `The schedule ends before ${runLabel}.`,
          },
          {
            value: 'whole',
            label: 'The whole schedule',
            description: 'Nothing else runs. Past runs are kept.',
          },
        ]
      : [
          {
            value: 'whole',
            label: 'The whole schedule',
            description: 'Nothing else will run. Its past runs are kept.',
          },
        ];

  const paused = schedule?.status === SCHEDULE_STATUS.PAUSED;
  const needsOwner =
    paused && schedule?.paused_reason === PAUSED_REASON.CREATOR_ACCESS;

  return (
    <>
      <BaseDrawer
        open={Boolean(scheduleId)}
        onClose={requestClose}
        title={schedule?.name ?? 'Schedule'}
        loading={saving}
        onSave={editable ? handleSave : undefined}
        saveButtonText="Save"
        loadingText="Saving..."
        saveDisabled={!dirty || Boolean(previewError) || blockedByBoth}
        error={blockedByBoth ? BOTH_CHANGED : error}
        onDelete={
          schedule && can(schedule, Capability.TestRun.DELETE)
            ? () => setAskDelete(true)
            : undefined
        }
        closeButtonText={editable ? 'Cancel' : 'Close'}
      >
        {!schedule || !form ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                flexWrap: 'wrap',
              }}
            >
              <ScheduleStatusChip schedule={schedule} />
              <Typography variant="body2" color="text.secondary">
                {schedule.repeats} · {schedule.test_set?.name} →{' '}
                {schedule.endpoint?.name}
              </Typography>
            </Box>
            {paused &&
              schedule.paused_reason &&
              schedule.paused_reason !== PAUSED_REASON.USER && (
                <Alert severity="warning">
                  {PAUSED_REASON_LABEL[schedule.paused_reason]}
                  {needsOwner && schedule.owner?.name
                    ? `. ${schedule.owner.name} can no longer run tests here.`
                    : '.'}
                </Alert>
              )}
            {schedule.status === SCHEDULE_STATUS.FINISHED && (
              <Alert severity="success">
                Nothing else is planned. Pick a new date to run it again.
              </Alert>
            )}
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {can(schedule, Capability.TestRun.EXECUTE) && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={async () => {
                    if (await actions.runNow(schedule)) onClose();
                  }}
                >
                  Run now
                </Button>
              )}
              {editable && schedule.status === SCHEDULE_STATUS.SCHEDULED && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => actions.pause(schedule)}
                >
                  Pause
                </Button>
              )}
              {editable && paused && !needsOwner && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => actions.resume(schedule)}
                >
                  Resume
                </Button>
              )}
              {editable &&
                needsOwner &&
                can(schedule, Capability.TestRun.EXECUTE) && (
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => onTakeOver(schedule)}
                  >
                    Take over
                  </Button>
                )}
              <Button
                size="small"
                component={Link}
                href={`/test-runs/schedules/${schedule.id}`}
              >
                Open schedule page
              </Button>
            </Box>

            {occurrence && repeating && (
              <Box>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    mb: 1,
                  }}
                >
                  <Typography variant="subtitle2">
                    This run ({formatRunTime(occurrence.at, zone)})
                  </Typography>
                  {editable && (
                    <Button
                      size="small"
                      onClick={() => void remove(SCHEDULE_SCOPE.ONE)}
                    >
                      Skip this run
                    </Button>
                  )}
                </Box>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    label="Date"
                    type="date"
                    value={moveDate}
                    onChange={e => setMoveDate(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    disabled={!editable}
                    fullWidth
                  />
                  <TextField
                    label={`Time (${zone})`}
                    type="time"
                    value={moveTime}
                    onChange={e => setMoveTime(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    disabled={!editable}
                    fullWidth
                  />
                </Box>
              </Box>
            )}

            {editable ? (
              <RunDrawerScheduleSection
                form={form}
                onChange={setForm}
                onPreviewError={setPreviewError}
                showName
                sdkEndpoint={schedule.endpoint?.connection_type === 'SDK'}
                initialForm={initialForm ?? undefined}
              />
            ) : (
              <Alert severity="info">
                You can see this schedule but not change it.
              </Alert>
            )}
          </Box>
        )}
      </BaseDrawer>

      <ScheduleScopeDialog
        open={askScope}
        title="Save changes to a repeating schedule"
        options={scopeOptions}
        initial={
          settingsChanged ? SCHEDULE_SCOPE.FOLLOWING : SCHEDULE_SCOPE.ONE
        }
        confirmText="Save"
        onCancel={() => setAskScope(false)}
        onConfirm={scope => {
          setAskScope(false);
          void save(scope);
        }}
      />
      <ScheduleScopeDialog<DeleteScope>
        open={askDelete}
        title={
          occurrence && repeating
            ? 'Delete a repeating schedule'
            : `Delete ${schedule?.name ?? 'schedule'}?`
        }
        options={deleteOptions}
        initial={deleteOptions[0].value}
        confirmText="Delete"
        destructive
        onCancel={() => setAskDelete(false)}
        onConfirm={remove}
      />
      <Dialog
        open={askDiscard}
        onClose={() => setAskDiscard(false)}
        maxWidth="xs"
      >
        <DialogTitle>Discard your changes?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Nothing you changed here is saved yet.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAskDiscard(false)}>Keep editing</Button>
          <Button
            color="error"
            onClick={() => {
              setAskDiscard(false);
              onClose();
            }}
          >
            Discard
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
