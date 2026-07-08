'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import {
  Alert,
  Avatar,
  Box,
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
import PersonIcon from '@mui/icons-material/Person';
import GridToolbar, {
  linkedGridToolbarSx,
  sectionCardGridTableEdgeCellResetSx,
  sectionCardGridTableInsetSx,
} from '@/components/common/GridToolbar';
import {
  ROW_ACTIONS_CLASS,
} from '@/components/common/createRowActionsColumn';
import {
  SectionOverviewHeaderCell,
  SectionOverviewPagination,
  sectionOverviewBodyCellSx,
  sectionOverviewRowActionIconButtonSx,
  sectionOverviewTableSx,
} from '@/components/common/SectionOverviewTable';
import { DeleteIcon } from '@/components/icons';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import {
  combineTeamFiltersToOData,
  EMPTY_TEAM_FILTERS,
  hasActiveTeamFilters,
  countActiveTeamFilters,
  type TeamFilters,
} from '@/utils/odata-filter';
import TeamFilterDrawer from './TeamFilterDrawer';
import MemberAccessDrawer from './MemberAccessDrawer';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { getMemberRoleExtensions } from '@/lib/extension-registries';

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
  const canDeleteMember = useCan(Capability.Member.DELETE);
  const canManageMembers = useCan(Capability.Member.MANAGE);
  const notifications = useNotifications();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] =
    useState<TeamFilters>(EMPTY_TEAM_FILTERS);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [accessDrawerOpen, setAccessDrawerOpen] = useState(false);
  const [accessDrawerUser, setAccessDrawerUser] = useState<User | null>(null);

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
    setPage(0);
  }, [searchQuery, drawerFilters]);

  useEffect(() => {
    const skip = page * pageSize;
    fetchUsers(skip, pageSize);
  }, [fetchUsers, page, pageSize, refreshTrigger]);

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

      const skip = page * pageSize;
      await fetchUsers(skip, pageSize);
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

  const handleRowClick = useCallback((user: User) => {
    setAccessDrawerUser(user);
    setAccessDrawerOpen(true);
  }, []);

  const { OrgRoleCell, prewarmCaches } = getMemberRoleExtensions();
  const sessionToken = session?.session_token ?? '';

  useEffect(() => {
    if (sessionToken) {
      prewarmCaches?.(sessionToken, { canManageRoles: canManageMembers });
    }
  }, [sessionToken, prewarmCaches, canManageMembers]);

  const showRoleColumn = Boolean(OrgRoleCell);
  const currentUserId = session?.user?.id;

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search team members…"
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveTeamFilters(drawerFilters)}
        activeFilterCount={countActiveTeamFilters(drawerFilters)}
        sx={linkedGridToolbarSx}
      />

      <TableContainer
        sx={[
          sectionOverviewTableSx,
          sectionCardGridTableInsetSx,
          sectionCardGridTableEdgeCellResetSx,
        ]}
      >
        <Table>
          <TableHead>
            <TableRow>
              <SectionOverviewHeaderCell>Name</SectionOverviewHeaderCell>
              <SectionOverviewHeaderCell showDivider>
                Email
              </SectionOverviewHeaderCell>
              {showRoleColumn && (
                <SectionOverviewHeaderCell showDivider width={150}>
                  Role
                </SectionOverviewHeaderCell>
              )}
              <SectionOverviewHeaderCell showDivider width={120}>
                Status
              </SectionOverviewHeaderCell>
              {canDeleteMember && (
                <SectionOverviewHeaderCell showDivider width={56} />
              )}
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell
                  colSpan={showRoleColumn ? (canDeleteMember ? 5 : 4) : canDeleteMember ? 4 : 3}
                  sx={{ ...sectionOverviewBodyCellSx, borderTop: 'none' }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'center',
                      py: 4,
                    }}
                  >
                    <CircularProgress size={24} />
                  </Box>
                </TableCell>
              </TableRow>
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={showRoleColumn ? (canDeleteMember ? 5 : 4) : canDeleteMember ? 4 : 3}
                  sx={{ ...sectionOverviewBodyCellSx, borderTop: 'none' }}
                >
                  <Typography variant="body2" color="text.secondary">
                    No team members match your search.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              users.map(user => {
                const status = getUserStatus(user);
                const displayName = getDisplayName(user);

                return (
                  <TableRow
                    key={user.id}
                    hover
                    onClick={() => handleRowClick(user)}
                    sx={{ height: 48, cursor: 'pointer' }}
                  >
                    <TableCell sx={sectionOverviewBodyCellSx}>
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
                              status === 'active' ? 'primary.main' : 'grey.400',
                          }}
                        >
                          {user.picture ? null : (
                            <PersonIcon fontSize="small" />
                          )}
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
                    </TableCell>
                    <TableCell sx={sectionOverviewBodyCellSx}>
                      <Typography variant="body2" color="text.secondary">
                        {user.email}
                      </Typography>
                    </TableCell>
                    {showRoleColumn && OrgRoleCell && (
                      <TableCell
                        sx={sectionOverviewBodyCellSx}
                        data-field="orgRole"
                        onClick={e => e.stopPropagation()}
                        onMouseDown={e => e.stopPropagation()}
                      >
                        <OrgRoleCell
                          userId={user.id}
                          sessionToken={sessionToken}
                        />
                      </TableCell>
                    )}
                    <TableCell sx={sectionOverviewBodyCellSx}>
                      {status === 'active' ? 'Active' : 'Invited'}
                    </TableCell>
                    {canDeleteMember && (
                      <TableCell
                        align="right"
                        sx={{ ...sectionOverviewBodyCellSx, width: 56 }}
                      >
                        {user.id !== currentUserId && (
                          <Box
                            className={ROW_ACTIONS_CLASS}
                            sx={{
                              display: 'flex',
                              justifyContent: 'flex-end',
                              width: '100%',
                            }}
                          >
                            <Tooltip title="Remove from organization">
                              <IconButton
                                size="small"
                                onClick={e => {
                                  e.stopPropagation();
                                  handleDeleteUser(user);
                                }}
                                sx={{
                                  ...sectionOverviewRowActionIconButtonSx,
                                  '&:hover': {
                                    color: 'error.main',
                                    bgcolor: 'action.hover',
                                  },
                                }}
                              >
                                <DeleteIcon sx={{ fontSize: 18 }} />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <SectionOverviewPagination
        page={page}
        pageSize={pageSize}
        totalRows={totalCount}
        onPageChange={setPage}
        onPageSizeChange={newSize => {
          setPageSize(newSize);
          setPage(0);
        }}
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

      <MemberAccessDrawer
        open={accessDrawerOpen}
        onClose={() => setAccessDrawerOpen(false)}
        user={accessDrawerUser}
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
    </>
  );
}
