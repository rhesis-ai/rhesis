'use client';

import * as React from 'react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Avatar, Box, Typography } from '@mui/material';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import PersonIcon from '@mui/icons-material/Person';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import { DeleteIcon } from '@/components/icons';
import { useSession } from 'next-auth/react';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import {
  EMPTY_TEAM_FILTERS,
  countActiveTeamFilters,
  teamList,
  type TeamFilters,
} from './list';
import TeamFilterDrawer from './TeamFilterDrawer';
import MemberAccessDrawer from './MemberAccessDrawer';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useFeature } from '@/contexts/FeaturesContext';
import { FeatureName } from '@/constants/features';
import { getMemberRoleExtensions } from '@/lib/extension-registries';
import { getMemberJoinStatus } from '@/utils/member-join-status';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { useDeleteUser } from '@/hooks/useUsers';

interface TeamMembersGridProps {
  refreshTrigger?: number;
  onTotalCountChange?: (count: number) => void;
  /** Server-fetched first page -- when present, skips the initial client fetch. */
  initialData?: User[];
  initialTotalCount?: number;
}

function getDisplayName(user: User): string {
  if (user.name) return user.name;
  if (user.given_name || user.family_name) {
    return `${user.given_name || ''} ${user.family_name || ''}`.trim();
  }
  return user.email;
}

function toFilters(state: EntityGridFilterState<TeamFilters>) {
  return {
    search: state.search,
    email: state.drawer.email,
    name: state.drawer.name,
    memberStatus: state.drawer.memberStatus,
    accountStatus:
      state.drawer.accountStatus === null
        ? ''
        : String(state.drawer.accountStatus),
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TeamFilters> = {
  empty: EMPTY_TEAM_FILTERS,
  countActive: countActiveTeamFilters,
  render: props => (
    <TeamFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

export default function TeamMembersGrid({
  refreshTrigger,
  onTotalCountChange,
  initialData,
  initialTotalCount,
}: TeamMembersGridProps) {
  const { data: session, status } = useSession();
  const canDeleteMember = useCan(Capability.Member.DELETE);
  const canManageMembers = useCan(Capability.Member.MANAGE);
  const notifications = useNotifications();

  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [accessDrawerOpen, setAccessDrawerOpen] = useState(false);
  const [accessDrawerUser, setAccessDrawerUser] = useState<User | null>(null);

  const onTotalCountChangeRef = React.useRef(onTotalCountChange);
  onTotalCountChangeRef.current = onTotalCountChange;
  const handleDataChange = useCallback((_data: User[], totalCount: number) => {
    onTotalCountChangeRef.current?.(totalCount);
  }, []);

  const deleteUser = useDeleteUser();

  const rbacEnabled = useFeature(FeatureName.RBAC);
  const { OrgRoleCell: RawOrgRoleCell, prewarmCaches } =
    getMemberRoleExtensions();
  const OrgRoleCell = rbacEnabled ? RawOrgRoleCell : undefined;

  useEffect(() => {
    if (rbacEnabled && isAuthenticated(status)) {
      prewarmCaches?.({ canManageRoles: canManageMembers });
    }
  }, [rbacEnabled, prewarmCaches, canManageMembers, status]);

  const currentUserId = session?.user?.id;

  const makeConfirmDelete = useCallback(
    (refresh: () => void) => async () => {
      if (!userToDelete || !isAuthenticated(status)) {
        return;
      }

      try {
        setDeleting(true);

        await deleteUser(userToDelete.id);

        notifications.show(
          `Successfully removed ${getDisplayName(userToDelete)} from the organization.`,
          { severity: 'success' }
        );

        refresh();
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error
            ? error.message
            : 'Failed to remove user from organization. Please try again.';

        notifications.show(errorMessage, {
          severity: 'error',
        });
      } finally {
        setDeleting(false);
        setUserToDelete(null);
      }
    },
    [userToDelete, status, deleteUser, notifications]
  );

  const handleCancelDelete = useCallback(() => setUserToDelete(null), []);

  const handleRowClick = useCallback((params: GridRowParams) => {
    setAccessDrawerUser(params.row as User);
    setAccessDrawerOpen(true);
  }, []);

  // Removal is org-specific ("remove from organization", name in the confirm
  // text, self-removal blocked), so it stays a grid-local extra action rather
  // than a descriptor delete spec.
  const extraRowActions = useMemo(
    () => [
      {
        key: 'remove',
        icon: DeleteIcon,
        tooltip: 'Remove from organization',
        onClick: (_id: string, row: Record<string, unknown>) =>
          setUserToDelete(row as unknown as User),
        can: (row: Record<string, unknown>) =>
          canDeleteMember && String(row.id) !== currentUserId,
        hoverColor: 'error.main' as const,
      },
    ],
    [canDeleteMember, currentUserId]
  );

  const columns: GridColDef[] = useMemo(() => {
    const cols: GridColDef[] = [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1.2,
        minWidth: 180,
        sortable: false,
        valueGetter: (_, row) => getDisplayName(row as User),
        renderCell: params => {
          const user = params.row as User;
          const memberStatus = getMemberJoinStatus(user);
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                minWidth: 0,
              }}
            >
              <Avatar
                src={user.picture || undefined}
                sx={{
                  width: 32,
                  height: 32,
                  flexShrink: 0,
                  bgcolor:
                    memberStatus === 'active' ? 'primary.main' : 'grey.400',
                }}
              >
                {user.picture ? null : <PersonIcon fontSize="small" />}
              </Avatar>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 500,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {params.value}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'email',
        headerName: 'Email',
        flex: 1.2,
        minWidth: 200,
        sortable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {params.value}
          </Typography>
        ),
      },
    ];

    if (OrgRoleCell) {
      cols.push({
        field: 'orgRole',
        headerName: 'Role',
        flex: 1.5,
        sortable: false,
        renderCell: params => (
          <Box
            onClick={e => e.stopPropagation()}
            onMouseDown={e => e.stopPropagation()}
            sx={{ width: '100%' }}
          >
            <OrgRoleCell userId={String(params.id)} />
          </Box>
        ),
      });
    }

    cols.push({
      field: 'status',
      headerName: 'Status',
      flex: 1.2,
      sortable: false,
      valueGetter: (_, row) =>
        getMemberJoinStatus(row as User) === 'active' ? 'Active' : 'Invited',
    });

    return cols;
  }, [OrgRoleCell]);

  return (
    <EntityGrid<User, typeof teamList.filters, TeamFilters>
      descriptor={teamList}
      columns={columns}
      toFilters={toFilters}
      emptyState={null}
      embedded
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      onDataChange={handleDataChange}
      searchPlaceholder="Search team members…"
      drawer={drawerAdapter}
      onRowClick={handleRowClick}
      editAction={false}
      extraRowActions={extraRowActions}
      rowActionsWidth={56}
      showGridButtons={false}
      persistState={false}
      serverSort={false}
      pageSizeOptions={[10, 25, 50]}
      sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
      renderSelectionExtras={ctx => (
        <>
          <MemberAccessDrawer
            open={accessDrawerOpen}
            onClose={() => setAccessDrawerOpen(false)}
            user={accessDrawerUser}
          />
          <DeleteModal
            open={userToDelete !== null}
            onClose={handleCancelDelete}
            onConfirm={makeConfirmDelete(ctx.refresh)}
            isLoading={deleting}
            title="Remove from Organization"
            message={`Are you sure you want to remove ${userToDelete ? getDisplayName(userToDelete) : ''} from the organization?\n\nThey will lose access to all organization resources but can be re-invited in the future. Their contributions to projects and tests will remain intact.`}
            itemType="user"
            confirmButtonText={
              deleting ? 'Removing...' : 'Remove from Organization'
            }
          />
        </>
      )}
    />
  );
}
