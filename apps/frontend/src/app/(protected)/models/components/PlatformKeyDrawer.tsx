'use client';

import React, { useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Link,
  TextField,
  Typography,
} from '@mui/material';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
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
  // An env-var key cannot be removed from here, so it keeps the input (saving
  // an org key overrides it). Only a stored org key uses the remove-first flow.
  const fromEnv = status?.source === 'environment';
  const removable = configured && !fromEnv;

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

  const intro =
    'Rhesis-hosted models (Rhesis, Rhesis Embedding, and Rhesis Polyphemus) require a platform API key on self-hosted deployments.';

  const loadingSection = (
    <Box sx={drawerSectionSx}>
      <FormSectionDivider headline="API Key" descriptiveText={intro} />
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="caption" color="text.secondary">
          Checking key status…
        </Typography>
      </Box>
    </Box>
  );

  // One key at a time: a stored org key is read-only, and the input only
  // reappears once it has been removed. Avoids a "replace" path that silently
  // overwrites a working key.
  const configuredSection = status && (
    <Box sx={drawerSectionSx}>
      <FormSectionDivider
        headline="Current API Key"
        descriptiveText={
          fromEnv ? intro : `${intro} Remove this key to set a different one.`
        }
      />

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
        <StatusRow label="Source">
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {fromEnv ? 'Environment variable' : 'Saved key'}
          </Typography>
        </StatusRow>
        {status.last_checked_at && (
          <StatusRow label="Last checked">
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {new Date(status.last_checked_at).toLocaleString()}
            </Typography>
          </StatusRow>
        )}
      </Box>
    </Box>
  );

  const keyInputSection = (
    <Box sx={drawerSectionSx}>
      <FormSectionDivider
        headline={fromEnv ? 'Override API Key' : 'API Key'}
        descriptiveText={
          <>
            {fromEnv
              ? 'This key comes from the RHESIS_API_KEY environment variable, so it cannot be removed here. A key saved below takes precedence over it. '
              : `${intro} `}
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
          label="Enter your Rhesis API Key"
          fullWidth
          type={showKey ? 'text' : 'password'}
          value={keyInput}
          onChange={e => setKeyInput(e.target.value)}
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
      </Box>
    </Box>
  );

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Rhesis Platform API Key"
      titleIcon={<VpnKeyIcon />}
      // While a removable org key is set, removal is the only write available.
      onSave={removable ? undefined : handleSave}
      saveButtonText="Save"
      saveDisabled={!keyInput.trim() || mutating}
      onDelete={removable ? () => setRemoveConfirmOpen(true) : undefined}
      deleteButtonText="Remove"
      deleteDisabled={mutating}
      loading={setKey.isPending}
    >
      {query.isLoading ? (
        loadingSection
      ) : (
        <>
          {configured && configuredSection}
          {!removable && keyInputSection}
        </>
      )}

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
