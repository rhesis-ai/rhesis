'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ScheduleIcon from '@mui/icons-material/Schedule';
import { useQuery } from '@tanstack/react-query';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { getApiErrorMessage } from '@/utils/error-utils';
import { scheduleKeys } from '@/constants/query-keys';
import {
  SCHEDULE_NOTIFY_LABEL,
  SCHEDULE_PREVIEW_DEBOUNCE_MS,
  type ScheduleNotify,
} from '@/constants/test-run-schedules';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  ENDS,
  FREQUENCY,
  FREQUENCY_LABEL,
  LAST_DAY,
  MONTH_DAYS,
  WEEKDAYS,
  formProblems,
  sameTiming,
  formatRunTime,
  timeZones,
  toScheduleSpec,
  type Ends,
  type Frequency,
  type ScheduleForm,
} from './schedule-form';

interface Props {
  form: ScheduleForm;
  onChange: (form: ScheduleForm) => void;
  /** The server refused the spec (shown in the summary box); the drawer disables submit. */
  onPreviewError: (message: string | null) => void;
  /** Show the Name field (the compact create drawer; the run drawer names it after the set). */
  showName?: boolean;
  /** SDK endpoints only answer while the connector is connected. */
  sdkEndpoint?: boolean;
  /** Several test sets: one schedule each. */
  testSetCount?: number;
  /** Editing a stored schedule: its unchanged dates may be in the past. */
  initialForm?: ScheduleForm;
}

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

const SUMMARY_SX = {
  border: 1,
  borderColor: 'divider',
  borderRadius: BORDER_RADIUS.sm,
  p: 2,
  bgcolor: 'action.hover',
} as const;

export default function RunDrawerScheduleSection({
  form,
  onChange,
  onPreviewError,
  showName = false,
  sdkEndpoint = false,
  testSetCount = 1,
  initialForm,
}: Props) {
  const set = <K extends keyof ScheduleForm>(key: K, value: ScheduleForm[K]) =>
    onChange({ ...form, [key]: value });
  const problems = formProblems(form, undefined, initialForm);
  // Unchanged timing was valid when saved; the preview may still refuse a past date.
  const keptTiming = initialForm !== undefined && sameTiming(form, initialForm);
  const zones = useMemo(() => timeZones(), []);

  const specText = JSON.stringify(toScheduleSpec(form));
  const debouncedSpec = useDebounced(specText, SCHEDULE_PREVIEW_DEBOUNCE_MS);
  const hasProblems = Object.keys(problems).length > 0;
  const preview = useQuery({
    queryKey: scheduleKeys.preview(debouncedSpec),
    queryFn: () =>
      new ApiClientFactory()
        .getTestRunSchedulesClient()
        .preview(JSON.parse(debouncedSpec)),
    enabled: !hasProblems,
    retry: false,
  });
  const previewError = preview.error
    ? getApiErrorMessage(preview.error, 'This schedule is not valid.')
    : null;

  useEffect(() => {
    onPreviewError(hasProblems ? 'invalid' : keptTiming ? null : previewError);
  }, [hasProblems, previewError, keptTiming, onPreviewError]);

  return (
    <Box sx={drawerSectionSx}>
      <FormSectionDivider
        headline="Schedule"
        descriptiveText="Each run uses the tests in the set at the time it starts."
      />
      <Box sx={drawerFieldsSx}>
        {showName && (
          <TextField
            label="Name"
            value={form.name}
            onChange={e => set('name', e.target.value)}
            fullWidth
          />
        )}

        <ToggleButtonGroup
          exclusive
          fullWidth
          value={form.repeat ? 'repeat' : 'once'}
          onChange={(_, value) => value && set('repeat', value === 'repeat')}
          aria-label="Run once or repeat"
        >
          <ToggleButton value="once">Run once</ToggleButton>
          <ToggleButton value="repeat">Repeat</ToggleButton>
        </ToggleButtonGroup>

        {form.repeat ? (
          <RepeatFields
            form={form}
            set={set}
            problems={problems}
            serverProblem={previewError}
          />
        ) : (
          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              label="Date"
              type="date"
              value={form.date}
              onChange={e => set('date', e.target.value)}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="Time"
              type="time"
              value={form.time}
              onChange={e => set('time', e.target.value)}
              InputLabelProps={{ shrink: true }}
              error={!!problems.time}
              helperText={problems.time}
              fullWidth
            />
          </Box>
        )}

        <Autocomplete
          options={zones}
          value={form.timezone}
          onChange={(_, value) => value && set('timezone', value)}
          disableClearable
          renderInput={params => <TextField {...params} label="Time zone" />}
        />

        {form.repeat && (
          <EndsFields form={form} set={set} problems={problems} />
        )}

        <FormControl fullWidth>
          <InputLabel id="schedule-notify">Notify me</InputLabel>
          <Select
            labelId="schedule-notify"
            label="Notify me"
            value={form.notify}
            onChange={e => set('notify', e.target.value as ScheduleNotify)}
          >
            {Object.entries(SCHEDULE_NOTIFY_LABEL).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>
            You also hear once after the first run, so you know it works.
          </FormHelperText>
        </FormControl>

        <Box sx={SUMMARY_SX} aria-live="polite">
          {hasProblems ? (
            <Typography variant="body2" color="text.secondary">
              Finish the fields above to see when it runs.
            </Typography>
          ) : previewError ? (
            <Typography variant="body2" color="error">
              {previewError}
            </Typography>
          ) : preview.isLoading || !preview.data ? (
            <>
              <Skeleton width="60%" />
              <Skeleton width="80%" />
              <Skeleton width="40%" />
            </>
          ) : (
            <>
              <Typography
                variant="subtitle2"
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <ScheduleIcon fontSize="small" color="primary" />
                {preview.data.repeats}
              </Typography>
              {form.repeat && preview.data.next.length > 0 && (
                <Typography variant="body2" color="text.secondary">
                  Next:{' '}
                  {preview.data.next
                    .map(at => formatRunTime(at, form.timezone))
                    .join(' · ')}
                </Typography>
              )}
              {testSetCount > 1 && (
                <Typography variant="body2" color="text.secondary">
                  Creates one schedule per selected test set ({testSetCount}).
                </Typography>
              )}
            </>
          )}
        </Box>

        {sdkEndpoint && (
          <Alert severity="info">
            This endpoint runs through the SDK. Scheduled runs only reach it
            while your connector is running.
          </Alert>
        )}
      </Box>
    </Box>
  );
}

type Setter = <K extends keyof ScheduleForm>(
  key: K,
  value: ScheduleForm[K]
) => void;
type Problems = Partial<Record<keyof ScheduleForm, string>>;

function RepeatFields({
  form,
  set,
  problems,
  serverProblem,
}: {
  form: ScheduleForm;
  set: Setter;
  problems: Problems;
  /** Why the server refused the schedule; shown at the cron field, which caused it. */
  serverProblem: string | null;
}) {
  const toggleDay = (day: number) =>
    set(
      'days',
      form.days.includes(day)
        ? form.days.filter(d => d !== day)
        : [...form.days, day]
    );
  return (
    <>
      <FormControl fullWidth>
        <InputLabel id="schedule-frequency">Repeat</InputLabel>
        <Select
          labelId="schedule-frequency"
          label="Repeat"
          value={form.frequency}
          onChange={e => set('frequency', e.target.value as Frequency)}
        >
          {Object.entries(FREQUENCY_LABEL).map(([value, label]) => (
            <MenuItem key={value} value={value}>
              {label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {form.frequency === FREQUENCY.WEEKLY && (
        <FormControl error={!!problems.days}>
          <ToggleButtonGroup aria-label="Days">
            {WEEKDAYS.map(day => (
              <ToggleButton
                key={day.value}
                value={day.value}
                selected={form.days.includes(day.value)}
                onChange={() => toggleDay(day.value)}
                aria-label={day.label}
              >
                {day.short}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          {problems.days && <FormHelperText>{problems.days}</FormHelperText>}
        </FormControl>
      )}

      {form.frequency === FREQUENCY.MONTHLY && (
        <FormControl fullWidth>
          <InputLabel id="schedule-month-day">Day of month</InputLabel>
          <Select
            labelId="schedule-month-day"
            label="Day of month"
            value={form.monthDay}
            onChange={e => set('monthDay', e.target.value)}
          >
            {MONTH_DAYS.map(day => (
              <MenuItem key={day} value={day}>
                {day}
              </MenuItem>
            ))}
            <MenuItem value={LAST_DAY}>Last day</MenuItem>
          </Select>
        </FormControl>
      )}

      {form.frequency === FREQUENCY.CUSTOM ? (
        <TextField
          label="Cron expression"
          value={form.cron}
          onChange={e => set('cron', e.target.value)}
          placeholder="0 9 * * 1-5"
          error={Boolean(problems.cron ?? serverProblem)}
          helperText={
            problems.cron ??
            serverProblem ??
            'Five fields: minute hour day month weekday.'
          }
          inputProps={{ spellCheck: false, style: { fontFamily: 'monospace' } }}
          fullWidth
        />
      ) : form.frequency === FREQUENCY.HOURLY ? (
        <TextField
          label="At minute"
          type="number"
          value={form.minute}
          onChange={e =>
            set(
              'minute',
              Math.min(59, Math.max(0, Number(e.target.value) || 0))
            )
          }
          inputProps={{ min: 0, max: 59 }}
          fullWidth
        />
      ) : (
        <TextField
          label="Time"
          type="time"
          value={form.time}
          onChange={e => set('time', e.target.value)}
          InputLabelProps={{ shrink: true }}
          fullWidth
        />
      )}
    </>
  );
}

function EndsFields({
  form,
  set,
  problems,
}: {
  form: ScheduleForm;
  set: Setter;
  problems: Problems;
}) {
  return (
    <Box sx={{ display: 'flex', gap: 2 }}>
      <FormControl fullWidth>
        <InputLabel id="schedule-ends">Ends</InputLabel>
        <Select
          labelId="schedule-ends"
          label="Ends"
          value={form.ends}
          onChange={e => set('ends', e.target.value as Ends)}
        >
          <MenuItem value={ENDS.NEVER}>Never</MenuItem>
          <MenuItem value={ENDS.ON}>On a date</MenuItem>
          <MenuItem value={ENDS.AFTER}>After a number of runs</MenuItem>
        </Select>
      </FormControl>
      {form.ends === ENDS.ON && (
        <TextField
          label="End date"
          type="date"
          value={form.endsOn}
          onChange={e => set('endsOn', e.target.value)}
          InputLabelProps={{ shrink: true }}
          error={!!problems.endsOn}
          helperText={problems.endsOn}
          fullWidth
        />
      )}
      {form.ends === ENDS.AFTER && (
        <TextField
          label="Runs"
          type="number"
          value={form.maxRuns}
          onChange={e => set('maxRuns', Number(e.target.value))}
          inputProps={{ min: 1 }}
          error={!!problems.maxRuns}
          helperText={problems.maxRuns}
          fullWidth
        />
      )}
    </Box>
  );
}
