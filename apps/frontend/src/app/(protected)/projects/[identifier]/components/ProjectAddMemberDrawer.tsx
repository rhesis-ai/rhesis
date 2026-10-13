'use client';

import * as React from 'react';
import { useEffect, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Avatar,
  Box,
  CircularProgress,
  TextField,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { useFeature } from '@/contexts/FeaturesContext';
import { FeatureName } from '@/constants/features';
import { getMemberRoleExtensions } from '@/lib/extension-registries';
import { useUsers } from '@/hooks/useLookups';

function getUserDisplayName(user: User): string {
  if (user.name) return user.name;
  const parts = [user.given_name, user.family_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : user.email;
}

interface ProjectAddMemberDrawerProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
  memberUserIds: string[];
  onMemberAdded: () => void;
}

export default function ProjectAddMemberDrawer({
  open,
  onClose,
  projectId,
  memberUserIds,
  onMemberAdded,
}: ProjectAddMemberDrawerProps) {
  const notifications = useNotifications();
  const {
    data: orgUsers = [],
    isLoading: usersLoading,
    isError: usersFailed,
  } = useUsers(open);
  const usersError = usersFailed
    ? 'Failed to load organisation members.'
    : null;
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const rbacEnabled = useFeature(FeatureName.RBAC);
  const { AddMemberRoleField: RawAddMemberRoleField } =
    getMemberRoleExtensions();
  const AddMemberRoleField = rbacEnabled ? RawAddMemberRoleField : undefined;

  useEffect(() => {
    if (!open) {
      setSelectedUser(null);
      setSelectedRoleId(null);
    }
  }, [open]);

  const memberIdSet = new Set(memberUserIds);
  const addableUsers = orgUsers.filter(u => !memberIdSet.has(u.id));

  const handleAdd = async () => {
    if (!selectedUser) return;
    setAdding(true);
    try {
      const factory = new ApiClientFactory();
      // A single atomic request: the backend applies the escalation guard
      // before creating the membership row, so there is no window where the
      // member exists with a role other than the one selected here.
      await factory.getProjectsClient().addProjectMember(projectId, {
        user_id: selectedUser.id,
        role: 'member',
        role_id: selectedRoleId ?? undefined,
      });

      notifications.show(
        `${getUserDisplayName(selectedUser)} added to the project.`,
        { severity: 'success' }
      );
      onMemberAdded();
      onClose();
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to add member.',
        { severity: 'error' }
      );
    } finally {
      setAdding(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Add member"
      onSave={handleAdd}
      saveButtonText="Add as member"
      saveDisabled={!selectedUser}
      loading={adding}
    >
      <Box sx={drawerSectionSx}>
        <FormSectionDivider
          headline="Member"
          descriptiveText="Select an organisation member to grant access to this project."
        />
        <Box sx={drawerFieldsSx}>
          {usersError && <Alert severity="warning">{usersError}</Alert>}
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
            renderOption={(props, option) => {
              const { key, ...optionProps } = props;
              return (
                <Box
                  component="li"
                  key={key}
                  {...optionProps}
                  sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}
                >
                  <Avatar src={option.picture} sx={{ width: 32, height: 32 }}>
                    <PersonIcon fontSize="small" />
                  </Avatar>
                  <Box>
                    <Box
                      component="span"
                      sx={{ display: 'block', fontSize: 14 }}
                    >
                      {getUserDisplayName(option)}
                    </Box>
                    <Box
                      component="span"
                      sx={{
                        display: 'block',
                        fontSize: 12,
                        color: 'text.secondary',
                      }}
                    >
                      {option.email}
                    </Box>
                  </Box>
                </Box>
              );
            }}
            renderInput={params => (
              <TextField
                {...params}
                label="Organisation member"
                placeholder="Search org members to add…"
                sx={drawerOutlinedFieldSx}
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
          />
          {AddMemberRoleField && (
            <AddMemberRoleField
              value={selectedRoleId}
              onChange={setSelectedRoleId}
            />
          )}
        </Box>
      </Box>
    </BaseDrawer>
  );
}
