'use client';

import React, { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Link,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import BaseDrawer from '@/components/common/BaseDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { usePlatformKey } from '@/hooks/usePlatformKey';
import { PlatformKeyError } from '@/utils/api-client/platform-client';
import type { PlatformKeyStatus } from '@/utils/api-client/interfaces/platform';
import { useNotifications } from '@/components/common/NotificationContext';

interface PlatformKeyDrawerProps {
  open: boolean;
  onClose: () => void;
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
      <StatusChip label="Valid" color="success" icon={<CheckCircleIcon />} />
    );
  }
  if (status.valid === false) {
    return <StatusChip label="Invalid" color="error" icon={<ErrorIcon />} />;
  }
  return (
    <StatusChip
      label="Not checked"
      color="default"
      icon={<HelpOutlineIcon />}
    />
  );
}

function PolyphemusChip({ status }: { status: PlatformKeyStatus }) {
  if (status.polyphemus_authorized === true) {
    return (
      <StatusChip
        label="Authorized"
        color="success"
        icon={<CheckCircleIcon />}
      />
    );
  }
  if (status.polyphemus_authorized === false) {
    return (
      <StatusChip label="Not authorized" color="warning" icon={<ErrorIcon />} />
    );
  }
  return (
    <StatusChip label="Unknown" color="default" icon={<HelpOutlineIcon />} />
  );
}

/** Label + chips on one grid row; the shared grid keeps every chip column aligned. */
function StatusRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        {label}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 0.75,
        }}
      >
        {children}
      </Box>
    </>
  );
}

export function PlatformKeyDrawer({
  open,
  onClose,
  onChange,
}: PlatformKeyDrawerProps) {
  const { show } = useNotifications();
  const { query, setKey, clearKey } = usePlatformKey();
  const [keyInput, setKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [removeConfirmOpen, setRemoveConfirmOpen] = useState(false);

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
      onClose();
      onChange?.();
    } catch (error) {
      show(error instanceof Error ? error.message : 'Failed to save the key.', {
        severity: 'error',
      });
    }
  };

  const handleRemove = async () => {
    try {
      await clearKey.mutateAsync();
      show('Rhesis platform API key removed.', { severity: 'success' });
      setRemoveConfirmOpen(false);
      onClose();
      onChange?.();
    } catch (error) {
      show(
        error instanceof Error ? error.message : 'Failed to remove the key.',
        { severity: 'error' }
      );
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
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'max-content 1fr',
        alignItems: 'center',
        columnGap: 2,
        rowGap: 1,
      }}
    >
      <StatusRow label="API Key">
        <ValidityChip status={status} />
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {status.masked_key ?? 'Configured'}
        </Typography>
      </StatusRow>
      <StatusRow label="Polyphemus">
        <PolyphemusChip status={status} />
      </StatusRow>
      {status.last_checked_at && (
        <StatusRow label="Last checked">
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {new Date(status.last_checked_at).toLocaleString()}
          </Typography>
        </StatusRow>
      )}
    </Box>
  ) : (
    <StatusChip
      label="No key configured"
      color="warning"
      icon={<ErrorIcon />}
    />
  );

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Rhesis Platform API Key"
      titleIcon={<VpnKeyIcon />}
      closeButtonText=""
    >
      <Box sx={drawerSectionSx}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <FormSectionDivider
              headline="Current API Key"
              descriptiveText="Rhesis-hosted models (Rhesis Default, Rhesis Default Embedding, and Rhesis Polyphemus) require a platform API key on self-hosted deployments."
            />
          </Box>
          {configured && (
            <Tooltip title="Remove key">
              <span>
                <IconButton
                  size="small"
                  color="error"
                  onClick={() => setRemoveConfirmOpen(true)}
                  disabled={mutating}
                  aria-label="Remove API key"
                  sx={{ flexShrink: 0 }}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>

        {statusContent}
      </Box>

      <Box sx={drawerSectionSx}>
        <FormSectionDivider
          headline={configured ? 'Replace API Key' : 'API Key'}
          descriptiveText={
            <>
              {configured
                ? 'Paste a new key to replace the current one. '
                : 'Paste your key to enable Rhesis-hosted models. '}
              Generate one from the{' '}
              <Link
                href="https://app.rhesis.ai/tokens"
                target="_blank"
                rel="noopener noreferrer"
              >
                Rhesis API Tokens page
              </Link>
              .
            </>
          }
        />

        <Box sx={drawerFieldsSx}>
          <TextField
            label={configured ? 'New key' : 'API key'}
            fullWidth
            type={showKey ? 'text' : 'password'}
            value={keyInput}
            onChange={e => setKeyInput(e.target.value)}
            placeholder={
              configured ? 'New key' : 'Enter your Rhesis platform API key'
            }
            disabled={mutating}
            sx={drawerOutlinedFieldSx}
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

          <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'flex-end' }}>
            {keyInput && (
              <Button
                variant="text"
                onClick={() => {
                  setKeyInput('');
                  setShowKey(false);
                }}
                disabled={mutating}
              >
                Clear
              </Button>
            )}
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={!keyInput.trim() || mutating}
              startIcon={
                setKey.isPending ? <CircularProgress size={16} /> : undefined
              }
            >
              Save
            </Button>
          </Box>
        </Box>
      </Box>

      <DeleteModal
        open={removeConfirmOpen}
        onClose={() => setRemoveConfirmOpen(false)}
        onConfirm={handleRemove}
        isLoading={clearKey.isPending}
        title="Remove API Key"
        message="Remove the stored Rhesis platform API key? Rhesis-hosted models will stop working until a new key is saved."
        confirmButtonText={clearKey.isPending ? 'Removing...' : 'Remove'}
      />
    </BaseDrawer>
  );
}
