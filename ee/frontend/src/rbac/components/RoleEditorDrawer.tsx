'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Link, Stack, TextField, Typography } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import {
  drawerOutlinedFieldSx,
  ROLE_EDITOR_DRAWER_WIDTH,
} from '@/components/common/drawerFormFieldSx';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOrgSettings } from '@/contexts/OrgSettingsContext';
import { RbacClient } from '../api/rbac-client';
import { invalidateRoles } from '../api/role-cache';
import { useActorAuthority } from '../hooks/useActorAuthority';
import { isCopyableRole } from '../role-display';
import type { RoleRead } from '../types';
import {
  CapabilityLevel,
  RESOURCE_AREAS,
  applyCapabilityToggle,
  applyLevel,
  areaCapabilitySet,
  levelForArea,
} from '../capability-groups';
import PermissionGroupControl from './PermissionGroupControl';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DrawerMode = 'view' | 'create' | 'edit';

export interface RoleEditorDrawerProps {
  open: boolean;
  onClose: () => void;
  mode: DrawerMode;
  role?: RoleRead;
  roles?: RoleRead[];
  onSaved?: (role: RoleRead) => void;
  onDeleted?: (roleId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RoleEditorDrawer({
  open,
  onClose,
  mode,
  role,
  roles = [],
  onSaved,
  onDeleted,
}: RoleEditorDrawerProps) {
  const { sessionToken } = useOrgSettings();
  const notifications = useNotifications();
  const readOnly = mode === 'view';
  const isCreate = mode === 'create';

  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [permissions, setPermissions] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  // Org-tier actor authority (matches the backend's project_id=None escalation
  // check for create_role/update_role) — drives the per-area maxLevel below so
  // an over-grant is disabled in the UI instead of rejected at save time.
  const { permissionNames: actorPermissions } = useActorAuthority(
    sessionToken,
    'org'
  );

  // Reset form when drawer opens or role changes
  useEffect(() => {
    if (!open) return;
    setError(undefined);
    setSubmitting(false);
    if (role && !isCreate) {
      setDisplayName(role.display_name);
      setDescription(role.description ?? '');
      setPermissions(new Set(role.permissions.map(p => p.name)));
    } else {
      setDisplayName('');
      setDescription('');
      setPermissions(new Set());
    }
  }, [open, role, isCreate]);

  const handleLevelChange = useCallback(
    (area: (typeof RESOURCE_AREAS)[number], level: CapabilityLevel) => {
      setPermissions(prev => {
        const next = new Set(prev);
        applyLevel(next, area, level);
        return next;
      });
    },
    []
  );

  const handleToggleCapability = useCallback(
    (cap: string, area: (typeof RESOURCE_AREAS)[number]) => {
      setPermissions(prev => {
        const next = new Set(prev);
        applyCapabilityToggle(next, cap, areaCapabilitySet(area));
        return next;
      });
    },
    []
  );

  const handleCopyFrom = useCallback(
    (roleId: string) => {
      const source = roles.find(r => r.id === roleId);
      if (source) {
        setPermissions(new Set(source.permissions.map(p => p.name)));
      }
    },
    [roles]
  );

  const canSave = !submitting && displayName.trim().length > 0 && !readOnly;

  const handleSave = async () => {
    if (!canSave) return;
    setSubmitting(true);
    setError(undefined);
    const client = new RbacClient(sessionToken);

    try {
      let saved: RoleRead;
      if (isCreate) {
        saved = await client.createRole({
          name: displayName.trim().toLowerCase().replace(/\s+/g, '_'),
          display_name: displayName.trim(),
          description: description.trim(),
          permission_names: [...permissions],
        });
      } else if (role) {
        saved = await client.updateRole(role.id, {
          display_name: displayName.trim(),
          description: description.trim(),
          permission_names: [...permissions],
        });
      } else {
        return;
      }
      onSaved?.(saved);
      invalidateRoles();
      onClose();
      notifications.show(isCreate ? 'Role created' : 'Role updated', {
        severity: 'success',
      });
    } catch (err) {
      const status = (err as { status?: number })?.status;
      setError(
        status === 409
          ? 'A role with this name already exists'
          : err instanceof Error
            ? err.message
            : 'Failed to save role'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteConfirmed = async () => {
    if (!role || readOnly || role.is_built_in) return;
    setSubmitting(true);
    setError(undefined);
    const client = new RbacClient(sessionToken);

    try {
      await client.deleteRole(role.id);
      invalidateRoles();
      setDeleteConfirmOpen(false);
      onDeleted?.(role.id);
      onClose();
      notifications.show('Role deleted', { severity: 'success' });
    } catch (err) {
      setDeleteConfirmOpen(false);
      setError(err instanceof Error ? err.message : 'Failed to delete role');
    } finally {
      setSubmitting(false);
    }
  };

  const title = isCreate
    ? 'Create Custom Role'
    : readOnly
      ? (role?.display_name ?? 'Role Details')
      : `Edit ${role?.display_name ?? 'Role'}`;

  const copyFromRoles = roles.filter(isCopyableRole);

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      width={ROLE_EDITOR_DRAWER_WIDTH}
      onSave={readOnly ? undefined : handleSave}
      saveButtonText={
        submitting ? 'Saving...' : isCreate ? 'Create role' : 'Save changes'
      }
      saveDisabled={!canSave}
      loading={submitting}
      error={error}
      closeButtonText={readOnly ? 'Close' : 'Cancel'}
      onDelete={
        !readOnly && !isCreate && role && !role.is_built_in
          ? () => setDeleteConfirmOpen(true)
          : undefined
      }
      deleteButtonText="Delete role"
    >
      {/* Role name and description */}
      {!readOnly && (
        <Stack spacing={2}>
          <TextField
            label="Role name"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            fullWidth
            required
            variant="outlined"
            disabled={submitting}
            helperText="A clear, descriptive name for this role"
            sx={drawerOutlinedFieldSx}
          />

          <TextField
            label="Description"
            value={description}
            onChange={e => setDescription(e.target.value)}
            multiline
            rows={4}
            fullWidth
            variant="outlined"
            disabled={submitting}
            helperText="Describe what this role is for and who should have it"
          />
        </Stack>
      )}

      {/* Read-only header for built-in roles */}
      {readOnly && role && (
        <Stack spacing={1.5}>
          <Typography variant="body2" color="text.secondary">
            {role.is_built_in ? 'Built-in role' : 'Custom role'} ·{' '}
            {role.permissions.length} permissions
          </Typography>
          {role.is_built_in && (
            <Alert severity="info">
              Permissions for built-in roles are fixed and cannot be changed.
            </Alert>
          )}
        </Stack>
      )}

      {/* Access by area */}
      <Box>
        <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
          Access by area
        </Typography>
        {isCreate && copyFromRoles.length > 0 && (
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
            mb={1.5}
          >
            <Typography variant="caption" color="text.secondary" noWrap>
              Optionally copy permissions from:
            </Typography>
            {copyFromRoles.map(r => (
              <Link
                key={r.id}
                component="button"
                type="button"
                variant="caption"
                color="primary"
                onClick={() => handleCopyFrom(r.id)}
              >
                {r.display_name}
              </Link>
            ))}
          </Stack>
        )}
        <Stack spacing={1.5}>
          {RESOURCE_AREAS.map(area => (
            <PermissionGroupControl
              key={area.id}
              area={area}
              currentLevel={levelForArea(permissions, area)}
              onLevelChange={lvl => handleLevelChange(area, lvl)}
              permissions={permissions}
              onToggleCapability={cap => handleToggleCapability(cap, area)}
              readOnly={readOnly}
              maxLevel={levelForArea(actorPermissions, area)}
            />
          ))}
        </Stack>
      </Box>

      {role && (
        <DeleteModal
          open={deleteConfirmOpen}
          onClose={() => setDeleteConfirmOpen(false)}
          onConfirm={handleDeleteConfirmed}
          isLoading={submitting}
          title="Delete role"
          itemName={role.display_name}
          itemType="role"
          warningMessage={
            role.member_count > 0
              ? `${role.member_count} member${role.member_count === 1 ? '' : 's'} currently ${
                  role.member_count === 1 ? 'holds' : 'hold'
                } this role. Deleting it removes the role from them — organization-level holders lose its access, and project-level holders revert to their inherited organization role.`
              : undefined
          }
        />
      )}
    </BaseDrawer>
  );
}
