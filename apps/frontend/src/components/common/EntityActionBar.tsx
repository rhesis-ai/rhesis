'use client';

import React from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  type SxProps,
  type Theme,
} from '@mui/material';
import type { WithPermittedActions } from '@/types/affordances';
import { resolveEntityActions, type EntityAction } from './entity-actions';

interface EntityActionBarProps<T extends WithPermittedActions> {
  subject: T | null | undefined;
  actions: EntityAction<T>[];
  iconSize?: number;
  sx?: SxProps<Theme>;
}

/**
 * Generic renderer for a row of entity actions as icon buttons. Renders only the
 * actions the server permits and `isVisible` allows; business-rule-disabled
 * actions are shown disabled with their reason. Returns null when nothing is
 * permitted, so callers need no surrounding conditional.
 *
 * This is the single place action descriptors become UI — components declare
 * actions as data and drop in this bar; no per-action `canX` booleans.
 */
export function EntityActionBar<T extends WithPermittedActions>({
  subject,
  actions,
  iconSize = 20,
  sx,
}: EntityActionBarProps<T>) {
  const resolved = resolveEntityActions(subject, actions);
  if (resolved.length === 0) return null;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px', ...sx }}>
      {resolved.map(({ action, enabled }) => {
        const Icon = action.icon;
        const tooltip =
          !enabled && action.disabledReason
            ? action.disabledReason
            : action.label;
        return (
          <Tooltip key={action.id} title={tooltip}>
            {/* span wrapper keeps the tooltip working on a disabled button */}
            <Box component="span" sx={{ display: 'inline-flex' }}>
              <IconButton
                size="small"
                color="primary"
                aria-label={action.label}
                disabled={!enabled}
                onClick={() => subject && action.onSelect(subject)}
                sx={{ p: 0 }}
              >
                {Icon ? <Icon sx={{ fontSize: iconSize }} /> : null}
              </IconButton>
            </Box>
          </Tooltip>
        );
      })}
    </Box>
  );
}
