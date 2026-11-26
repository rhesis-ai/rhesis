'use client';

import React from 'react';
import { Alert, ToggleButton, ToggleButtonGroup } from '@mui/material';
import RunDrawerScheduleSection from './RunDrawerScheduleSection';
import type { ScheduleForm } from './schedule-form';
import { RUN_WHEN, RUN_WHEN_LABEL, type RunWhen } from './run-drawer-types';

interface Props {
  when: RunWhen;
  onWhenChange: (when: RunWhen) => void;
  /** Editing a stored schedule: it can change timing but not become a run. */
  allowNow: boolean;
  form: ScheduleForm;
  onFormChange: (form: ScheduleForm) => void;
  onPreviewError: (message: string | null) => void;
  sdkEndpoint: boolean;
  testSetCount: number;
  initialForm?: ScheduleForm;
  /** Picking a schedule switched Reuse Outputs to fresh outputs. */
  reuseDropped: boolean;
}

/** Run now, once at a set time, or on a repeating schedule. */
export default function WhenField({
  when,
  onWhenChange,
  allowNow,
  form,
  onFormChange,
  onPreviewError,
  sdkEndpoint,
  testSetCount,
  initialForm,
  reuseDropped,
}: Props) {
  const options = allowNow
    ? [RUN_WHEN.NOW, RUN_WHEN.ONCE, RUN_WHEN.REPEAT]
    : [RUN_WHEN.ONCE, RUN_WHEN.REPEAT];

  return (
    <>
      <ToggleButtonGroup
        exclusive
        fullWidth
        value={when}
        onChange={(_, value: RunWhen | null) => value && onWhenChange(value)}
        aria-label="When to run"
      >
        {options.map(option => (
          <ToggleButton key={option} value={option}>
            {RUN_WHEN_LABEL[option]}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {when !== RUN_WHEN.NOW && reuseDropped && (
        <Alert severity="info">
          Scheduled runs always call the endpoint, so this switched to fresh
          outputs.
        </Alert>
      )}
      {when !== RUN_WHEN.NOW && (
        <RunDrawerScheduleSection
          embedded
          form={form}
          onChange={onFormChange}
          onPreviewError={onPreviewError}
          sdkEndpoint={sdkEndpoint}
          testSetCount={testSetCount}
          initialForm={initialForm}
        />
      )}
    </>
  );
}
