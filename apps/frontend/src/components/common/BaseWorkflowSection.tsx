'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  Avatar,
  Autocomplete,
  TextField,
  MenuItem,
} from '@mui/material';
import {
  UserReference,
  PriorityLevel,
} from '@/utils/api-client/interfaces/tests';
import { Status } from '@/utils/api-client/interfaces/status';
import PersonIcon from '@mui/icons-material/Person';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

interface BaseWorkflowSectionProps {
  title?: string;
  status?: string;
  priority?: number;
  assignee?: UserReference | null;
  owner?: UserReference | null;
  clientFactory?: ApiClientFactory | null;
  entityId: string;
  entityType: 'Test' | 'TestSet' | string;
  onStatusChange?: (newStatus: string) => void;
  onPriorityChange?: (newPriority: number) => void;
  onAssigneeChange?: (newAssignee: User | null) => void;
  onOwnerChange?: (newOwner: User | null) => void;
  onUpdateEntity: (updateData: any, fieldName: string) => Promise<void>;
  statusReadOnly?: boolean;
  showPriority?: boolean;
  // Optional pre-loaded data to avoid API calls
  preloadedStatuses?: Status[];
  preloadedUsers?: User[];
}

interface UserOption extends User {
  displayName: string;
}

const PRIORITY_OPTIONS: PriorityLevel[] = ['Low', 'Medium', 'High', 'Urgent'];

// Priority mapping for conversion between string and numeric values
const priorityMap: Record<PriorityLevel, number> = {
  Low: 0,
  Medium: 1,
  High: 2,
  Urgent: 3,
};

// Reverse mapping from number to PriorityLevel
const reversePriorityMap: Record<number, PriorityLevel> = {
  0: 'Low',
  1: 'Medium',
  2: 'High',
  3: 'Urgent',
};

export default function BaseWorkflowSection({
  title = 'Workflow',
  status,
  priority = 1,
  assignee,
  owner,
  clientFactory,
  entityId,
  entityType,
  onStatusChange,
  onPriorityChange,
  onAssigneeChange,
  onOwnerChange,
  onUpdateEntity,
  statusReadOnly = false,
  showPriority = true,
  preloadedStatuses,
  preloadedUsers,
}: BaseWorkflowSectionProps) {
  // Create stable derived state from props
  const initialPriority = useMemo(
    () => reversePriorityMap[priority] || 'Medium',
    [priority]
  );
  const initialStatus = useMemo(() => status || null, [status]);

  // Component state
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [currentPriority, setCurrentPriority] =
    useState<PriorityLevel>(initialPriority);
  const [currentStatus, setCurrentStatus] = useState<string | null>(
    initialStatus
  );
  const [currentAssignee, setCurrentAssignee] = useState<UserOption | null>(
    null
  );
  const [currentOwner, setCurrentOwner] = useState<UserOption | null>(null);
  const [statusesLoaded, setStatusesLoaded] = useState(false);
  const [usersLoaded, setUsersLoaded] = useState(false);

  const notifications = useNotifications();

  // Memoize clients to prevent recreation
  const clients = useMemo(() => {
    if (!clientFactory) return { statusClient: null, usersClient: null };
    return {
      statusClient: clientFactory.getStatusClient(),
      usersClient: clientFactory.getUsersClient(),
    };
  }, [clientFactory]);

  // Find user by ID helper function - memoize to prevent recreations
  const findUserById = useCallback(
    (userId?: string | null) => {
      if (!userId) return null;
      return users.find(user => user.id === userId) || null;
    },
    [users]
  );

  // Load statuses only once (use preloaded data if available)
  useEffect(() => {
    if (statusesLoaded) return;

    // Use preloaded statuses if available and not empty
    if (preloadedStatuses && preloadedStatuses.length > 0) {
      setStatuses(preloadedStatuses);
      setStatusesLoaded(true);
      return;
    }

    // Otherwise fetch from API
    if (!clients.statusClient) return;

    const fetchStatuses = async () => {
      try {
        setLoadingStatuses(true);
        const fetchedStatuses = await clients.statusClient!.getStatuses({
          entity_type: entityType,
          sort_by: 'name',
          sort_order: 'asc',
        });
        setStatuses(fetchedStatuses);
        setStatusesLoaded(true);
      } catch (error) {
        notifications.show('Failed to load status data', { severity: 'error' });
      } finally {
        setLoadingStatuses(false);
      }
    };

    fetchStatuses();
  }, [
    clients.statusClient,
    entityType,
    notifications,
    statusesLoaded,
    preloadedStatuses,
  ]);

  // Load users only once (use preloaded data if available)
  useEffect(() => {
    if (usersLoaded) return;

    // Use preloaded users if available and not empty
    if (preloadedUsers && preloadedUsers.length > 0) {
      const transformedUsers = preloadedUsers
        .filter(user => user.is_active) // Only show active users
        .map(user => ({
          ...user,
          displayName:
            user.name ||
            `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
            user.email,
        }));
      setUsers(transformedUsers);
      setUsersLoaded(true);
      return;
    }

    // Otherwise fetch from API
    if (!clients.usersClient) return;

    const fetchUsers = async () => {
      try {
        setLoadingUsers(true);
        const fetchedUsers = await clients.usersClient!.getUsers({
          limit: 100,
        });

        // Transform users into options with display names
        const transformedUsers = fetchedUsers.data
          .filter(user => user.is_active) // Only show active users
          .map(user => ({
            ...user,
            displayName:
              user.name ||
              `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
              user.email,
          }));
        setUsers(transformedUsers);
        setUsersLoaded(true);
      } catch (error) {
        notifications.show('Failed to load user data', { severity: 'error' });
      } finally {
        setLoadingUsers(false);
      }
    };

    fetchUsers();
  }, [clients.usersClient, notifications, usersLoaded, preloadedUsers]);

  // Set assignee and owner once users are loaded
  useEffect(() => {
    if (!usersLoaded || !users.length) return;

    setCurrentAssignee(findUserById(assignee?.id) as UserOption | null);
    setCurrentOwner(findUserById(owner?.id) as UserOption | null);
  }, [assignee?.id, owner?.id, findUserById, users, usersLoaded]);

  // Update current status and priority when props change
  useEffect(() => {
    setCurrentStatus(status || null);
  }, [status]);

  useEffect(() => {
    setCurrentPriority(reversePriorityMap[priority] || 'Medium');
  }, [priority]);

  const InfoRow = ({
    label,
    children,
  }: {
    label: string;
    children: React.ReactNode;
  }) => (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        py: 1,
        width: '100%',
      }}
    >
      <Typography variant="subtitle1" sx={{ letterSpacing: '0.15px' }}>
        {label}
      </Typography>
      {children}
    </Box>
  );

  // Memoize handlers to prevent recreations on render
  const handleStatusChange = useCallback(
    async (newStatus: string | null) => {
      // Update UI immediately
      setCurrentStatus(newStatus);
      onStatusChange?.(newStatus || '');

      // Then update backend
      try {
        if (newStatus) {
          // Find the status ID from the statuses array
          const statusObj = statuses.find(s => s.name === newStatus);
          if (statusObj) {
            await onUpdateEntity({ status_id: statusObj.id }, 'Status');
          } else {
            throw new Error(
              `Status "${newStatus}" not found in available statuses`
            );
          }
        } else {
          // If newStatus is null, clear the status
          await onUpdateEntity({ status_id: null }, 'Status');
        }
      } catch (error) {
        // Revert on error
        setCurrentStatus(status || null);
        onStatusChange?.(status || '');
        notifications.show('Failed to update status', { severity: 'error' });
      }
    },
    [onStatusChange, onUpdateEntity, status, statuses, notifications]
  );

  const handlePriorityChange = useCallback(
    async (newPriority: PriorityLevel) => {
      // Update UI immediately
      setCurrentPriority(newPriority);
      const numericPriority = priorityMap[newPriority];
      onPriorityChange?.(numericPriority);

      // Then update backend
      try {
        await onUpdateEntity({ priority: numericPriority }, 'Priority');
      } catch (error) {
        // Revert on error
        setCurrentPriority(reversePriorityMap[priority] || 'Medium');
        onPriorityChange?.(priority);
      }
    },
    [onPriorityChange, onUpdateEntity, priority]
  );

  const handleAssigneeChange = useCallback(
    async (newAssignee: UserOption | null) => {
      // Update UI immediately with the selected user
      setCurrentAssignee(newAssignee);

      try {
        await onUpdateEntity(
          { assignee_id: newAssignee?.id || null },
          'Assignee'
        );
        // Only call onAssigneeChange after successful API update
        onAssigneeChange?.(newAssignee);
      } catch (error) {
        // Revert on error
        const originalAssignee = findUserById(
          assignee?.id
        ) as UserOption | null;
        setCurrentAssignee(originalAssignee);
        notifications.show('Failed to update assignee', { severity: 'error' });
      }
    },
    [
      assignee?.id,
      findUserById,
      notifications,
      onAssigneeChange,
      onUpdateEntity,
    ]
  );

  const handleOwnerChange = useCallback(
    async (newOwner: UserOption | null) => {
      // Update UI immediately with the selected user
      setCurrentOwner(newOwner);
      onOwnerChange?.(newOwner);

      // Then update backend
      try {
        await onUpdateEntity({ owner_id: newOwner?.id || null }, 'Owner');
      } catch (error) {
        // Revert on error
        const originalOwner = findUserById(owner?.id) as UserOption | null;
        setCurrentOwner(originalOwner);
        onOwnerChange?.(originalOwner);
      }
    },
    [findUserById, onOwnerChange, onUpdateEntity, owner?.id]
  );

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        width: '100%',
      }}
    >
      {title && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}

      <Autocomplete
        value={currentStatus}
        onChange={(_, newValue) => handleStatusChange(newValue)}
        options={statuses.map(s => s.name)}
        sx={{ width: '100%' }}
        renderInput={params => (
          <TextField
            {...params}
            label="Status"
            variant="outlined"
            placeholder="Select Status"
          />
        )}
        loading={loadingStatuses}
        disabled={loadingStatuses}
      />

      {showPriority && (
        <Autocomplete
          value={currentPriority}
          onChange={(_, newValue) =>
            handlePriorityChange(newValue as PriorityLevel)
          }
          options={PRIORITY_OPTIONS}
          sx={{ width: '100%' }}
          renderInput={params => (
            <TextField
              {...params}
              label="Priority"
              variant="outlined"
              placeholder="Select Priority"
            />
          )}
          disableClearable
        />
      )}

      <Autocomplete
        options={users}
        value={currentAssignee}
        onChange={(_, newValue) => handleAssigneeChange(newValue)}
        getOptionLabel={option => option.displayName}
        loading={loadingUsers}
        sx={{ width: '100%' }}
        renderInput={params => (
          <TextField
            {...params}
            label="Assignee"
            variant="outlined"
            placeholder="Select Assignee"
            InputProps={{
              ...params.InputProps,
              startAdornment: currentAssignee && (
                <Box sx={{ display: 'flex', alignItems: 'center', pl: 1 }}>
                  <Avatar
                    src={currentAssignee.picture}
                    sx={{
                      width: AVATAR_SIZES.SMALL,
                      height: AVATAR_SIZES.SMALL,
                    }}
                  >
                    <PersonIcon />
                  </Avatar>
                </Box>
              ),
            }}
          />
        )}
        renderOption={(props, option) => {
          const { key, ...otherProps } = props;
          return (
            <li key={option.id} {...otherProps}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Avatar
                  src={option.picture}
                  sx={{
                    width: AVATAR_SIZES.MEDIUM,
                    height: AVATAR_SIZES.MEDIUM,
                  }}
                >
                  {!option.picture && option.displayName.charAt(0)}
                </Avatar>
                <Typography>{option.displayName}</Typography>
              </Box>
            </li>
          );
        }}
      />

      <Autocomplete
        options={users}
        value={currentOwner}
        onChange={(_, newValue) => handleOwnerChange(newValue)}
        getOptionLabel={option => option.displayName}
        loading={loadingUsers}
        sx={{ width: '100%' }}
        renderInput={params => (
          <TextField
            {...params}
            label="Owner"
            variant="outlined"
            placeholder="Select Owner"
            InputProps={{
              ...params.InputProps,
              startAdornment: currentOwner && (
                <Box sx={{ display: 'flex', alignItems: 'center', pl: 1 }}>
                  <Avatar
                    src={currentOwner.picture}
                    sx={{
                      width: AVATAR_SIZES.SMALL,
                      height: AVATAR_SIZES.SMALL,
                    }}
                  >
                    <PersonIcon />
                  </Avatar>
                </Box>
              ),
            }}
          />
        )}
        renderOption={(props, option) => {
          const { key, ...otherProps } = props;
          return (
            <li key={option.id} {...otherProps}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Avatar
                  src={option.picture}
                  sx={{
                    width: AVATAR_SIZES.MEDIUM,
                    height: AVATAR_SIZES.MEDIUM,
                  }}
                >
                  {!option.picture && option.displayName.charAt(0)}
                </Avatar>
                <Typography>{option.displayName}</Typography>
              </Box>
            </li>
          );
        }}
      />
    </Box>
  );
}
