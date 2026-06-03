'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Avatar,
  Box,
  Button,
  CircularProgress,
  IconButton,
  TextField,
  Typography,
} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
} from '@mui/x-data-grid';
import PersonAddOutlinedIcon from '@mui/icons-material/PersonAddOutlined';
import PersonIcon from '@mui/icons-material/Person';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UsersClient } from '@/utils/api-client/users-client';
import {
  ProjectMember,
  ProjectMemberUser,
} from '@/utils/api-client/interfaces/project';
import { User } from '@/utils/api-client/interfaces/user';
import { DeleteIcon } from '@/components/icons';

interface ProjectMembersProps {
  projectId: string;
  sessionToken: string;
  /** ID of the project owner — prevents removing them. */
  ownerId?: string;
}

function getMemberDisplayName(user: ProjectMemberUser | null | undefined): string {
  if (!user) return 'Unknown';
  if (user.name) return user.name;
  const parts = [user.given_name, user.family_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : (user.email ?? 'Unknown');
}

function getUserDisplayName(user: User): string {
  if (user.name) return user.name;
  const parts = [user.given_name, user.family_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : user.email;
}

export default function ProjectMembers({
  projectId,
  sessionToken,
  ownerId,
}: ProjectMembersProps) {
  const notifications = useNotifications();

  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });

  const [orgUsers, setOrgUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRole] = useState<string>('member');
  const [adding, setAdding] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<ProjectMember | null>(null);
  const [removing, setRemoving] = useState(false);

  const fetchMembers = useCallback(async () => {
    setMembersLoading(true);
    setMembersError(null);
    try {
      const factory = new ApiClientFactory(sessionToken);
      const data = await factory.getProjectsClient().getProjectMembers(projectId);
      setMembers(data);
    } catch {
      setMembersError('Failed to load project members.');
    } finally {
      setMembersLoading(false);
    }
  }, [projectId, sessionToken]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  // Load non-member org users for the add-member autocomplete.
  // Waits for the members list to finish loading so we can pass an OData
  // exclusion filter — only users not already in the project are fetched.
  useEffect(() => {
    if (membersLoading) return;

    let cancelled = false;
    async function load() {
      setUsersLoading(true);
      setUsersError(null);
      try {
        // Pass '' as projectId so getHeaders() skips X-Project-Id entirely.
        // Users are org-scoped; the header would trigger project membership
        // validation that is irrelevant here.
        const usersClient = new UsersClient(sessionToken, undefined, '');

        // Build an OData exclusion filter so the API only returns users who
        // are not yet project members.
        const memberIds = members.map(m => m.user_id);
        const $filter =
          memberIds.length > 0
            ? memberIds.map(id => `id ne '${id}'`).join(' and ')
            : undefined;

        const result = await usersClient.getUsers({ limit: 100, $filter });
        if (!cancelled) setOrgUsers(result.data);
      } catch {
        if (!cancelled) setUsersError('Failed to load organisation members.');
      } finally {
        if (!cancelled) setUsersLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [sessionToken, members, membersLoading]);

  // addableUsers is now already pre-filtered by the API; keep the client-side
  // guard as a safety net against any race between the two fetches.
  const memberUserIds = new Set(members.map(m => m.user_id));
  const addableUsers = orgUsers.filter(u => !memberUserIds.has(u.id));

  const handleAdd = async () => {
    if (!selectedUser) return;
    setAdding(true);
    try {
      const factory = new ApiClientFactory(sessionToken);
      await factory.getProjectsClient().addProjectMember(projectId, {
        user_id: selectedUser.id,
        role: selectedRole,
      });
      notifications.show(
        `${getUserDisplayName(selectedUser)} added to the project.`,
        { severity: 'success' }
      );
      setSelectedUser(null);
      await fetchMembers();
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to add member.',
        { severity: 'error' }
      );
    } finally {
      setAdding(false);
    }
  };

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
      await fetchMembers();
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
              sx={{ width: 32, height: 32, flexShrink: 0 }}
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
        <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
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
        if (ownerId && member.user_id === ownerId) return null;
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
      {/* Add member row */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 3, alignItems: 'center' }}>
        <Autocomplete<User>
          options={addableUsers}
          loading={usersLoading}
          value={selectedUser}
          onChange={(_e, value) => setSelectedUser(value)}
          getOptionLabel={getUserDisplayName}
          isOptionEqualToValue={(opt, val) => opt.id === val.id}
          noOptionsText={
            usersError
              ? 'Failed to load members'
              : addableUsers.length === 0 && !usersLoading
                ? 'All organisation members are already in this project'
                : 'No members found'
          }
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Search org members to add…"
              size="small"
              slotProps={{
                input: {
                  ...params.InputProps,
                  endAdornment: (
                    <>
                      {usersLoading && <CircularProgress size={16} />}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                },
              }}
            />
          )}
          sx={{ width: 320 }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={
            adding ? (
              <CircularProgress size={16} color="inherit" />
            ) : (
              <PersonAddOutlinedIcon />
            )
          }
          disabled={!selectedUser || adding}
          onClick={handleAdd}
        >
          Add as member
        </Button>
      </Box>

      {usersError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {usersError}
        </Alert>
      )}

      {membersError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {membersError}
        </Alert>
      )}

      <BaseDataGrid
        rows={members}
        columns={columns}
        loading={membersLoading}
        getRowId={row => `${(row as ProjectMember).project_id}-${(row as ProjectMember).user_id}`}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        serverSidePagination={false}
        totalRows={members.length}
        pageSizeOptions={[10, 25, 50]}
        disableRowSelectionOnClick
        disablePaperWrapper
      />

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
