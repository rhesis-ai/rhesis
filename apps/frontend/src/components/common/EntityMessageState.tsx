'use client';

import React from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import {
  EMPTY_STATE,
  emptyStateActionsRowSx,
  emptyStateCompactContentSx,
  emptyStateCompactTitleSx,
  emptyStateContainedActionSx,
  emptyStateDescriptionSx,
  emptyStateHeaderStackSx,
  emptyStateIconSx,
  emptyStateInnerStackSx,
  emptyStateOutlinedActionSx,
} from '@/components/common/entityEmptyStateSx';
import { EntityEmptyStateCardShell } from '@/components/common/EntityEmptyStateEnrichmentParts';

export interface EntityMessageAction {
  label: string;
  onClick: () => void;
  startIcon?: React.ReactNode;
  variant?: 'contained' | 'outlined';
  disabled?: boolean;
  loading?: boolean;
}

export interface EntityMessageStateProps {
  icon: React.ComponentType<SvgIconProps>;
  title: string;
  description?: string;
  meta?: string;
  primaryAction?: EntityMessageAction;
  secondaryAction?: EntityMessageAction;
  /** When true, shows a spinner instead of the icon. */
  loading?: boolean;
  card?: boolean;
}

function MessageActionButton({ action }: { action: EntityMessageAction }) {
  const variant = action.variant ?? 'outlined';

  return (
    <Button
      variant={variant}
      startIcon={
        action.loading ? (
          <CircularProgress
            color="inherit"
            size={EMPTY_STATE.spinnerSize.button}
          />
        ) : (
          action.startIcon
        )
      }
      onClick={action.onClick}
      disabled={action.disabled || action.loading}
      sx={
        variant === 'contained'
          ? emptyStateContainedActionSx
          : emptyStateOutlinedActionSx
      }
    >
      {action.label}
    </Button>
  );
}

/**
 * Figma-aligned status message used for entity detail not-found and
 * cross-project states. Matches EntityEmptyState card styling.
 */
export default function EntityMessageState({
  icon: Icon,
  title,
  description,
  meta,
  primaryAction,
  secondaryAction,
  loading = false,
  card = true,
}: EntityMessageStateProps) {
  const content = (
    <Box sx={emptyStateCompactContentSx()}>
      <Box sx={emptyStateInnerStackSx('md')}>
        <Box sx={emptyStateHeaderStackSx(true)}>
          {loading ? (
            <CircularProgress
              size={EMPTY_STATE.spinnerSize.icon}
              sx={{ color: 'primary.main' }}
            />
          ) : (
            <Icon sx={emptyStateIconSx(EMPTY_STATE.iconSize.compact)} />
          )}

          <Typography variant="h6" sx={emptyStateCompactTitleSx}>
            {title}
          </Typography>
        </Box>

        {description && (
          <Typography
            variant="body2"
            sx={emptyStateDescriptionSx({ compact: true })}
          >
            {description}
          </Typography>
        )}

        {meta && (
          <Typography variant="body2" color="text.secondary">
            {meta}
          </Typography>
        )}

        {(primaryAction || secondaryAction) && (
          <Box sx={emptyStateActionsRowSx}>
            {secondaryAction && <MessageActionButton action={secondaryAction} />}
            {primaryAction && <MessageActionButton action={primaryAction} />}
          </Box>
        )}
      </Box>
    </Box>
  );

  if (!card) {
    return <Box sx={{ width: '100%' }}>{content}</Box>;
  }

  return (
    <Box sx={{ width: '100%' }}>
      <EntityEmptyStateCardShell>{content}</EntityEmptyStateCardShell>
    </Box>
  );
}
