import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Chip,
  Avatar,
  Typography,
  Alert,
  IconButton,
} from '@mui/material';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import PersonIcon from '@mui/icons-material/Person';
import { DeleteIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';

interface TeamMembersGridProps {
  refreshTrigger?: number; // Used to trigger refresh when new invites are sent
}

export default function TeamMembersGrid({
  refreshTrigger,
}: TeamMembersGridProps) {
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchUsers = useCallback(
    async (skip = 0, limit = 25) => {
      if (!session?.session_token) {
        setError('Session expired. Please refresh the page.');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const clientFactory = new ApiClientFactory(session.session_token);
        const usersClient = clientFactory.getUsersClient();

        // Fetch users for the current organization
        const response = await usersClient.getUsers({
          skip,
          limit,
        });

        setUsers(response.data || []);
        setTotalCount(response.total || 0);
      } catch (error) {
        setError('Failed to load team members. Please try again.');
      } finally {
        setLoading(false);
      }
    },
    [session?.session_token]
  );

  // Initial load
  useEffect(() => {
    fetchUsers(0, paginationModel.pageSize);
  }, [fetchUsers, paginationModel.pageSize]);

  // Refresh when new invites are sent
  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      fetchUsers(
        paginationModel.page * paginationModel.pageSize,
        paginationModel.pageSize
      );
    }
  }, [refreshTrigger, fetchUsers, paginationModel]);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
      const skip = newModel.page * newModel.pageSize;
      fetchUsers(skip, newModel.pageSize);
    },
    [fetchUsers]
  );

  // Determine if user is active (has logged in) or just invited
  const getUserStatus = (user: User) => {
    // Active users have name, given_name, family_name, or auth0_id populated
    const hasProfileData =
      user.name || user.given_name || user.family_name || user.auth0_id;
    return hasProfileData ? 'active' : 'invited';
  };

  const getDisplayName = (user: User) => {
    if (user.name) return user.name;
    if (user.given_name || user.family_name) {
      return `${user.given_name || ''} ${user.family_name || ''}`.trim();
    }
    return user.email;
  };

  const handleDeleteUser = (user: User) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!userToDelete || !session?.session_token) {
      return;
    }

    try {
      setDeleting(true);

      const clientFactory = new ApiClientFactory(session.session_token);
      const usersClient = clientFactory.getUsersClient();

      await usersClient.deleteUser(userToDelete.id);

      notifications.show(
        `Successfully removed ${getDisplayName(userToDelete)} from the organization.`,
        { severity: 'success' }
      );

      // Refresh the users list
      const skip = paginationModel.page * paginationModel.pageSize;
      fetchUsers(skip, paginationModel.pageSize);
    } catch (error: any) {
      // Handle specific error cases
      const errorMessage =
        error?.message ||
        'Failed to remove user from organization. Please try again.';

      notifications.show(errorMessage, {
        severity: 'error',
      });
    } finally {
      setDeleting(false);
      setDeleteDialogOpen(false);
      setUserToDelete(null);
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setUserToDelete(null);
  };

  const columns: GridColDef[] = [
    {
      field: 'avatar',
      headerName: '',
      width: 60,
      sortable: false,
      renderCell: params => {
        const user = params.row as User;
        const status = getUserStatus(user);

        return (
          <Avatar
            src={user.picture || undefined}
            sx={{
              width: 32,
              height: 32,
              bgcolor: status === 'active' ? 'primary.main' : 'grey.400',
            }}
          >
            {user.picture ? null : <PersonIcon fontSize="small" />}
          </Avatar>
        );
      },
    },
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 200,
      renderCell: params => {
        const user = params.row as User;
        const displayName = getDisplayName(user);

        return (
          <Typography variant="body2" fontWeight="medium">
            {displayName}
          </Typography>
        );
      },
    },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1,
      minWidth: 250,
      renderCell: params => {
        const user = params.row as User;
        return <Typography variant="body2">{user.email}</Typography>;
      },
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: params => {
        const user = params.row as User;
        const status = getUserStatus(user);

        return (
          <Chip
            label={status === 'active' ? 'Active' : 'Invited'}
            size="small"
            color={status === 'active' ? 'success' : 'warning'}
            variant="outlined"
          />
        );
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: params => {
        const user = params.row as User;
        const currentUserId = session?.user?.id;

        // Don't show actions for current user
        if (user.id === currentUserId) {
          return null;
        }

        return (
          <IconButton
            onClick={() => handleDeleteUser(user)}
            size="small"
            title="Remove from organization"
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        );
      },
    },
  ];

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Team Members ({totalCount})
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage your organization&apos;s team members and their access
        </Typography>
      </Box>

      <BaseDataGrid
        rows={users}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        disableRowSelectionOnClick
        enableQuickFilter={true}
        disablePaperWrapper={true}
        sx={{
          '& .MuiDataGrid-row': {
            '&:hover': {
              backgroundColor: 'action.hover',
            },
          },
        }}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteModal
        open={deleteDialogOpen}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        isLoading={deleting}
        title="Remove from Organization"
        message={`Are you sure you want to remove ${userToDelete ? getDisplayName(userToDelete) : ''} from the organization?\n\nThey will lose access to all organization resources but can be re-invited in the future. Their contributions to projects and tests will remain intact.`}
        itemType="user"
        confirmButtonText={
          deleting ? 'Removing...' : 'Remove from Organization'
        }
      />
    </Box>
  );
}
