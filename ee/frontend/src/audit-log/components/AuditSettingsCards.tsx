'use client';

import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import CircularProgress from '@mui/material/CircularProgress';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { alpha, type Theme } from '@mui/material/styles';
import { useCan } from '@/components/common/Can';
import { SectionCard } from '@/components/common/SectionCard';
import { Capability } from '@/constants/capabilities';
import { BORDER_RADIUS } from '@/styles/theme-constants';
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
import { listRowSx, listSx } from './AuditApiAccessCard';

const CUSTOM = 'custom';

/** Why someone would pick each preset. */
const PRESET_HINTS: Record<number, string> = {
  90: 'The shortest allowed',
  365: 'Recommended',
  1095: 'For regulated industries',
};

/** The settings, or a spinner or error in place of the card's body. */
function WithSettings({
  children,
}: {
  children: (settings: AuditLogSettings, canManage: boolean) => React.ReactNode;
}) {
  const canManage = useCan(Capability.AuditLog.MANAGE);
  const { data: settings, isLoading, error } = useAuditLogSettings();
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
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
  return <>{children(settings, canManage)}</>;
}

function optionSx(selected: boolean, disabled: boolean) {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    px: 1.5,
    py: 0.5,
    border: '1px solid',
    borderColor: (t: Theme) =>
      selected ? t.palette.primary.main : t.palette.greyscale.border,
    borderRadius: BORDER_RADIUS.sm,
    bgcolor: (t: Theme) =>
      selected ? alpha(t.palette.primary.main, 0.06) : 'transparent',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.6 : 1,
  };
}

function RetentionOption({
  value,
  label,
  hint,
  selected,
  disabled,
}: {
  value: string;
  label: string;
  hint: string;
  selected: boolean;
  disabled: boolean;
}) {
  return (
    <Box component="label" sx={optionSx(selected, disabled)}>
      <Radio
        value={value}
        disabled={disabled}
        slotProps={{ input: { 'aria-label': label } }}
      />
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <Typography variant="subtitle2">{label}</Typography>
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      </Box>
    </Box>
  );
}

function RetentionForm({
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
  const planMax = settings.max_retention_days;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <RadioGroup
        aria-label="Retention period"
        value={choice}
        onChange={e => {
          setChoice(e.target.value);
          update.reset();
        }}
        sx={{ gap: 1 }}
      >
        {RETENTION_PRESETS.map(preset => {
          const abovePlan = preset.days > planMax;
          return (
            <RetentionOption
              key={preset.days}
              value={String(preset.days)}
              label={preset.label}
              hint={abovePlan ? 'Above your plan' : PRESET_HINTS[preset.days]}
              selected={choice === String(preset.days)}
              disabled={!canManage || abovePlan}
            />
          );
        })}
        <RetentionOption
          value={CUSTOM}
          label="Custom"
          hint={`Up to ${retentionLabel(planMax)} on your plan`}
          selected={choice === CUSTOM}
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

      <Alert severity={settings.below_eu_ai_act_minimum ? 'warning' : 'info'}>
        {settings.below_eu_ai_act_minimum
          ? `${retentionLabel(saved)} is shorter than the six months the EU AI Act asks providers of high-risk AI systems to keep logs. You can still use it.`
          : 'For high-risk AI systems under the EU AI Act, keep logs for at least six months. Check your obligations with your compliance team.'}
      </Alert>

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
  );
}

export function AuditRetentionCard() {
  return (
    <SectionCard
      title="Retention"
      subtitle="A daily job deletes events older than this. Stream them to your SIEM to keep them longer."
    >
      <WithSettings>
        {(settings, canManage) => (
          <RetentionForm settings={settings} canManage={canManage} />
        )}
      </WithSettings>
    </SectionCard>
  );
}

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
    <Box sx={listRowSx}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="subtitle2">{label}</Typography>
        <Typography variant="caption" color="text.secondary">
          {description}
        </Typography>
      </Box>
      <Checkbox
        checked={checked}
        disabled={disabled}
        onChange={e => onChange?.(e.target.checked)}
        slotProps={{ input: { 'aria-label': label } }}
      />
    </Box>
  );
}

function PrivacyForm({
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
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={listSx}>
        <ToggleRow
          label="Mask IP addresses"
          description="Keep only the network part (/24 for IPv4, /48 for IPv6). Turning this off records full addresses on new events only; events already recorded stay masked."
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
      </Box>
      {update.error && (
        <Alert severity="error">
          {getApiErrorMessage(update.error, 'Could not save the setting.')}
        </Alert>
      )}
    </Box>
  );
}

export function AuditPrivacyCard() {
  return (
    <SectionCard
      title="Privacy"
      subtitle="Entries are append-only and cannot be edited or deleted. These settings apply when an event is recorded, so a change affects new events only."
    >
      <WithSettings>
        {(settings, canManage) => (
          <PrivacyForm settings={settings} canManage={canManage} />
        )}
      </WithSettings>
    </SectionCard>
  );
}

/** Warnings that apply to the whole tab: paused jobs, and read-only access. */
export function AuditSettingsNotices() {
  const canManage = useCan(Capability.AuditLog.MANAGE);
  const { data: settings } = useAuditLogSettings();
  return (
    <>
      {settings?.scheduled_jobs_running === false && (
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
    </>
  );
}
