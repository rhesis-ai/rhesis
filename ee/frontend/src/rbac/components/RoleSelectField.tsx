'use client';

import React, { useEffect, useState } from 'react';
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  Typography,
} from '@mui/material';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import { fetchRoles } from '../api/role-cache';
import {
  isAssignableOrgRole,
  isAssignableProjectRole,
  isWithinActorAuthority,
} from '../role-display';
import { useActorAuthority } from '../hooks/useActorAuthority';
import type { RoleRead } from '../types';

interface RoleSelectFieldProps {
  sessionToken: string;
  value: string | null;
  onChange: (roleId: string | null) => void;
  size?: 'small' | 'medium';
  /** Which tier of roles to list. Defaults to project-scoped assignment. */
  scope?: 'org' | 'project';
}

export default function RoleSelectField({
  sessionToken,
  value,
  onChange,
  size = 'medium',
  scope = 'project',
}: RoleSelectFieldProps) {
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);

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

  const { level: myLevel, permissionNames: myPermissions } = useActorAuthority(
    sessionToken,
    'org'
  );
  const assignableRoles = roles.filter(r =>
    (scope === 'org' ? isAssignableOrgRole(r) : isAssignableProjectRole(r)) &&
      isWithinActorAuthority(r, myLevel, myPermissions)
  );
  const roleLabel = 'Assign role';

  if (loading) {
    return <Skeleton variant="rounded" height={size === 'small' ? 32 : 56} />;
  }

  if (size === 'small') {
    return (
      <Select
        value={value ?? ''}
        onChange={e => onChange(e.target.value || null)}
        size="small"
        displayEmpty
        renderValue={selected => {
          if (!selected) {
            return (
              <Typography variant="body2" color="text.disabled">
                Assign role
              </Typography>
            );
          }
          return (
            assignableRoles.find(r => r.id === selected)?.display_name ??
            selected
          );
        }}
        sx={{
          minWidth: theme => theme.spacing(15),
          fontSize: theme => theme.typography.body2.fontSize,
        }}
        onClick={e => e.stopPropagation()}
      >
        {assignableRoles.map(role => (
          <MenuItem key={role.id} value={role.id}>
            {role.display_name}
          </MenuItem>
        ))}
      </Select>
    );
  }

  return (
    <FormControl fullWidth sx={drawerOutlinedFieldSx}>
      <InputLabel id="role-select-label">{roleLabel}</InputLabel>
      <Select
        labelId="role-select-label"
        label={roleLabel}
        value={value ?? ''}
        onChange={e => onChange(e.target.value || null)}
      >
        <MenuItem value="">
          <em>Default (Member)</em>
        </MenuItem>
        {assignableRoles.map(role => (
          <MenuItem key={role.id} value={role.id}>
            {role.display_name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
