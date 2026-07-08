'use client';

import React, { useState } from 'react';
import {
  alpha,
  Box,
  Checkbox,
  Collapse,
  FormControlLabel,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import {
  CapabilityLevel,
  groupAreaCapabilitiesByResource,
  LEVEL_LABELS,
  type ResourceArea,
} from '../capability-groups';

interface PermissionGroupControlProps {
  area: ResourceArea;
  currentLevel: CapabilityLevel;
  onLevelChange: (level: CapabilityLevel) => void;
  permissions: ReadonlySet<string>;
  onToggleCapability: (cap: string) => void;
  maxLevel?: CapabilityLevel;
  readOnly?: boolean;
}

const LEVELS = [
  CapabilityLevel.NONE,
  CapabilityLevel.VIEW,
  CapabilityLevel.EDIT,
  CapabilityLevel.MANAGE,
] as const;

const PERMISSION_COLUMNS = [
  { key: 'view' as const, label: 'View' },
  { key: 'create' as const, label: 'Create' },
  { key: 'editOwn' as const, label: 'Edit (own)' },
  { key: 'editAll' as const, label: 'Edit (all)' },
  { key: 'deleteOwn' as const, label: 'Delete (own)' },
  { key: 'deleteAll' as const, label: 'Delete (all)' },
] as const;

const PERMISSION_GRID_COLUMNS =
  'minmax(120px, max-content) repeat(6, 54px) minmax(200px, 1fr)';

const permissionGridRowSx = {
  display: 'grid',
  gridTemplateColumns: PERMISSION_GRID_COLUMNS,
  columnGap: 0.5,
  alignItems: 'center',
} as const;

const crudHeaderCellSx = {
  display: 'flex',
  justifyContent: 'center',
  textAlign: 'center',
  px: 0.25,
} as const;

const crudCheckboxCellSx = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  minHeight: 36,
} as const;

const permissionCheckboxSx = {
  p: 0.5,
  m: 0,
} as const;

function PermissionCheckbox({
  cap,
  label,
  checked,
  onToggle,
  readOnly,
  compact = false,
}: {
  cap: string;
  label: string;
  checked: boolean;
  onToggle: (cap: string) => void;
  readOnly?: boolean;
  compact?: boolean;
}) {
  return (
    <FormControlLabel
      control={
        <Checkbox
          size="small"
          checked={checked}
          onChange={() => onToggle(cap)}
          disabled={readOnly}
        />
      }
      label={
        <Typography variant={compact ? 'caption' : 'body2'} sx={{ fontSize: 12 }}>
          {label}
        </Typography>
      }
      sx={{ mr: compact ? 1 : 2, ml: 0 }}
    />
  );
}

export default function PermissionGroupControl({
  area,
  currentLevel,
  onLevelChange,
  permissions,
  onToggleCapability,
  maxLevel = CapabilityLevel.MANAGE,
  readOnly = false,
}: PermissionGroupControlProps) {
  const [expanded, setExpanded] = useState(false);
  const resourceRows = groupAreaCapabilitiesByResource(area);

  const allCaps = new Set(
    Object.values(area.levels).flatMap(caps => [...caps])
  );
  const grantedCount = [...allCaps].filter(c => permissions.has(c)).length;

  return (
    <Box
      sx={{
        border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        overflow: 'hidden',
      }}
    >
      {/* Header row */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          px: 2,
          py: 1.5,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {area.label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {area.description}
            {grantedCount > 0 && ` · ${grantedCount} granted`}
          </Typography>
        </Box>

        <ToggleButtonGroup
          value={currentLevel}
          exclusive
          onChange={(_, val) => {
            if (val !== null && !readOnly) onLevelChange(val);
          }}
          size="small"
          sx={{
            flexShrink: 0,
            border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
            borderRadius: BORDER_RADIUS.sm,
            '& .MuiToggleButtonGroup-grouped': {
              border: 'none',
              borderRadius: `${BORDER_RADIUS.sm} !important`,
              mx: '1px',
              px: 1.5,
              py: 0.5,
              fontSize: 12,
              fontWeight: 600,
              textTransform: 'none',
              color: (t: Theme) => t.palette.greyscale.subtitle,
              '&.Mui-disabled': {
                color: (t: Theme) => t.palette.greyscale.border,
              },
            },
          }}
        >
          {LEVELS.map(lvl => {
            const isNone = lvl === CapabilityLevel.NONE;
            const aboveMax = lvl > maxLevel;
            return (
              <ToggleButton
                key={lvl}
                value={lvl}
                disabled={readOnly || aboveMax}
                title={aboveMax ? 'Above your own access' : undefined}
                sx={{
                  '&.Mui-selected': isNone
                    ? {
                        bgcolor: (t: Theme) => t.palette.greyscale.surface2,
                        color: (t: Theme) =>
                          `${t.palette.greyscale.subtitle} !important`,
                        '&:hover': {
                          bgcolor: (t: Theme) => t.palette.greyscale.surface2,
                        },
                      }
                    : {
                        bgcolor: 'primary.main',
                        color: (t: Theme) =>
                          `${t.palette.primary.contrastText} !important`,
                        '&:hover': {
                          bgcolor: 'primary.dark',
                        },
                      },
                }}
              >
                {LEVEL_LABELS[lvl]}
              </ToggleButton>
            );
          })}
        </ToggleButtonGroup>

        <IconButton
          size="small"
          onClick={() => setExpanded(v => !v)}
          aria-label={expanded ? 'Collapse permissions' : 'Expand permissions'}
          aria-expanded={expanded}
          sx={{
            flexShrink: 0,
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderTop: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
            bgcolor: (t: Theme) => alpha(t.palette.greyscale.surface1, 0.5),
          }}
        >
          <Box
            sx={{
              ...permissionGridRowSx,
              pb: 1,
              borderBottom: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
              mb: 0.5,
            }}
          >
            <Typography variant="caption" sx={{ fontWeight: 700, color: 'greyscale.body' }}>
              Resource
            </Typography>
            {PERMISSION_COLUMNS.map(col => (
              <Typography
                key={col.key}
                variant="caption"
                sx={{
                  fontWeight: 700,
                  color: 'greyscale.body',
                  fontSize: 10,
                  lineHeight: 1.2,
                  ...crudHeaderCellSx,
                }}
              >
                {col.label}
              </Typography>
            ))}
            <Typography variant="caption" sx={{ fontWeight: 700, color: 'greyscale.body' }}>
              Other
            </Typography>
          </Box>

          {resourceRows.map(row => (
            <Box
              key={row.resourceId}
              sx={{
                ...permissionGridRowSx,
                py: 0.75,
                borderBottom: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
                '&:last-child': { borderBottom: 'none' },
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: 13 }}>
                {row.label}
              </Typography>

              {PERMISSION_COLUMNS.map(col => {
                const cap = row[col.key];
                return (
                  <Box key={col.key} sx={crudCheckboxCellSx}>
                    {cap ? (
                      <Checkbox
                        size="small"
                        checked={permissions.has(cap)}
                        onChange={() => onToggleCapability(cap)}
                        disabled={readOnly}
                        sx={permissionCheckboxSx}
                        inputProps={{ 'aria-label': `${row.label} ${col.label}` }}
                      />
                    ) : null}
                  </Box>
                );
              })}

              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {row.extras.map(extra => (
                  <PermissionCheckbox
                    key={extra.cap}
                    cap={extra.cap}
                    label={extra.label}
                    checked={permissions.has(extra.cap)}
                    onToggle={onToggleCapability}
                    readOnly={readOnly}
                    compact
                  />
                ))}
              </Box>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
