'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Chip,
  MenuItem,
  Select,
  SelectChangeEvent,
  Skeleton,
  Typography,
} from '@mui/material';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useFeature } from '@/contexts/FeaturesContext';
import { FeatureName } from '@/constants/features';
import { useNotifications } from '@/components/common/NotificationContext';
import { RbacClient } from '../api/rbac-client';
import { fetchRoles } from '../api/role-cache';
import {
  fetchOrgMembers,
  invalidateOrgMembers,
  getCachedOrgMembers,
} from '../api/org-members-cache';
import {
  getRoleChipSx,
  isAssignableOrgRole,
  isWithinActorAuthority,
} from '../role-display';
import { useActorAuthority } from '../hooks/useActorAuthority';
import type { OrgMemberRead, RoleRead } from '../types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OrgRoleChipProps {
  userId: string;
  sessionToken: string;
  onRoleChanged?: () => void;
  currentUserId?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrgRoleChip({
  userId,
  sessionToken,
  onRoleChanged,
  currentUserId,
}: OrgRoleChipProps) {
  const rbacEnabled = useFeature(FeatureName.RBAC);
  const canManage = useCan(Capability.Member.MANAGE);
  const notifications = useNotifications();
  const [members, setMembers] = useState<OrgMemberRead[]>(
    getCachedOrgMembers()
  );
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(getCachedOrgMembers().length === 0);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    fetchOrgMembers(sessionToken)
      .then(data => {
        if (!cancelled) {
          setMembers(data);
          setLoading(false);
        }
      })
      .catch(() => {
        // Unlicensed RBAC (404, since /rbac/* is gated by require_feature) or
        // any other fetch failure: fall back to a plain display instead of
        // hanging in the loading skeleton forever. Mirrors ProjectRoleChip,
        // which already handles this correctly.
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    if (!rbacEnabled || !sessionToken || !canManage) return;
    let cancelled = false;
    fetchRoles(sessionToken)
      .then(data => {
        if (!cancelled) setRoles(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [rbacEnabled, sessionToken, canManage]);

  const { level: myLevel, permissionNames: myPermissions } = useActorAuthority(
    sessionToken,
    'org'
  );
  const member = members.find(m => m.user_id === userId);
  const assignableRoles = roles.filter(
    r =>
      isAssignableOrgRole(r) &&
      isWithinActorAuthority(r, myLevel, myPermissions)
  );

  const handleChange = useCallback(
    async (e: SelectChangeEvent<string>) => {
      const roleId = e.target.value;
      if (!roleId || roleId === member?.role_id) return;
      setAssigning(true);
      try {
        const client = new RbacClient(sessionToken);
        await client.assignOrgRole(userId, { role_id: roleId });
        invalidateOrgMembers();
        const fresh = await fetchOrgMembers(sessionToken);
        setMembers(fresh);
        onRoleChanged?.();
        notifications.show('Role updated', { severity: 'success' });
      } catch (err) {
        // A last-owner-demotion or escalation rejection lands here (e.g. 400
        // "Cannot demote the last Owner of an organization"); without this,
        // the select silently re-enables with no indication the change failed.
        notifications.show(
          err instanceof Error ? err.message : 'Failed to update role',
          { severity: 'error' }
        );
      } finally {
        setAssigning(false);
      }
    },
    [sessionToken, userId, member?.role_id, onRoleChanged, notifications]
  );

  if (loading) {
    return <Skeleton variant="rounded" width={110} height={32} />;
  }

  // Changing your own org role is high-risk (self-demotion, including the
  // last-Owner case) and gets no confirmation step, so it is read-only here
  // rather than merely discouraged.
  if (currentUserId && userId === currentUserId) {
    if (!member?.role) {
      return (
        <Typography variant="body2" color="text.disabled">
          —
        </Typography>
      );
    }
    return (
      <Chip
        label={member.role.display_name}
        size="small"
        sx={getRoleChipSx(member.role)}
      />
    );
  }

  return (
    <Select
      value={member?.role_id ?? ''}
      onChange={handleChange}
      disabled={!canManage || assigning}
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
        // Use the full roles list so non-assignable roles (e.g. Owner) still
        // display their name rather than falling back to the raw UUID.
        const role = roles.find(r => r.id === selected);
        return role?.display_name ?? selected;
      }}
      sx={{ minWidth: 120, fontSize: 13 }}
    >
      {assignableRoles.map(role => (
        <MenuItem key={role.id} value={role.id}>
          {role.display_name}
        </MenuItem>
      ))}
    </Select>
  );
}
