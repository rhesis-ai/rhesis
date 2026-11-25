'use client';

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import Typography from '@mui/material/Typography';
import {
  ArrowForward as ArrowIcon,
  ExpandMore as ExpandIcon,
  WarningAmber as WarnIcon,
} from '@mui/icons-material';
import type { RoleMappingPreview } from '../types';
import { useRoleMappingData } from './context';
import { RoleChip } from './RuleRow';

/** One line saying who changes at their next sign-in; the list on demand. */
export default function ChangeSummary({
  preview,
  loading,
}: {
  preview: RoleMappingPreview | null;
  loading: boolean;
}) {
  const { catalog } = useRoleMappingData();
  const [open, setOpen] = useState(false);
  if (!preview) {
    return loading ? (
      <CircularProgress size={16} aria-label="Checking who changes" />
    ) : null;
  }
  const { changes, without_sign_in: unknown } = preview;
  const lowered = changes.filter(c => c.less_access);
  const chip = (name: string | null) => {
    const role = catalog.roles.find(r => r.name === name);
    return role ? (
      <RoleChip role={role} />
    ) : (
      <Typography variant="body2">{name}</Typography>
    );
  };

  return (
    <Box
      aria-live="polite"
      sx={{
        border: 1,
        borderColor: lowered.length ? 'warning.main' : 'divider',
        borderRadius: t => `${t.shape.borderRadius}px`,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5 }}>
        {lowered.length > 0 && <WarnIcon color="warning" fontSize="small" />}
        <Typography variant="body2" sx={{ flex: 1 }}>
          {preview.new_accounts_only ? (
            'Existing members keep their roles. The mapping applies at each person’s first SSO sign-in.'
          ) : changes.length === 0 ? (
            'Nobody’s organization role changes.'
          ) : (
            <>
              <b>
                {changes.length} {changes.length === 1 ? 'member' : 'members'}
              </b>{' '}
              {changes.length === 1 ? 'changes' : 'change'} at their next
              sign-in
              {lowered.length > 0 && (
                <>
                  , <b>{lowered.length}</b> of them get less access
                </>
              )}
              .
            </>
          )}
          {unknown > 0 &&
            ` ${unknown} ${unknown === 1 ? 'member hasn’t' : 'members haven’t'} signed in with SSO yet, so their groups aren’t known.`}
        </Typography>
        {loading && <CircularProgress size={16} />}
        {changes.length > 0 && (
          <Button
            size="small"
            endIcon={
              <ExpandIcon
                sx={{ transform: open ? 'rotate(180deg)' : 'none' }}
              />
            }
            onClick={() => setOpen(!open)}
            aria-expanded={open}
          >
            {open ? 'Hide' : 'Review'}
          </Button>
        )}
      </Box>
      <Collapse in={open}>
        <Divider />
        <Box
          sx={{
            p: 1.5,
            display: 'grid',
            gridTemplateColumns: 'minmax(0, auto) 1fr',
            columnGap: 3,
            rowGap: 1,
            alignItems: 'center',
          }}
        >
          {changes.map(c => (
            <React.Fragment key={c.user_id}>
              <Typography variant="body2" title={c.email}>
                {c.name}
              </Typography>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  flexWrap: 'wrap',
                }}
              >
                {chip(c.from_role)}
                <ArrowIcon
                  fontSize="small"
                  sx={{
                    color: c.less_access ? 'warning.main' : 'text.secondary',
                  }}
                />
                {c.blocked ? (
                  <Typography variant="body2" color="error.main">
                    Can&apos;t sign in
                  </Typography>
                ) : (
                  chip(c.to_role)
                )}
              </Box>
            </React.Fragment>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
