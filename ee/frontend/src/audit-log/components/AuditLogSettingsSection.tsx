'use client';

import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useCan } from '@/components/common/Can';
import { SectionCard } from '@/components/common/SectionCard';
import { Capability } from '@/constants/capabilities';
import { getApiErrorMessage } from '@/utils/error-utils';
import {
  useAuditLogSettings,
  useUpdateAuditLogSettings,
} from '../hooks/useAuditLogSettings';
import {
  MAX_RETENTION_DAYS,
  MIN_RETENTION_DAYS,
  RETENTION_PRESETS,
  isPresetRetention,
  parseRetentionDays,
  retentionLabel,
} from '../retention';
import type { AuditLogSettings, AuditLogSettingsUpdate } from '../types';

const CUSTOM = 'custom';

function ToggleRow({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled: boolean;
  onChange?: (checked: boolean) => void;
}) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
      <Box sx={{ flex: 1 }}>
        <Typography variant="subtitle2">{label}</Typography>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </Box>
      <Switch
        checked={checked}
        disabled={disabled}
        onChange={e => onChange?.(e.target.checked)}
        slotProps={{ input: { 'aria-label': label } }}
      />
    </Box>
  );
}

function RetentionCard({
  settings,
  canManage,
}: {
  settings: AuditLogSettings;
  canManage: boolean;
}) {
  const saved = settings.retention_days;
  const [choice, setChoice] = React.useState(
    isPresetRetention(saved) ? String(saved) : CUSTOM
  );
  const [customDays, setCustomDays] = React.useState(String(saved));
  const update = useUpdateAuditLogSettings();

  // A save, or a lower plan cap clamping the choice, moves the saved value.
  React.useEffect(() => {
    setChoice(isPresetRetention(saved) ? String(saved) : CUSTOM);
    setCustomDays(String(saved));
  }, [saved]);

  const days =
    choice === CUSTOM ? parseRetentionDays(customDays) : Number(choice);
  const customInvalid = choice === CUSTOM && days === null;

  return (
    <SectionCard
      title="Retention"
      subtitle="How long events are kept. A daily job deletes events older than this."
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <RadioGroup
          row
          aria-label="Retention period"
          value={choice}
          onChange={e => {
            setChoice(e.target.value);
            update.reset();
          }}
        >
          {RETENTION_PRESETS.map(preset => (
            <FormControlLabel
              key={preset.days}
              value={String(preset.days)}
              control={<Radio />}
              label={preset.label}
              disabled={!canManage}
            />
          ))}
          <FormControlLabel
            value={CUSTOM}
            control={<Radio />}
            label="Custom"
            disabled={!canManage}
          />
        </RadioGroup>

        {choice === CUSTOM && (
          <TextField
            label="Days"
            type="number"
            size="small"
            value={customDays}
            onChange={e => {
              setCustomDays(e.target.value);
              update.reset();
            }}
            disabled={!canManage}
            error={customInvalid}
            helperText={`${MIN_RETENTION_DAYS} to ${MAX_RETENTION_DAYS} days`}
            slotProps={{
              htmlInput: { min: MIN_RETENTION_DAYS, max: MAX_RETENTION_DAYS },
            }}
            sx={{ maxWidth: theme => theme.spacing(25) }}
          />
        )}

        <Typography variant="body2" color="text.secondary">
          Your plan keeps events for up to{' '}
          {retentionLabel(settings.max_retention_days)}.
        </Typography>

        {settings.below_eu_ai_act_minimum && (
          <Alert severity="warning">
            {retentionLabel(saved)} is shorter than the six months the EU AI Act
            asks providers of high-risk AI systems to keep logs. You can still
            use it.
          </Alert>
        )}

        {update.error && (
          <Alert severity="error">
            {getApiErrorMessage(update.error, 'Could not save the retention.')}
          </Alert>
        )}

        {canManage && (
          <Box>
            <Button
              variant="contained"
              disabled={days === null || days === saved || update.isPending}
              onClick={() => {
                if (days !== null) update.mutate({ retention_days: days });
              }}
            >
              {update.isPending ? 'Saving…' : 'Save retention'}
            </Button>
          </Box>
        )}
      </Box>
    </SectionCard>
  );
}

function PrivacyCard({
  settings,
  canManage,
}: {
  settings: AuditLogSettings;
  canManage: boolean;
}) {
  const update = useUpdateAuditLogSettings();
  const save = (change: AuditLogSettingsUpdate) => update.mutate(change);
  const disabled = !canManage || update.isPending;

  return (
    <SectionCard
      title="Privacy"
      subtitle="Both settings apply when an event is recorded, so a change affects new events only."
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
        <ToggleRow
          label="Mask IP addresses"
          description="Keep only the network part of each address (/24 for IPv4, /48 for IPv6). Turning this off records full addresses on new events only; events already recorded stay masked."
          checked={settings.mask_ip}
          disabled={disabled}
          onChange={checked => save({ mask_ip: checked })}
        />
        <ToggleRow
          label="Include content"
          description="Keep the values of content fields, such as prompts and test inputs, encrypted with each change. Only the event detail shows them, and only while this is on."
          checked={settings.include_content}
          disabled={disabled}
          onChange={checked => save({ include_content: checked })}
        />
        <ToggleRow
          label="Redact secrets"
          description="Always on. API keys, passwords and other secrets are never recorded, only that they changed."
          checked
          disabled
        />
        {update.error && (
          <Alert severity="error">
            {getApiErrorMessage(update.error, 'Could not save the setting.')}
          </Alert>
        )}
      </Box>
    </SectionCard>
  );
}

/** Retention and privacy. Anyone who can read the log sees them; `audit_log:manage` changes them. */
export default function AuditLogSettingsSection() {
  const canManage = useCan(Capability.AuditLog.MANAGE);
  const { data: settings, isLoading, error } = useAuditLogSettings();

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error || !settings) {
    return (
      <Alert severity="error">
        {getApiErrorMessage(error, 'Could not load the audit log settings.')}
      </Alert>
    );
  }

  return (
    <Box>
      {settings.scheduled_jobs_running === false && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Scheduled jobs are not running, so retention and streaming are paused:
          old events are not deleted and nothing is sent to streaming
          destinations until they run again.
        </Alert>
      )}
      {!canManage && (
        <Alert severity="info" sx={{ mb: 3 }}>
          You can view these settings. Only roles that can manage the audit log
          can change them.
        </Alert>
      )}
      <RetentionCard settings={settings} canManage={canManage} />
      <PrivacyCard settings={settings} canManage={canManage} />
    </Box>
  );
}
