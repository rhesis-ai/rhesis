'use client';

import React, { useRef, useCallback } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Autocomplete, TextField, Box, Avatar, MenuItem, Typography, Divider } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { Status } from '@/utils/api-client/interfaces/status';
import PersonIcon from '@mui/icons-material/Person';

// Priority levels mapping (same as in TestDrawer)
const PRIORITY_LEVELS = [
  { value: 0, label: 'Low' },
  { value: 1, label: 'Medium' },
  { value: 2, label: 'High' },
  { value: 3, label: 'Urgent' }
];

interface TestSetDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  testSet?: TestSet;
  onSuccess?: () => void;
}

export default function TestSetDrawer({ 
  open, 
  onClose, 
  sessionToken,
  testSet,
  onSuccess 
}: TestSetDrawerProps) {
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const [name, setName] = React.useState(testSet?.name || '');
  const [description, setDescription] = React.useState(testSet?.description || '');
  const [shortDescription, setShortDescription] = React.useState(testSet?.short_description || '');
  const [status, setStatus] = React.useState<Status | null>(null);
  const [assignee, setAssignee] = React.useState<User | null>(null);
  const [owner, setOwner] = React.useState<User | null>(null);
  const [priority, setPriority] = React.useState<number>(testSet?.priority || 1); // Default to Medium (1)
  const [statuses, setStatuses] = React.useState<Status[]>([]);
  const [users, setUsers] = React.useState<User[]>([]);

  // Get current user from token
  const getCurrentUserId = useCallback(() => {
    try {
      const [, payloadBase64] = sessionToken.split('.');
      // Add padding if needed
      const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/');
      const pad = base64.length % 4;
      const paddedBase64 = pad ? base64 + '='.repeat(4 - pad) : base64;
      
      const payload = JSON.parse(Buffer.from(paddedBase64, 'base64').toString('utf-8'));
      const currentUser = users.find(user => user.id === payload.user?.id);
      return currentUser?.id;
    } catch (err) {
      console.error('Error decoding JWT token:', err);
      return undefined;
    }
  }, [sessionToken, users]);

  // Load statuses and users
  React.useEffect(() => {
    const loadData = async () => {
      if (!sessionToken) return;

      const clientFactory = new ApiClientFactory(sessionToken);
      const statusClient = clientFactory.getStatusClient();
      const usersClient = clientFactory.getUsersClient();

      try {
        const currentUserId = getCurrentUserId();
        const [fetchedStatuses, fetchedUsers] = await Promise.all([
          statusClient.getStatuses({ 
            entity_type: 'TestSet',
            sort_by: 'name',
            sort_order: 'asc'
          }),
          usersClient.getUsers()
        ]);

        setStatuses(fetchedStatuses);
        setUsers(fetchedUsers);

        // Set initial values if editing
        if (testSet) {
          if (testSet.status_id) {
            const currentStatus = fetchedStatuses.find(s => s.id === testSet.status_id);
            setStatus(currentStatus || null);
          }
          if (testSet.assignee_id) {
            const currentAssignee = fetchedUsers.find(u => u.id === testSet.assignee_id);
            setAssignee(currentAssignee || null);
          }
          if (testSet.owner_id) {
            const currentOwner = fetchedUsers.find(u => u.id === testSet.owner_id);
            setOwner(currentOwner || null);
          }
        } else {
          // Set default owner as current user for new test sets
          if (currentUserId) {
            const currentUser = fetchedUsers.find(u => u.id === currentUserId);
            setOwner(currentUser || null);
          }
        }
      } catch (err) {
        console.error('Error loading data:', err);
        setError('Failed to load required data');
      }
    };

    loadData();
  }, [sessionToken, testSet, getCurrentUserId]);

  const handleSave = async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      const testSetData = {
        name,
        description,
        short_description: shortDescription,
        status_id: status?.id,
        assignee_id: assignee?.id,
        owner_id: owner?.id,
        priority,
        visibility: 'organization' as const,
        is_published: false,
        attributes: {}
      };

      if (testSet) {
        await testSetsClient.updateTestSet(testSet.id, testSetData);
      } else {
        await testSetsClient.createTestSet(testSetData);
      }

      onSuccess?.();
      onClose();
    } catch (err) {
      console.error('Error saving test set:', err);
      setError('Failed to save test set');
    } finally {
      setLoading(false);
    }
  };

  const getUserDisplayName = (user: User) => {
    return user.name || 
      `${user.given_name || ''} ${user.family_name || ''}`.trim() || 
      user.email;
  };

  const renderUserOption = (props: React.HTMLAttributes<HTMLLIElement> & { key?: string }, option: User) => {
    const { key, ...otherProps } = props;
    return (
      <Box component="li" key={key} {...otherProps}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Avatar
            src={option.picture}
            sx={{ width: 24, height: 24 }}
          >
            <PersonIcon />
          </Avatar>
          {getUserDisplayName(option)}
        </Box>
      </Box>
    );
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={testSet ? 'Edit Test Set' : 'New Test Set'}
      loading={loading}
      error={error}
      onSave={handleSave}
    >
      <>
        <Typography variant="subtitle2" color="text.secondary">
          Workflow
        </Typography>

        <Autocomplete
          options={statuses}
          value={status}
          onChange={(_, newValue) => setStatus(newValue)}
          getOptionLabel={(option) => option.name}
          renderInput={(params) => (
            <TextField {...params} label="Status" required />
          )}
        />

<TextField
          select
          label="Priority"
          value={priority}
          onChange={(e) => setPriority(Number(e.target.value))}
          fullWidth
          required
        >
          {PRIORITY_LEVELS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>

        <Autocomplete
          options={users}
          value={assignee}
          onChange={(_, newValue) => setAssignee(newValue)}
          getOptionLabel={getUserDisplayName}
          renderOption={renderUserOption}
          renderInput={(params) => (
            <TextField 
              {...params} 
              label="Assignee"
              InputProps={{
                ...params.InputProps,
                startAdornment: assignee && (
                  <Avatar
                    src={assignee.picture}
                    sx={{ width: 24, height: 24, mr: 1 }}
                  >
                    <PersonIcon />
                  </Avatar>
                )
              }}
            />
          )}
        />

        <Autocomplete
          options={users}
          value={owner}
          onChange={(_, newValue) => setOwner(newValue)}
          getOptionLabel={getUserDisplayName}
          renderOption={renderUserOption}
          renderInput={(params) => (
            <TextField 
              {...params} 
              label="Owner" 
              required
              InputProps={{
                ...params.InputProps,
                startAdornment: owner && (
                  <Avatar
                    src={owner.picture}
                    sx={{ width: 24, height: 24, mr: 1 }}
                  >
                    <PersonIcon />
                  </Avatar>
                )
              }}
            />
          )}
        />

        <Divider sx={{ my: 1 }} />

        <Typography variant="subtitle2" color="text.secondary">
          Test Set Details
        </Typography>

        <TextField
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          fullWidth
        />

        <TextField
          label="Short Description"
          value={shortDescription}
          onChange={(e) => setShortDescription(e.target.value)}
          fullWidth
        />

        <TextField
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          rows={4}
          fullWidth
        />
      </>
    </BaseDrawer>
  );
} 