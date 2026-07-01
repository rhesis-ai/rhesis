'use client';

import * as React from 'react';
import { useCallback, useState } from 'react';
import { Alert, Avatar, Box, IconButton, Typography } from '@mui/material';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import PersonIcon from '@mui/icons-material/Person';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ProjectMember,
  ProjectMemberUser,
} from '@/utils/api-client/interfaces/project';
import { DeleteIcon, PersonAddIcon } from '@/components/icons';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { projectKeys } from '@/constants/query-keys';

interface ProjectMembersProps {
  projectId: string;
  sessionToken: string;
  /** ID of the project owner — prevents removing them. */
  ownerId?: string;
  refreshKey?: number;
  onMembersLoaded?: (members: ProjectMember[]) => void;
}

function getMemberDisplayName(
  user: ProjectMemberUser | null | undefined
): string {
  if (!user) return 'Unknown';
  if (user.name) return user.name;
  const parts = [user.given_name, user.family_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : (user.email ?? 'Unknown');
}

export default function ProjectMembers({
  projectId,
  sessionToken,
  ownerId,
  refreshKey = 0,
  onMembersLoaded,
}: ProjectMembersProps) {
  const notifications = useNotifications();
  const canManageMembers = useCan(Capability.ProjectMember.MANAGE);
  const queryClient = useQueryClient();

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<ProjectMember | null>(
    null
  );
  const [removing, setRemoving] = useState(false);

  const membersQueryKey = [
    ...projectKeys.detail(projectId),
    'members',
  ] as const;

  const {
    data: members = [],
    isLoading: membersLoading,
    error: membersQueryError,
  } = useQuery({
    queryKey: membersQueryKey,
    queryFn: async () => {
      const data = await new ApiClientFactory(sessionToken)
        .getProjectsClient()
        .getProjectMembers(projectId);
      onMembersLoaded?.(data);
      return data;
    },
    enabled: !!sessionToken && !!projectId,
  });

  const membersError = membersQueryError
    ? 'Failed to load project members.'
    : null;

  // Re-fetch when refreshKey increments
  const prevRefreshKey = React.useRef(refreshKey);
  React.useEffect(() => {
    if (refreshKey !== prevRefreshKey.current) {
      prevRefreshKey.current = refreshKey;
      queryClient.invalidateQueries({ queryKey: membersQueryKey });
    }
  }, [refreshKey, queryClient, membersQueryKey]);

  const handleRemoveClick = (member: ProjectMember) => {
    setMemberToRemove(member);
    setDeleteOpen(true);
  };

  const handleRemoveConfirm = async () => {
    if (!memberToRemove) return;
    setRemoving(true);
    try {
      const factory = new ApiClientFactory(sessionToken);
      await factory
        .getProjectsClient()
        .removeProjectMember(projectId, memberToRemove.user_id);
      notifications.show('Member removed from the project.', {
        severity: 'success',
      });
      queryClient.invalidateQueries({ queryKey: membersQueryKey });
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to remove member.',
        { severity: 'error' }
      );
    } finally {
      setRemoving(false);
      setDeleteOpen(false);
      setMemberToRemove(null);
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 200,
      valueGetter: (_value, row) =>
        getMemberDisplayName((row as ProjectMember).user),
      renderCell: params => {
        const member = params.row as ProjectMember;
        const name = getMemberDisplayName(member.user);
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Avatar
              src={member.user?.picture ?? undefined}
              sx={{
                width: theme => theme.spacing(4),
                height: theme => theme.spacing(4),
                flexShrink: 0,
              }}
            >
              {!member.user?.picture && <PersonIcon fontSize="small" />}
            </Avatar>
            <Typography variant="body2" fontWeight={500}>
              {name}
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1,
      minWidth: 200,
      valueGetter: (_value, row) => (row as ProjectMember).user?.email ?? '',
      renderCell: params => (
        <Typography variant="body2" color="text.secondary">
          {(params.row as ProjectMember).user?.email ?? ''}
        </Typography>
      ),
    },
    {
      field: 'role',
      headerName: 'Role',
      width: 120,
      sortable: false,
      filterable: false,
      valueGetter: (_value, row) => (row as ProjectMember).role ?? 'member',
      renderCell: params => (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ textTransform: 'capitalize' }}
        >
          {(params.row as ProjectMember).role ?? 'member'}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: 56,
      sortable: false,
      filterable: false,
      renderCell: params => {
        const member = params.row as ProjectMember;
        // Never show delete for the project owner, and only for users with manage capability.
        if ((ownerId && member.user_id === ownerId) || !canManageMembers) {
          return null;
        }
        return (
          <IconButton
            size="small"
            title="Remove from project"
            onClick={e => {
              e.stopPropagation();
              handleRemoveClick(member);
            }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        );
      },
    },
  ];

  return (
    <Box>
      {membersError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {membersError}
        </Alert>
      )}

      {!membersLoading && members.length === 0 ? (
        <SectionEmptyState
          icon={PersonAddIcon}
          title="No members yet"
          description="Add organisation members to grant them access to this project."
        />
      ) : (
        <BaseDataGrid
          rows={members}
          columns={columns}
          loading={membersLoading}
          getRowId={row =>
            `${(row as ProjectMember).project_id}-${(row as ProjectMember).user_id}`
          }
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          serverSidePagination={false}
          totalRows={members.length}
          pageSizeOptions={[10, 25, 50]}
          disableRowSelectionOnClick
          disablePaperWrapper
        />
      )}

      <DeleteModal
        open={deleteOpen}
        onClose={() => {
          setDeleteOpen(false);
          setMemberToRemove(null);
        }}
        onConfirm={handleRemoveConfirm}
        isLoading={removing}
        title="Remove from project"
        message={`Remove ${getMemberDisplayName(memberToRemove?.user)} from this project? They will lose access to project-scoped data.`}
        itemType="user"
        confirmButtonText={removing ? 'Removing…' : 'Remove from project'}
      />
    </Box>
  );
}
