'use client';

import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import Grid from '@mui/material/Grid';
import {
  Avatar,
  Box,
  FormControl,
  InputLabel,
  ListItemAvatar,
  ListItemText,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import PersonIcon from '@mui/icons-material/Person';
import EditableField from '@/components/common/EditableField';
import EditableSection from '@/components/common/EditableSection';
import {
  editableOutlinedFieldSx,
  readOnlyOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';
import { SECTION_GRID } from '@/styles/theme-constants';
import { Project } from '@/utils/api-client/interfaces/project';
import { User } from '@/utils/api-client/interfaces/user';
import { UsersClient } from '@/utils/api-client/users-client';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

const readOnlySelectSx: SxProps<Theme> = [
  readOnlyOutlinedFieldSx as Record<string, unknown>,
  { '& .MuiSelect-icon': { display: 'none' }, pointerEvents: 'none' },
];

interface MetadataDraft {
  name: string;
  description: string;
  is_active: boolean;
  owner_id: string;
}

interface ProjectMetadataCardProps {
  project: Project;
  onSave: (updatedProject: Partial<Project>) => Promise<boolean>;
  editable?: boolean;
}

function getUserDisplayName(user: User): string {
  if (user.name) return user.name;
  const parts = [user.given_name, user.family_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : user.email;
}

export default function ProjectMetadataCard({
  project,
  onSave,
  editable,
}: ProjectMetadataCardProps) {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadUsers() {
      try {
        const usersClient = new UsersClient(undefined, undefined, '');
        const result = await usersClient.getUsers({ limit: 100 });
        if (!cancelled) setUsers(result.data);
      } catch {
        if (!cancelled) setUsers([]);
      }
    }

    loadUsers();
    return () => {
      cancelled = true;
    };
  }, []);

  const initialDraft: MetadataDraft = useMemo(
    () => ({
      name: project.name,
      description: project.description ?? '',
      is_active: project.is_active ?? true,
      owner_id: String(project.owner?.id ?? project.owner_id ?? ''),
    }),
    [project]
  );

  // Returning the result keeps the card in edit mode when the update fails.
  const handleSave = (draft: MetadataDraft) =>
    onSave({
      name: draft.name.trim(),
      description: draft.description,
      is_active: draft.is_active,
      owner_id: draft.owner_id || undefined,
    });

  const ownerFromProject =
    project.owner?.name || project.owner?.email || 'Not assigned';

  return (
    <EditableSection
      title="Project details"
      initialValue={initialDraft}
      onSave={handleSave}
      editable={editable}
    >
      {({ draft, setDraft, isEditing }) => {
        const selectedOwner = users.find(u => u.id === draft.owner_id);
        const ownerName = selectedOwner
          ? getUserDisplayName(selectedOwner)
          : ownerFromProject;
        const ownerPicture =
          selectedOwner?.picture ?? project.owner?.picture ?? undefined;

        return (
          <Grid
            container
            columnSpacing={SECTION_GRID.columnSpacing}
            rowSpacing={SECTION_GRID.rowSpacing}
            alignItems="flex-start"
          >
            <Grid size={{ xs: 12, sm: 6, md: 6 }}>
              <EditableField
                fullWidth
                editing={isEditing}
                label="Name"
                value={draft.name}
                onChange={e => setDraft(d => ({ ...d, name: e.target.value }))}
                required={isEditing}
              />
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <FormControl
                fullWidth
                sx={isEditing ? editableOutlinedFieldSx : readOnlySelectSx}
              >
                <InputLabel>Status</InputLabel>
                <Select
                  value={draft.is_active ? 'active' : 'inactive'}
                  label="Status"
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      is_active: e.target.value === 'active',
                    }))
                  }
                  readOnly={!isEditing}
                >
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="inactive">Inactive</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl
                fullWidth
                sx={isEditing ? editableOutlinedFieldSx : readOnlySelectSx}
              >
                <InputLabel shrink>Owner</InputLabel>
                <Select
                  displayEmpty
                  notched
                  value={draft.owner_id}
                  label="Owner"
                  onChange={e =>
                    setDraft(d => ({ ...d, owner_id: e.target.value }))
                  }
                  readOnly={!isEditing}
                  renderValue={selected => {
                    const user = users.find(u => u.id === selected);
                    const displayName = user
                      ? getUserDisplayName(user)
                      : ownerName;
                    const picture = user?.picture ?? ownerPicture;
                    return (
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <Avatar
                          src={picture}
                          alt={displayName}
                          sx={{
                            width: AVATAR_SIZES.SMALL,
                            height: AVATAR_SIZES.SMALL,
                          }}
                        >
                          <PersonIcon fontSize="small" />
                        </Avatar>
                        <Typography variant="body2">{displayName}</Typography>
                      </Box>
                    );
                  }}
                >
                  {users.map(user => (
                    <MenuItem key={user.id} value={user.id}>
                      <ListItemAvatar>
                        <Avatar
                          src={user.picture}
                          alt={getUserDisplayName(user)}
                          sx={{
                            width: AVATAR_SIZES.MEDIUM,
                            height: AVATAR_SIZES.MEDIUM,
                          }}
                        >
                          <PersonIcon fontSize="small" />
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={getUserDisplayName(user)}
                        secondary={user.email}
                      />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid size={12}>
              <EditableField
                fullWidth
                editing={isEditing}
                label="Description"
                value={
                  isEditing
                    ? draft.description
                    : draft.description || 'No description provided'
                }
                onChange={e =>
                  setDraft(d => ({ ...d, description: e.target.value }))
                }
                multiline
                minRows={3}
              />
            </Grid>
          </Grid>
        );
      }}
    </EditableSection>
  );
}
