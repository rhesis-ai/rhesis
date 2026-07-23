'use client';

import React, { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Collapse,
  Divider,
  IconButton,
  InputAdornment,
  Stack,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';
import { PageLayout } from '@/components/layout/PageLayout';
import { SectionCard } from '@/components/common/SectionCard';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import {
  AccountTreeIcon,
  ArrowBackIcon,
  ArrowForwardIcon,
  BlockIcon,
  BoltIcon,
  CheckCircleIcon,
  CloudIcon,
  CloudSyncIcon,
  EndpointsIcon,
  GradingIcon,
  MenuBookIcon,
  ScheduleIcon,
  SmartToyIcon,
  StorageIcon,
  SwapHorizIcon,
  VisibilityIcon,
  VisibilityOffIcon,
} from '@/components/icons';

/* -------------------------------------------------------------------------- */
/*  Sync direction model                                                       */
/*                                                                             */
/*  Orientation: this local deployment sits on the LEFT, the Rhesis platform   */
/*  sits on the RIGHT. Each category picks how its data flows between them.    */
/* -------------------------------------------------------------------------- */

type SyncDirection = 'pull' | 'both' | 'push' | 'off';

interface DirectionOption {
  value: SyncDirection;
  label: string;
  /** Full sentence shown in the tooltip so the meaning is unambiguous. */
  hint: string;
  icon: React.ReactNode;
  /** Accent colour for the selected state. */
  color: (theme: Theme) => string;
}

const DIRECTION_OPTIONS: DirectionOption[] = [
  {
    value: 'pull',
    label: 'Pull',
    hint: 'To the left — bring changes down from the platform into this deployment',
    icon: <ArrowBackIcon fontSize="small" />,
    color: theme => theme.palette.primary.main,
  },
  {
    value: 'both',
    label: 'Both ways',
    hint: 'Both ways — keep this deployment and the platform in sync in both directions',
    icon: <SwapHorizIcon fontSize="small" />,
    color: theme => theme.palette.success.main,
  },
  {
    value: 'push',
    label: 'Push',
    hint: 'To the right — send changes from this deployment up to the platform',
    icon: <ArrowForwardIcon fontSize="small" />,
    color: theme => theme.palette.secondary.main,
  },
  {
    value: 'off',
    label: 'Off',
    hint: "Not at all — don't sync this category",
    icon: <BlockIcon fontSize="small" />,
    color: theme => theme.palette.text.disabled,
  },
];

interface SyncCategory {
  key: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  default: SyncDirection;
}

const SYNC_CATEGORIES: SyncCategory[] = [
  {
    key: 'models',
    label: 'Models',
    description: 'Provider connections and model configurations',
    icon: <SmartToyIcon />,
    default: 'pull',
  },
  {
    key: 'endpoints',
    label: 'Endpoints',
    description: 'Endpoints under test and their connection settings',
    icon: <EndpointsIcon />,
    default: 'pull',
  },
  {
    key: 'test-sets',
    label: 'Test Sets',
    description: 'Test sets and the tests they contain',
    icon: <MenuBookIcon />,
    default: 'both',
  },
  {
    key: 'evaluation',
    label: 'Metrics & Behaviors',
    description: 'Evaluation metrics and the behaviors they measure',
    icon: <GradingIcon />,
    default: 'both',
  },
  {
    key: 'projects',
    label: 'Projects',
    description: 'Projects, tags and workspace structure',
    icon: <AccountTreeIcon />,
    default: 'off',
  },
];

/* -------------------------------------------------------------------------- */
/*  Direction selector — four options, all visible at once (no dropdown)       */
/* -------------------------------------------------------------------------- */

function SyncDirectionSelector({
  value,
  onChange,
  disabled,
}: {
  value: SyncDirection;
  onChange: (value: SyncDirection) => void;
  disabled?: boolean;
}) {
  return (
    <ToggleButtonGroup
      exclusive
      value={value}
      disabled={disabled}
      onChange={(_event, next: SyncDirection | null) => {
        if (next) onChange(next);
      }}
      sx={{
        gap: 0.5,
        '& .MuiToggleButtonGroup-grouped': {
          border: theme => `1px solid ${theme.palette.greyscale.border}`,
          borderRadius: '10px !important',
          px: 1.5,
          py: 0.75,
          textTransform: 'none',
          color: 'text.secondary',
          flexDirection: 'column',
          gap: 0.25,
          minWidth: 74,
        },
      }}
    >
      {DIRECTION_OPTIONS.map(option => (
        <ToggleButton
          key={option.value}
          value={option.value}
          aria-label={option.label}
          sx={{
            '&.Mui-selected': {
              color: option.color,
              bgcolor: theme => alpha(option.color(theme), 0.12),
              borderColor: theme => alpha(option.color(theme), 0.5),
              '&:hover': {
                bgcolor: theme => alpha(option.color(theme), 0.18),
              },
            },
          }}
        >
          <Tooltip title={option.hint} arrow placement="top">
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 0.25,
              }}
            >
              {option.icon}
              <Typography variant="caption" sx={{ fontWeight: 600 }}>
                {option.label}
              </Typography>
            </Box>
          </Tooltip>
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

/* -------------------------------------------------------------------------- */
/*  Orientation legend — makes "left" and "right" concrete                     */
/* -------------------------------------------------------------------------- */

function OrientationLegend() {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        flexWrap: 'wrap',
        p: 2,
        mb: 3,
        borderRadius: '10px',
        border: theme => `1px dashed ${theme.palette.greyscale.border}`,
        bgcolor: theme => alpha(theme.palette.primary.main, 0.03),
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center">
        <StorageIcon fontSize="small" sx={{ color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          This deployment
        </Typography>
      </Stack>
      <Stack direction="row" spacing={1.5} alignItems="center">
        <Tooltip title="Pull — platform to here" arrow>
          <ArrowBackIcon fontSize="small" sx={{ color: 'primary.main' }} />
        </Tooltip>
        <Tooltip title="Both ways" arrow>
          <SwapHorizIcon fontSize="small" sx={{ color: 'success.main' }} />
        </Tooltip>
        <Tooltip title="Push — here to platform" arrow>
          <ArrowForwardIcon fontSize="small" sx={{ color: 'secondary.main' }} />
        </Tooltip>
      </Stack>
      <Stack direction="row" spacing={1} alignItems="center">
        <CloudIcon fontSize="small" sx={{ color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Rhesis platform
        </Typography>
      </Stack>
    </Box>
  );
}

/* -------------------------------------------------------------------------- */
/*  Schedule model — run once on demand, or automatically on an interval       */
/* -------------------------------------------------------------------------- */

type ScheduleMode = 'manual' | 'scheduled';

interface ScheduleModeOption {
  value: ScheduleMode;
  label: string;
  caption: string;
  icon: React.ReactNode;
}

const SCHEDULE_MODES: ScheduleModeOption[] = [
  {
    value: 'manual',
    label: 'One-time',
    caption: 'Runs only when you click Sync now',
    icon: <BoltIcon />,
  },
  {
    value: 'scheduled',
    label: 'Scheduled',
    caption: 'Runs automatically on a set interval',
    icon: <ScheduleIcon />,
  },
];

const INTERVAL_PRESETS: { minutes: number; label: string }[] = [
  { minutes: 15, label: '15 min' },
  { minutes: 30, label: '30 min' },
  { minutes: 60, label: '1 hour' },
  { minutes: 360, label: '6 hours' },
  { minutes: 1440, label: '24 hours' },
];

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${minutes} minutes`;
  const hours = minutes / 60;
  if (hours < 24) return hours === 1 ? '1 hour' : `${hours} hours`;
  const days = hours / 24;
  return days === 1 ? '1 day' : `${days} days`;
}

function ScheduleModeSelector({
  value,
  onChange,
}: {
  value: ScheduleMode;
  onChange: (value: ScheduleMode) => void;
}) {
  return (
    <ToggleButtonGroup
      exclusive
      fullWidth
      value={value}
      onChange={(_event, next: ScheduleMode | null) => {
        if (next) onChange(next);
      }}
      sx={{
        gap: 1.5,
        '& .MuiToggleButtonGroup-grouped': {
          border: theme => `1px solid ${theme.palette.greyscale.border}`,
          borderRadius: '10px !important',
          p: 2,
          gap: 1.5,
          justifyContent: 'flex-start',
          textTransform: 'none',
          color: 'text.secondary',
          '&.Mui-selected': {
            color: 'primary.main',
            bgcolor: theme => alpha(theme.palette.primary.main, 0.1),
            borderColor: theme => alpha(theme.palette.primary.main, 0.5),
            '&:hover': {
              bgcolor: theme => alpha(theme.palette.primary.main, 0.16),
            },
          },
        },
      }}
    >
      {SCHEDULE_MODES.map(mode => (
        <ToggleButton
          key={mode.value}
          value={mode.value}
          aria-label={mode.label}
        >
          {mode.icon}
          <Box sx={{ textAlign: 'left' }}>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {mode.label}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {mode.caption}
            </Typography>
          </Box>
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

/* -------------------------------------------------------------------------- */
/*  Page                                                                       */
/* -------------------------------------------------------------------------- */

export default function PlatformSyncPage() {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Model.CREATE
  );

  const [enabled, setEnabled] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState('https://api.rhesis.ai');
  const [directions, setDirections] = useState<Record<string, SyncDirection>>(
    () =>
      Object.fromEntries(
        SYNC_CATEGORIES.map(c => [c.key, c.default])
      ) as Record<string, SyncDirection>
  );

  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>('scheduled');
  const [intervalMinutes, setIntervalMinutes] = useState(60);

  const activeCount = Object.values(directions).filter(d => d !== 'off').length;

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="platform sync" />;

  return (
    <PageLayout
      title="Platform Sync"
      description="Keep this deployment aligned with the Rhesis platform. Turn sync on, connect with an API key, then choose which direction each category flows."
    >
      <Box sx={{ width: '100%' }}>
        {/* Master toggle ---------------------------------------------------- */}
        <SectionCard>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 2,
            }}
          >
            <Stack direction="row" spacing={2} alignItems="center">
              <Box
                sx={{
                  width: 48,
                  height: 48,
                  borderRadius: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: enabled ? 'primary.main' : 'text.disabled',
                  bgcolor: theme =>
                    alpha(
                      enabled
                        ? theme.palette.primary.main
                        : theme.palette.text.disabled,
                      0.1
                    ),
                }}
              >
                <CloudSyncIcon />
              </Box>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Platform Sync
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  {enabled
                    ? `On — ${activeCount} of ${SYNC_CATEGORIES.length} categories, ${
                        scheduleMode === 'scheduled'
                          ? `every ${formatInterval(intervalMinutes)}`
                          : 'manual sync'
                      }`
                    : 'Off — this deployment runs standalone'}
                </Typography>
              </Box>
            </Stack>
            <Switch
              checked={enabled}
              onChange={e => setEnabled(e.target.checked)}
              inputProps={{ 'aria-label': 'Enable platform sync' }}
            />
          </Box>
        </SectionCard>

        <Collapse in={enabled} unmountOnExit>
          {/* Connection --------------------------------------------------- */}
          <SectionCard
            title="Connection"
            subtitle="How this deployment reaches the Rhesis platform."
          >
            <Stack spacing={3}>
              <TextField
                label="API key"
                placeholder="rh-..."
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                fullWidth
                autoComplete="off"
                helperText="Create one under API in the platform sidebar."
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        edge="end"
                        aria-label={showKey ? 'Hide API key' : 'Show API key'}
                        onClick={() => setShowKey(v => !v)}
                      >
                        {showKey ? (
                          <VisibilityOffIcon fontSize="small" />
                        ) : (
                          <VisibilityIcon fontSize="small" />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <TextField
                label="Platform URL"
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
                fullWidth
              />
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Button variant="outlined" size="small">
                  Test connection
                </Button>
                <Chip
                  size="small"
                  variant="outlined"
                  color="success"
                  icon={<CheckCircleIcon fontSize="small" />}
                  label="Connected"
                />
              </Stack>
            </Stack>
          </SectionCard>

          {/* Sync settings ------------------------------------------------ */}
          <SectionCard
            title="Sync settings"
            subtitle="Pick a direction for each category. Choose one of the four — all shown at once."
          >
            <OrientationLegend />

            <Stack divider={<Divider flexItem />} spacing={0}>
              {SYNC_CATEGORIES.map(category => (
                <Box
                  key={category.key}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 2,
                    py: 2,
                    flexWrap: 'wrap',
                  }}
                >
                  <Stack
                    direction="row"
                    spacing={2}
                    alignItems="center"
                    sx={{ minWidth: 0, flex: '1 1 240px' }}
                  >
                    <Box
                      sx={{
                        color:
                          directions[category.key] === 'off'
                            ? 'text.disabled'
                            : 'primary.main',
                        display: 'flex',
                      }}
                    >
                      {category.icon}
                    </Box>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {category.label}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ color: 'text.secondary' }}
                      >
                        {category.description}
                      </Typography>
                    </Box>
                  </Stack>
                  <SyncDirectionSelector
                    value={directions[category.key]}
                    onChange={next =>
                      setDirections(prev => ({
                        ...prev,
                        [category.key]: next,
                      }))
                    }
                  />
                </Box>
              ))}
            </Stack>
          </SectionCard>

          {/* Schedule ----------------------------------------------------- */}
          <SectionCard
            title="Schedule"
            subtitle="Sync once on demand, or keep this deployment in sync automatically."
          >
            <ScheduleModeSelector
              value={scheduleMode}
              onChange={setScheduleMode}
            />

            <Collapse in={scheduleMode === 'scheduled'} unmountOnExit>
              <Box sx={{ mt: 3 }}>
                <Typography
                  variant="subtitle2"
                  sx={{ fontWeight: 600, mb: 1.5 }}
                >
                  Run every
                </Typography>
                <ToggleButtonGroup
                  exclusive
                  value={intervalMinutes}
                  onChange={(_event, next: number | null) => {
                    if (next) setIntervalMinutes(next);
                  }}
                  sx={{
                    flexWrap: 'wrap',
                    gap: 0.75,
                    '& .MuiToggleButtonGroup-grouped': {
                      border: theme =>
                        `1px solid ${theme.palette.greyscale.border}`,
                      borderRadius: '999px !important',
                      px: 2,
                      py: 0.5,
                      textTransform: 'none',
                      color: 'text.secondary',
                      '&.Mui-selected': {
                        color: 'primary.main',
                        bgcolor: theme =>
                          alpha(theme.palette.primary.main, 0.1),
                        borderColor: theme =>
                          alpha(theme.palette.primary.main, 0.5),
                        '&:hover': {
                          bgcolor: theme =>
                            alpha(theme.palette.primary.main, 0.16),
                        },
                      },
                    },
                  }}
                >
                  {INTERVAL_PRESETS.map(preset => (
                    <ToggleButton key={preset.minutes} value={preset.minutes}>
                      {preset.label}
                    </ToggleButton>
                  ))}
                </ToggleButtonGroup>
                <Typography
                  variant="body2"
                  sx={{ mt: 2, color: 'text.secondary' }}
                >
                  Syncs automatically every {formatInterval(intervalMinutes)}.
                  Only categories that aren&apos;t set to Off are included.
                </Typography>
              </Box>
            </Collapse>
          </SectionCard>

          {/* Footer actions ----------------------------------------------- */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Last synced 2 hours ago
              {scheduleMode === 'scheduled' &&
                ` · Next run in ~${formatInterval(intervalMinutes)}`}
            </Typography>
            <Button
              variant="contained"
              startIcon={<CloudSyncIcon />}
              disabled={activeCount === 0}
            >
              Sync now
            </Button>
          </Box>
        </Collapse>
      </Box>
    </PageLayout>
  );
}
