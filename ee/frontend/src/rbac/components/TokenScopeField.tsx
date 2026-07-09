'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  alpha,
  Box,
  Chip,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import LockIcon from '@mui/icons-material/Lock';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { fetchRoles } from '../api/role-cache';
import { isAssignableProjectRole } from '../role-display';
import type { RoleRead } from '../types';
import {
  RESOURCE_AREAS,
  levelForArea,
  CapabilityLevel,
  LEVEL_LABELS,
} from '../capability-groups';

interface TokenScopeFieldProps {
  sessionToken: string;
  value: string[] | null;
  onChange: (scopes: string[] | null) => void;
}

const LEVEL_COLORS: Record<CapabilityLevel, string> = {
  [CapabilityLevel.NONE]: 'default',
  [CapabilityLevel.VIEW]: 'info',
  [CapabilityLevel.EDIT]: 'warning',
  [CapabilityLevel.MANAGE]: 'success',
};

export default function TokenScopeField({
  sessionToken,
  value,
  onChange,
}: TokenScopeFieldProps) {
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const mode = value === null ? 'full' : 'restricted';

  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    fetchRoles(sessionToken)
      .then(data => {
        if (!cancelled) {
          setRoles(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  const assignableRoles = useMemo(
    () => roles.filter(isAssignableProjectRole),
    [roles]
  );

  const selectedRole = useMemo(
    () => roles.find(r => r.id === selectedRoleId),
    [roles, selectedRoleId]
  );

  const areaSummary = useMemo(() => {
    if (!selectedRole?.permissions) return [];
    const permSet = new Set(selectedRole.permissions.map(p => p.name));
    return RESOURCE_AREAS.map(area => ({
      label: area.label,
      level: levelForArea(permSet, area),
    }));
  }, [selectedRole]);

  const handleModeChange = (newMode: string) => {
    if (newMode === 'full') {
      setSelectedRoleId('');
      onChange(null);
    } else {
      if (selectedRoleId && selectedRole?.permissions) {
        onChange(selectedRole.permissions.map(p => p.name));
      } else {
        onChange([]);
      }
    }
  };

  const handleRoleChange = (roleId: string) => {
    setSelectedRoleId(roleId);
    if (!roleId) {
      onChange([]);
      return;
    }
    const role = roles.find(r => r.id === roleId);
    if (role?.permissions) {
      onChange(role.permissions.map(p => p.name));
    }
  };

  if (loading) return null;
  if (assignableRoles.length === 0) return null;

  return (
    <Stack spacing={2}>
      <Typography variant="subtitle2" color="text.secondary">
        Token permissions
      </Typography>

      <RadioGroup value={mode} onChange={e => handleModeChange(e.target.value)}>
        <FormControlLabel
          value="full"
          control={<Radio size="small" />}
          label={
            <Stack direction="row" spacing={1} alignItems="center">
              <LockOpenIcon
                fontSize="small"
                sx={{ color: (t: Theme) => t.palette.greyscale.subtitle }}
              />
              <Typography variant="body2">
                Full access — inherits your permissions
              </Typography>
            </Stack>
          }
        />
        <FormControlLabel
          value="restricted"
          control={<Radio size="small" />}
          label={
            <Stack direction="row" spacing={1} alignItems="center">
              <LockIcon
                fontSize="small"
                sx={{ color: (t: Theme) => t.palette.greyscale.subtitle }}
              />
              <Typography variant="body2">
                Restricted — scoped to a role
              </Typography>
            </Stack>
          }
        />
      </RadioGroup>

      {mode === 'restricted' && (
        <>
          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel id="token-role-label" shrink>
              Role template
            </InputLabel>
            <Select
              labelId="token-role-label"
              label="Role template"
              value={selectedRoleId}
              displayEmpty
              notched
              onChange={e => handleRoleChange(e.target.value)}
              renderValue={value => {
                if (!value) {
                  return (
                    <Typography variant="body1" color="text.secondary">
                      Select a role
                    </Typography>
                  );
                }
                const role = assignableRoles.find(r => r.id === value);
                return role?.display_name ?? value;
              }}
            >
              <MenuItem value="">
                <Typography variant="body1" color="text.secondary">
                  Select a role
                </Typography>
              </MenuItem>
              {assignableRoles.map(role => (
                <MenuItem key={role.id} value={role.id}>
                  {role.display_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {selectedRole && areaSummary.length > 0 && (
            <Box
              sx={{
                p: 1.5,
                borderRadius: BORDER_RADIUS.sm,
                bgcolor: (t: Theme) => alpha(t.palette.primary.main, 0.04),
                border: (t: Theme) =>
                  `1px solid ${alpha(t.palette.primary.main, 0.12)}`,
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 1, display: 'block' }}
              >
                Permission summary
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {areaSummary.map(({ label, level }) => (
                  <Chip
                    key={label}
                    size="small"
                    label={`${label}: ${LEVEL_LABELS[level]}`}
                    color={
                      LEVEL_COLORS[level] as
                        | 'default'
                        | 'info'
                        | 'warning'
                        | 'success'
                    }
                    variant={
                      level === CapabilityLevel.NONE ? 'outlined' : 'filled'
                    }
                    sx={(t: Theme) => ({
                      fontSize: t.typography.caption.fontSize,
                      height: t.spacing(2.75),
                    })}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </>
      )}
    </Stack>
  );
}
