'use client';

import * as React from 'react';
import { useState, useEffect, useCallback, useContext, useMemo } from 'react';
import { Box, Avatar, Typography, Alert, IconButton } from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { SearchPill } from '@/components/common/SearchPill';
import { FilterButton } from '@/components/common/FilterButton';
import GridBadge from '@/components/common/GridBadge';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import PersonIcon from '@mui/icons-material/Person';
import { DeleteIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { GREYSCALE } from '@/styles/theme';
import {
  combineTeamFiltersToOData,
  EMPTY_TEAM_FILTERS,
  hasActiveTeamFilters,
  type TeamFilters,
} from '@/utils/odata-filter';
import TeamFilterDrawer from './TeamFilterDrawer';

interface TeamToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
}

const TeamToolbarContext = React.createContext<TeamToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

function TeamUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(TeamToolbarContext);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1,
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.tableBorder
              : GREYSCALE.dark.tableBorder
          }`,
        bgcolor: theme =>
          theme.palette.mode === 'light'
            ? GREYSCALE.light.tableSurface
            : GREYSCALE.dark.tableSurface,
        minHeight: 52,
      }}
    >
      <FilterButton
        onClick={openFilterDrawer}
        hasActiveFilters={hasActiveDrawerFilters}
      />

      <SearchPill
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Search team members…"
        width={240}
      />

      <Box sx={{ flex: 1 }} />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <GridToolbarColumnsButton />
        <GridToolbarDensitySelector />
        <GridToolbarExport />
      </Box>
    </Box>
  );
}

interface TeamMembersGridProps {
  refreshTrigger?: number;
  onTotalCountChange?: (count: number) => void;
}

function getUserStatus(user: User): 'active' | 'invited' {
  const hasProfileData =
    user.name || user.given_name || user.family_name || user.auth0_id;
  return hasProfileData ? 'active' : 'invited';
}

function getDisplayName(user: User): string {
  if (user.name) return user.name;
  if (user.given_name || user.family_name) {
    return `${user.given_name || ''} ${user.family_name || ''}`.trim();
  }
  return user.email;
}

export default function TeamMembersGrid({
  refreshTrigger,
  onTotalCountChange,
}: TeamMembersGridProps) {
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] =
    useState<TeamFilters>(EMPTY_TEAM_FILTERS);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
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
        const response = await usersClient.getUsers({
          skip,
          limit: Math.min(limit, 100),
          $filter: combineTeamFiltersToOData(searchQuery, drawerFilters),
        });

        setUsers(response.data || []);
        const total = response.total || 0;
        setTotalCount(total);
        onTotalCountChange?.(total);
      } catch (_error) {
        setError('Failed to load team members. Please try again.');
      } finally {
        setLoading(false);
      }
    },
    [session?.session_token, onTotalCountChange, searchQuery, drawerFilters]
  );

  useEffect(() => {
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [searchQuery, drawerFilters]);

  useEffect(() => {
    const skip = paginationModel.page * paginationModel.pageSize;
    fetchUsers(skip, paginationModel.pageSize);
  }, [
    fetchUsers,
    paginationModel.page,
    paginationModel.pageSize,
    refreshTrigger,
  ]);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const handleDeleteUser = useCallback((user: User) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  }, []);

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

      const skip = paginationModel.page * paginationModel.pageSize;
      await fetchUsers(skip, paginationModel.pageSize);
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
      setDeleteDialogOpen(false);
      setUserToDelete(null);
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setUserToDelete(null);
  };

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1,
        minWidth: 220,
        valueGetter: (_value, row) => getDisplayName(row as User),
        renderCell: params => {
          const user = params.row as User;
          const status = getUserStatus(user);
          const displayName = getDisplayName(user);

          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                width: '100%',
                minWidth: 0,
              }}
            >
              <Avatar
                src={user.picture || undefined}
                sx={{
                  width: 32,
                  height: 32,
                  flexShrink: 0,
                  bgcolor: status === 'active' ? 'primary.main' : 'grey.400',
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
                {displayName}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'email',
        headerName: 'Email',
        flex: 1,
        minWidth: 220,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {(params.row as User).email}
          </Typography>
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        sortable: true,
        valueGetter: (_value, row) => getUserStatus(row as User),
        renderCell: params => {
          const status = getUserStatus(params.row as User);
          return (
            <GridBadge label={status === 'active' ? 'Active' : 'Invited'} />
          );
        },
      },
      {
        field: 'actions',
        headerName: '',
        width: 56,
        sortable: false,
        filterable: false,
        renderCell: params => {
          const user = params.row as User;
          const currentUserId = session?.user?.id;

          if (user.id === currentUserId) {
            return null;
          }

          return (
            <IconButton
              onClick={e => {
                e.stopPropagation();
                handleDeleteUser(user);
              }}
              size="small"
              title="Remove from organization"
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          );
        },
      },
    ],
    [session?.user?.id, handleDeleteUser]
  );

  return (
    <TeamToolbarContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        openFilterDrawer: () => setFilterDrawerOpen(true),
        hasActiveDrawerFilters: hasActiveTeamFilters(drawerFilters),
      }}
    >
      {error && (
        <Alert severity="error" sx={{ m: 2 }}>
          {error}
        </Alert>
      )}

      <BaseDataGrid
        rows={users}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50, 100]}
        disableRowSelectionOnClick
        disablePaperWrapper={true}
        showToolbar={true}
        toolbarSlot={TeamUnifiedToolbar}
        persistState
        storageKey="team-members-grid"
      />

      <TeamFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={f => {
          setDrawerFilters(f);
          setFilterDrawerOpen(false);
        }}
      />

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
    </TeamToolbarContext.Provider>
  );
}
