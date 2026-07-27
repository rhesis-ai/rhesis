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
import { can, useCan } from '@/components/common/Can';
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
  onRoleChanged?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrgRoleChip({
  userId,
  onRoleChanged,
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
    let cancelled = false;
    fetchOrgMembers()
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
  }, []);

  useEffect(() => {
    if (!rbacEnabled || !canManage) return;
    let cancelled = false;
    fetchRoles()
      .then(data => {
        if (!cancelled) setRoles(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [rbacEnabled, canManage]);

  const { level: myLevel, permissionNames: myPermissions } =
    useActorAuthority('org');
  const member = members.find(m => m.user_id === userId);
  const assignableRoles = roles.filter(
    r =>
      isAssignableOrgRole(r) &&
      isWithinActorAuthority(r, myLevel, myPermissions)
  );
  // The member's current role (e.g. Owner, or a role above the viewer's
  // authority) may not be in `assignableRoles`. MUI's Select warns
  // ("out-of-range value") when the controlled value has no matching
  // MenuItem, so always render it — disabled — if it's missing.
  const currentRoleInList = assignableRoles.some(r => r.id === member?.role_id);
  const extraCurrentRole =
    !currentRoleInList && member?.role ? member.role : null;

  const handleChange = useCallback(
    async (e: SelectChangeEvent<string>) => {
      const roleId = e.target.value;
      if (!roleId || roleId === member?.role_id) return;
      setAssigning(true);
      try {
        const client = new RbacClient();
        await client.assignOrgRole(userId, { role_id: roleId });
        invalidateOrgMembers();
        const fresh = await fetchOrgMembers();
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
    [userId, member?.role_id, onRoleChanged, notifications]
  );

  if (loading) {
    return <Skeleton variant="rounded" width={110} height={32} />;
  }

  // `member.permitted_actions` is server-resolved and already encodes every
  // reason this member can't be modified — self-change, last-Owner, or
  // outranking the actor (e.g. a project Admin viewing an org Owner). The
  // frontend must not re-derive any of that; it only checks membership.
  if (!can(member, Capability.Member.MANAGE)) {
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
      disabled={assigning}
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
        // `member.role` is already resolved by the backend and arrives with
        // the members fetch that gates the loading skeleton, so prefer it
        // over the separate (slower, permission-gated) roles catalog fetch —
        // otherwise the raw UUID flashes until that catalog resolves. Fall
        // back to the catalog only for the unexpected case where it's stale.
        const label =
          member?.role?.display_name ??
          roles.find(r => r.id === selected)?.display_name;
        return label ?? selected;
      }}
      sx={{ minWidth: 120, fontSize: 13 }}
    >
      {extraCurrentRole && (
        <MenuItem
          key={extraCurrentRole.id}
          value={extraCurrentRole.id}
          disabled
        >
          {extraCurrentRole.display_name}
        </MenuItem>
      )}
      {assignableRoles.map(role => (
        <MenuItem key={role.id} value={role.id}>
          {role.display_name}
        </MenuItem>
      ))}
    </Select>
  );
}
