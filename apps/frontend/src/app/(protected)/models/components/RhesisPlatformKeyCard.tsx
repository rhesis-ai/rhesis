'use client';

import React, { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { usePlatformKey } from '@/hooks/usePlatformKey';
import { PlatformKeyError } from '@/utils/api-client/platform-client';
import type { PlatformKeyStatus } from '@/utils/api-client/interfaces/platform';
import { useNotifications } from '@/components/common/NotificationContext';

interface RhesisPlatformKeyCardProps {
  /** Called after a successful set/clear so the caller can refresh model availability. */
  onChange?: () => void;
}

type ChipColor = 'success' | 'error' | 'warning' | 'default';

function StatusChip({
  label,
  color,
  icon,
}: {
  label: string;
  color: ChipColor;
  icon: React.ReactElement;
}) {
  return (
    <Chip
      size="small"
      variant="outlined"
      color={color}
      icon={icon}
      label={label}
    />
  );
}

function ValidityChip({ status }: { status: PlatformKeyStatus }) {
  if (status.valid === true) {
    return (
      <StatusChip label="Key valid" color="success" icon={<CheckCircleIcon />} />
    );
  }
  if (status.valid === false) {
    return <StatusChip label="Key invalid" color="error" icon={<ErrorIcon />} />;
  }
  return (
    <StatusChip label="Not checked" color="default" icon={<HelpOutlineIcon />} />
  );
}

function PolyphemusChip({ status }: { status: PlatformKeyStatus }) {
  if (status.polyphemus_authorized === true) {
    return (
      <StatusChip
        label="Polyphemus authorized"
        color="success"
        icon={<CheckCircleIcon />}
      />
    );
  }
  if (status.polyphemus_authorized === false) {
    return (
      <StatusChip
        label="Polyphemus not authorized"
        color="warning"
        icon={<ErrorIcon />}
      />
    );
  }
  return (
    <StatusChip
      label="Polyphemus unknown"
      color="default"
      icon={<HelpOutlineIcon />}
    />
  );
}

/**
 * Local-only settings card for the deployment-wide Rhesis platform API key.
 * Mount this ONLY in local mode (see the caller's `isLocalMode` gate) — the
 * backend endpoints 404 elsewhere.
 */
export function RhesisPlatformKeyCard({ onChange }: RhesisPlatformKeyCardProps) {
  const { show } = useNotifications();
  const { query, setKey, clearKey } = usePlatformKey();
  const [keyInput, setKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Endpoint absent (non-local backend): hide the card entirely.
  if (query.error instanceof PlatformKeyError && query.error.status === 404) {
    return null;
  }

  const status = query.data;
  const configured = status?.configured ?? false;
  const mutating = setKey.isPending || clearKey.isPending;

  const handleSave = async () => {
    const trimmed = keyInput.trim();
    if (!trimmed) return;
    try {
      await setKey.mutateAsync(trimmed);
      setKeyInput('');
      setShowKey(false);
      show('Rhesis platform API key saved.', { severity: 'success' });
      onChange?.();
    } catch (error) {
      show(error instanceof Error ? error.message : 'Failed to save the key.', {
        severity: 'error',
      });
    }
  };

  const handleClear = async () => {
    try {
      await clearKey.mutateAsync();
      show('Rhesis platform API key cleared.', { severity: 'success' });
      onChange?.();
    } catch (error) {
      show(error instanceof Error ? error.message : 'Failed to clear the key.', {
        severity: 'error',
      });
    }
  };

  const statusContent = query.isLoading ? (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <CircularProgress size={16} />
      <Typography variant="caption" color="text.secondary">
        Checking key status…
      </Typography>
    </Box>
  ) : configured && status ? (
    <>
      <StatusChip
        label={
          status.masked_key ? `Configured (${status.masked_key})` : 'Configured'
        }
        color="default"
        icon={<VpnKeyIcon />}
      />
      <ValidityChip status={status} />
      <PolyphemusChip status={status} />
    </>
  ) : (
    <StatusChip
      label="No key configured"
      color="warning"
      icon={<ErrorIcon />}
    />
  );

  const toggle = () => setExpanded(prev => !prev);

  return (
    <Paper
      variant="outlined"
      sx={{ p: 2, mb: 3, display: 'flex', flexDirection: 'column' }}
    >
      {/* Header stays visible at all times; the key status lives here. */}
      <Box
        onClick={toggle}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <VpnKeyIcon fontSize="small" color="action" />
        <Typography variant="subtitle1" sx={{ fontWeight: 600, flexShrink: 0 }}>
          Rhesis Platform API Key
        </Typography>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 0.75,
            ml: 1,
            flexGrow: 1,
          }}
        >
          {statusContent}
        </Box>
        <IconButton
          size="small"
          aria-label={expanded ? 'Collapse' : 'Expand'}
          aria-expanded={expanded}
          onClick={e => {
            e.stopPropagation();
            toggle();
          }}
          sx={{ flexShrink: 0 }}
        >
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Rhesis-hosted models (Rhesis Default, Rhesis Default Embedding, and
            Rhesis Polyphemus) require a Rhesis platform API key on a
            self-hosted deployment. Set it here to enable those models.
          </Typography>

          {configured && status?.last_checked_at && (
            <Typography variant="caption" color="text.secondary">
              Last checked: {new Date(status.last_checked_at).toLocaleString()}
            </Typography>
          )}

          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
            <TextField
              label={configured ? 'Replace API key' : 'API key'}
              fullWidth
              size="small"
              type={showKey ? 'text' : 'password'}
              value={keyInput}
              onChange={e => setKeyInput(e.target.value)}
              placeholder="Enter your Rhesis platform API key"
              disabled={mutating}
              InputProps={{
                endAdornment: keyInput ? (
                  <IconButton
                    size="small"
                    edge="end"
                    onClick={() => setShowKey(prev => !prev)}
                    aria-label={showKey ? 'Hide API key' : 'Show API key'}
                  >
                    {showKey ? (
                      <VisibilityOffIcon fontSize="small" />
                    ) : (
                      <VisibilityIcon fontSize="small" />
                    )}
                  </IconButton>
                ) : null,
              }}
            />
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={!keyInput.trim() || mutating}
              startIcon={
                setKey.isPending ? <CircularProgress size={16} /> : undefined
              }
              sx={{ height: 40, flexShrink: 0 }}
            >
              Save
            </Button>
            {configured && (
              <Button
                variant="outlined"
                color="error"
                onClick={handleClear}
                disabled={mutating}
                startIcon={
                  clearKey.isPending ? <CircularProgress size={16} /> : undefined
                }
                sx={{ height: 40, flexShrink: 0 }}
              >
                Clear
              </Button>
            )}
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
}
