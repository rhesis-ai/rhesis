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
  fetchProjectMembers,
  invalidateProjectMembers,
  hasProjectMembers,
  getCachedProjectMembers,
} from '../api/project-members-cache';
import {
  getRoleChipSx,
  isAssignableProjectRole,
  isWithinActorAuthority,
} from '../role-display';
import { useActorAuthority } from '../hooks/useActorAuthority';
import type { ProjectMemberRoleRead, RoleRead } from '../types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ProjectRoleChipProps {
  userId: string;
  projectId: string;
  sessionToken: string;
  onRoleChanged?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ProjectRoleChip({
  userId,
  projectId,
  sessionToken,
  onRoleChanged,
}: ProjectRoleChipProps) {
  const rbacEnabled = useFeature(FeatureName.RBAC);
  const canManage = useCan(Capability.ProjectMember.MANAGE);
  const notifications = useNotifications();
  const [members, setMembers] = useState<ProjectMemberRoleRead[]>(
    getCachedProjectMembers(sessionToken, projectId)
  );
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(
    !hasProjectMembers(sessionToken, projectId)
  );
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (!sessionToken || !projectId) return;
    let cancelled = false;
    fetchProjectMembers(sessionToken, projectId)
      .then(data => {
        if (!cancelled) {
          setMembers(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken, projectId]);

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
    'project',
    projectId
  );
  const memberEntry = members.find(m => m.user_id === userId);
  const assignableRoles = roles.filter(
    r =>
      isAssignableProjectRole(r) &&
      isWithinActorAuthority(r, myLevel, myPermissions)
  );
  // The member's current role (e.g. Owner, or a role above the viewer's
  // authority) may not be in `assignableRoles`. MUI's Select warns
  // ("out-of-range value") when the controlled value has no matching
  // MenuItem, so always render it — disabled — if it's missing.
  const currentRoleInList = assignableRoles.some(
    r => r.id === memberEntry?.role_id
  );
  const extraCurrentRole =
    !currentRoleInList && memberEntry?.role ? memberEntry.role : null;

  const handleChange = useCallback(
    async (e: SelectChangeEvent<string>) => {
      const roleId = e.target.value;
      if (!roleId || roleId === memberEntry?.role_id) return;
      setAssigning(true);
      try {
        const client = new RbacClient(sessionToken);
        await client.assignProjectRole(projectId, userId, { role_id: roleId });
        invalidateProjectMembers(sessionToken, projectId);
        const fresh = await fetchProjectMembers(sessionToken, projectId);
        setMembers(fresh);
        onRoleChanged?.();
        notifications.show('Project role updated', { severity: 'success' });
      } catch (err) {
        notifications.show(
          err instanceof Error ? err.message : 'Failed to update project role',
          { severity: 'error' }
        );
      } finally {
        setAssigning(false);
      }
    },
    [
      sessionToken,
      projectId,
      userId,
      memberEntry?.role_id,
      onRoleChanged,
      notifications,
    ]
  );

  if (loading) {
    return <Skeleton variant="rounded" width={110} height={32} />;
  }

  // `memberEntry.permitted_actions` is server-resolved and already encodes
  // every reason this member can't be modified — self-change or outranking
  // the actor. The frontend must not re-derive any of that; it only checks
  // membership. Uses `Capability.Member.MANAGE` (not `ProjectMember.MANAGE`)
  // because `assign_project_role`/`list_project_members` are gated by the
  // same `member:manage` capability as the org-level endpoints, evaluated
  // at project scope.
  if (!can(memberEntry, Capability.Member.MANAGE)) {
    if (!memberEntry?.role) {
      return (
        <Typography variant="body2" color="text.disabled">
          —
        </Typography>
      );
    }
    return (
      <Chip
        label={memberEntry.role.display_name}
        size="small"
        sx={getRoleChipSx(memberEntry.role)}
      />
    );
  }

  return (
    <Select
      value={memberEntry?.role_id ?? ''}
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
        // `memberEntry.role` is already resolved by the backend and arrives
        // with the members fetch that gates the loading skeleton, so prefer
        // it over the separate (slower, permission-gated) roles catalog
        // fetch — otherwise the raw UUID flashes until that catalog
        // resolves. Fall back to the catalog only for the unexpected case
        // where it's stale.
        const label =
          memberEntry?.role?.display_name ??
          roles.find(r => r.id === selected)?.display_name;
        return label ?? selected;
      }}
      sx={{ minWidth: 120, fontSize: 13 }}
    >
      {extraCurrentRole && (
        <MenuItem key={extraCurrentRole.id} value={extraCurrentRole.id} disabled>
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
