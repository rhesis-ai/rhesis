'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import AddIcon from '@mui/icons-material/Add';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import AccessDenied from '@/components/common/AccessDenied';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { ROW_ACTIONS_CLASS } from '@/components/common/createRowActionsColumn';
import { EditIcon, DeleteIcon } from '@/components/icons';
import { SectionCard, overviewTableInnerSx } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import {
  sectionCardGridBleedSx,
  sectionCardGridTableInsetSx,
  sectionCardGridTableEdgeCellResetSx,
} from '@/components/common/GridToolbar';
import { useOrgSettings } from '@/contexts/OrgSettingsContext';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { RbacClient } from '../api/rbac-client';
import { fetchRoles } from '../api/role-cache';
import { getRoleChipSx } from '../role-display';
import type { RoleRead } from '../types';
import RoleEditorDrawer, { type DrawerMode } from './RoleEditorDrawer';

// Figma Frontend node 1640:23151 — overview table inside section cards
const customRolesTableSx = {
  ...overviewTableInnerSx,
  [`& .${ROW_ACTIONS_CLASS}`]: {
    opacity: 0,
    pointerEvents: 'none',
    transition: 'opacity 0.15s ease',
  },
  [`& .MuiTableRow-root:hover .${ROW_ACTIONS_CLASS}, & .MuiTableRow-root:focus-within .${ROW_ACTIONS_CLASS}`]:
    {
      opacity: 1,
      pointerEvents: 'auto',
    },
} as const;

const customRolesHeaderCellSx = {
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  color: 'greyscale.body',
  height: 48,
  p: 0,
  bgcolor: 'background.paper',
  borderBottom: 'none',
  verticalAlign: 'middle',
} as const;

const customRolesBodyCellSx = {
  fontSize: 14,
  lineHeight: '22px',
  color: 'greyscale.body',
  py: '12px',
  px: '12px',
  borderTop: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  borderBottom: 'none',
  height: 48,
  bgcolor: 'background.paper',
  verticalAlign: 'middle',
} as const;

function CustomRolesHeaderCell({
  children,
  showDivider = false,
  width,
}: {
  children?: React.ReactNode;
  showDivider?: boolean;
  width?: number | string;
}) {
  return (
    <TableCell sx={{ ...customRolesHeaderCellSx, width }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          height: 48,
          pl: 0,
          pr: '12px',
        }}
      >
        {showDivider && (
          <Box
            sx={{
              width: '1px',
              height: 23,
              bgcolor: 'greyscale.border',
              mx: '12px',
              flexShrink: 0,
            }}
          />
        )}
        {children && (
          <Typography
            component="span"
            sx={{
              fontWeight: 700,
              fontSize: 14,
              lineHeight: '22px',
              color: 'greyscale.body',
            }}
          >
            {children}
          </Typography>
        )}
      </Box>
    </TableCell>
  );
}

const rowActionIconButtonSx = {
  p: 0.5,
  color: 'text.secondary',
} as const;

function CustomRoleRowActions({
  canManageRoles,
  onEdit,
  onDelete,
}: {
  canManageRoles: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Box
      className={ROW_ACTIONS_CLASS}
      sx={{
        display: 'flex',
        gap: '4px',
        justifyContent: 'flex-end',
        alignItems: 'center',
        width: '100%',
      }}
    >
      <Tooltip title={canManageRoles ? 'Edit' : 'View'}>
        <IconButton
          size="small"
          onClick={onEdit}
          sx={{
            ...rowActionIconButtonSx,
            '&:hover': {
              color: 'primary.main',
              bgcolor: 'action.hover',
            },
          }}
        >
          <EditIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </Tooltip>
      {canManageRoles && (
        <Tooltip title="Delete">
          <IconButton
            size="small"
            onClick={onDelete}
            sx={{
              ...rowActionIconButtonSx,
              '&:hover': {
                color: 'error.main',
                bgcolor: 'action.hover',
              },
            }}
          >
            <DeleteIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function BuiltInRoleCard({
  role,
  onDetails,
}: {
  role: RoleRead;
  onDetails: () => void;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        p: 2,
        border: t => `1px solid ${t.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        transition: 'background 0.15s',
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <Box sx={{ width: 92, flexShrink: 0 }}>
        <Chip
          label={role.display_name}
          size="small"
          sx={{ ...getRoleChipSx(role), fontSize: 12, height: 24 }}
        />
      </Box>
      <Typography
        variant="body2"
        sx={{ flex: 1, color: 'text.primary', lineHeight: 1.5 }}
      >
        {role.description}
      </Typography>
      <Button
        size="small"
        onClick={onDetails}
        sx={{ textTransform: 'none', flexShrink: 0 }}
      >
        Details
      </Button>
    </Box>
  );
}

function PrivilegeRail() {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        py: 0.5,
        flexShrink: 0,
        width: 18,
      }}
    >
      <Typography
        sx={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'text.secondary',
          writingMode: 'vertical-rl',
          whiteSpace: 'nowrap',
          transform: 'rotate(180deg)',
        }}
      >
        Most access
      </Typography>
      <Box
        sx={{
          width: 4,
          flex: 1,
          borderRadius: BORDER_RADIUS.sm,
          background: t =>
            `linear-gradient(to bottom, ${t.palette.primary.main} 0%, ${t.palette.primary.light} 45%, ${t.palette.greyscale.border} 100%)`,
          my: 1,
        }}
      />
      <Typography
        sx={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'text.secondary',
          writingMode: 'vertical-rl',
          whiteSpace: 'nowrap',
        }}
      >
        Least access
      </Typography>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function RolesTab() {
  const { sessionToken } = useOrgSettings();
  const notifications = useNotifications();
  const { allowed: canReadRoles, loading: permsLoading } = useCanWithStatus(
    Capability.Role.READ
  );
  const canManageRoles = useCan(Capability.Role.MANAGE);
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<DrawerMode>('view');
  const [selectedRole, setSelectedRole] = useState<RoleRead | undefined>();
  const [roleToDelete, setRoleToDelete] = useState<RoleRead | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadRoles = useCallback(() => {
    fetchRoles(sessionToken)
      .then(data => {
        setRoles(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load roles');
        setLoading(false);
      });
  }, [sessionToken]);

  useEffect(() => {
    if (permsLoading || !canReadRoles) return;
    loadRoles();
  }, [loadRoles, permsLoading, canReadRoles]);

  const openDrawer = useCallback((mode: DrawerMode, role?: RoleRead) => {
    setDrawerMode(mode);
    setSelectedRole(role);
    setDrawerOpen(true);
  }, []);

  const handleSaved = useCallback((saved: RoleRead) => {
    setRoles(prev => {
      const idx = prev.findIndex(r => r.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [...prev, saved];
    });
  }, []);

  const handleDeleted = useCallback((roleId: string) => {
    setRoles(prev => prev.filter(r => r.id !== roleId));
  }, []);

  const handleDeleteConfirmed = useCallback(async () => {
    if (!roleToDelete) return;
    setDeleting(true);
    try {
      const client = new RbacClient(sessionToken);
      await client.deleteRole(roleToDelete.id);
      handleDeleted(roleToDelete.id);
      setRoleToDelete(null);
      notifications.show('Role deleted', { severity: 'success' });
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to delete role',
        { severity: 'error' }
      );
    } finally {
      setDeleting(false);
    }
  }, [roleToDelete, sessionToken, handleDeleted, notifications]);

  if (permsLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!canReadRoles) {
    return <AccessDenied resource="roles" />;
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Typography color="error" sx={{ p: 2 }}>
        {error}
      </Typography>
    );
  }

  const builtInRoles = roles
    .filter(r => r.is_built_in)
    .sort((a, b) => b.level - a.level);

  const customRoles = roles.filter(r => !r.is_built_in);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Built-in Roles */}
      <SectionCard
        title="Built-in Roles"
        subtitle="Five roles, ready to use. Permissions are fixed and cannot be changed."
      >
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'stretch' }}>
          <PrivilegeRail />
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              gap: 1.25,
            }}
          >
            {builtInRoles.map(role => (
              <BuiltInRoleCard
                key={role.id}
                role={role}
                onDetails={() => openDrawer('view', role)}
              />
            ))}
          </Box>
        </Box>
      </SectionCard>

      {/* Custom Roles */}
      <SectionCard
        title="Custom Roles"
        subtitle="Named roles for separation of duties. Common in regulated teams where built-in roles are not granular enough."
        actions={
          customRoles.length > 0 ? (
            <Can capability={Capability.Role.MANAGE}>
              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon sx={{ fontSize: 20 }} />}
                onClick={() => openDrawer('create')}
                sx={sectionEditButtonSx}
              >
                New role
              </Button>
            </Can>
          ) : undefined
        }
      >
        {customRoles.length === 0 ? (
          <EntityEmptyState
            icon={AdminPanelSettingsIcon}
            title="No custom roles yet"
            description="Create a custom role to define permissions that built-in roles do not cover."
            actionLabel={canManageRoles ? 'New role' : undefined}
            onAction={canManageRoles ? () => openDrawer('create') : undefined}
            embedded
          />
        ) : (
          <Box sx={sectionCardGridBleedSx}>
            <TableContainer
              sx={[
                customRolesTableSx,
                sectionCardGridTableInsetSx,
                sectionCardGridTableEdgeCellResetSx,
              ]}
            >
              <Table>
                <TableHead>
                  <TableRow>
                    <CustomRolesHeaderCell>Role</CustomRolesHeaderCell>
                    <CustomRolesHeaderCell showDivider width="34%">
                      Purpose
                    </CustomRolesHeaderCell>
                    <CustomRolesHeaderCell showDivider width={120}>
                      Members
                    </CustomRolesHeaderCell>
                    <CustomRolesHeaderCell showDivider width={88} />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {customRoles.map(role => (
                    <TableRow key={role.id} sx={{ height: 48 }}>
                      <TableCell sx={customRolesBodyCellSx}>
                        <Chip
                          label={role.display_name}
                          size="small"
                          sx={{ ...getRoleChipSx(role), fontSize: 12 }}
                        />
                      </TableCell>
                      <TableCell sx={customRolesBodyCellSx}>
                        {role.permissions.length} permissions
                      </TableCell>
                      <TableCell sx={customRolesBodyCellSx}>
                        {role.member_count}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ ...customRolesBodyCellSx, width: 88 }}
                      >
                        <CustomRoleRowActions
                          canManageRoles={canManageRoles}
                          onEdit={() =>
                            openDrawer(canManageRoles ? 'edit' : 'view', role)
                          }
                          onDelete={() => setRoleToDelete(role)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </SectionCard>

      {/* Role editor drawer */}
      <RoleEditorDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        mode={drawerMode}
        role={selectedRole}
        roles={roles}
        onSaved={handleSaved}
        onDeleted={handleDeleted}
      />

      {roleToDelete && (
        <DeleteModal
          open
          onClose={() => setRoleToDelete(null)}
          onConfirm={handleDeleteConfirmed}
          isLoading={deleting}
          title="Delete role"
          itemName={roleToDelete.display_name}
          itemType="role"
          warningMessage={
            roleToDelete.member_count > 0
              ? `${roleToDelete.member_count} member${roleToDelete.member_count === 1 ? '' : 's'} currently ${
                  roleToDelete.member_count === 1 ? 'holds' : 'hold'
                } this role. Deleting it removes the role from them — organization-level holders lose its access, and project-level holders revert to their inherited organization role.`
              : undefined
          }
        />
      )}
    </Box>
  );
}
