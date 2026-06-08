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
  TextField,
  Typography,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import ViewField from '@/components/common/ViewField';
import EditableSection from '@/components/common/EditableSection';
import GridBadge from '@/components/common/GridBadge';
import { Project } from '@/utils/api-client/interfaces/project';
import { User } from '@/utils/api-client/interfaces/user';
import { UsersClient } from '@/utils/api-client/users-client';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

interface MetadataDraft {
  name: string;
  description: string;
  is_active: boolean;
  owner_id: string;
}

interface ProjectMetadataCardProps {
  project: Project;
  sessionToken: string;
  onSave: (updatedProject: Partial<Project>) => Promise<void>;
}

function getUserDisplayName(user: User): string {
  if (user.name) return user.name;
  const parts = [user.given_name, user.family_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : user.email;
}

export default function ProjectMetadataCard({
  project,
  sessionToken,
  onSave,
}: ProjectMetadataCardProps) {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadUsers() {
      try {
        const usersClient = new UsersClient(sessionToken, undefined, '');
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
  }, [sessionToken]);

  const initialDraft: MetadataDraft = useMemo(
    () => ({
      name: project.name,
      description: project.description ?? '',
      is_active: project.is_active ?? true,
      owner_id: String(project.owner?.id ?? project.owner_id ?? ''),
    }),
    [project]
  );

  const handleSave = async (draft: MetadataDraft) => {
    await onSave({
      name: draft.name.trim(),
      description: draft.description,
      is_active: draft.is_active,
      owner_id: draft.owner_id || undefined,
    });
  };

  const ownerFromProject =
    project.owner?.name || project.owner?.email || 'Not assigned';

  return (
    <EditableSection
      title="Project details"
      initialValue={initialDraft}
      onSave={handleSave}
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
            columnSpacing={isEditing ? 2 : '30px'}
            rowSpacing={isEditing ? 2 : '20px'}
            alignItems="flex-start"
          >
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Name"
                  value={draft.name}
                  onChange={e =>
                    setDraft(d => ({ ...d, name: e.target.value }))
                  }
                  required
                />
              ) : (
                <ViewField label="Name" value={draft.name} />
              )}
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              {isEditing ? (
                <TextField
                  select
                  fullWidth
                  label="Status"
                  value={draft.is_active ? 'active' : 'inactive'}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      is_active: e.target.value === 'active',
                    }))
                  }
                >
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="inactive">Inactive</MenuItem>
                </TextField>
              ) : (
                <ViewField label="Status">
                  <GridBadge
                    size="detail"
                    label={draft.is_active ? 'Active' : 'Inactive'}
                  />
                </ViewField>
              )}
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <FormControl fullWidth>
                  <InputLabel>Owner</InputLabel>
                  <Select
                    value={draft.owner_id}
                    label="Owner"
                    onChange={e =>
                      setDraft(d => ({ ...d, owner_id: e.target.value }))
                    }
                    renderValue={selected => {
                      const user = users.find(u => u.id === selected);
                      if (!user) return ownerFromProject;
                      return (
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          <Avatar
                            src={user.picture}
                            alt={getUserDisplayName(user)}
                            sx={{ width: 24, height: 24 }}
                          >
                            <PersonIcon sx={{ fontSize: 16 }} />
                          </Avatar>
                          <Typography variant="body2">
                            {getUserDisplayName(user)}
                          </Typography>
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
                            sx={{ width: 32, height: 32 }}
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
              ) : (
                <ViewField label="Owner">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Avatar
                      src={ownerPicture}
                      alt={ownerName}
                      sx={{
                        width: AVATAR_SIZES.MEDIUM,
                        height: AVATAR_SIZES.MEDIUM,
                      }}
                    >
                      <PersonIcon />
                    </Avatar>
                    <Typography variant="body1">{ownerName}</Typography>
                  </Box>
                </ViewField>
              )}
            </Grid>

            <Grid size={12}>
              {isEditing ? (
                <TextField
                  fullWidth
                  multiline
                  minRows={3}
                  label="Description"
                  value={draft.description}
                  onChange={e =>
                    setDraft(d => ({ ...d, description: e.target.value }))
                  }
                />
              ) : (
                <ViewField
                  label="Description"
                  value={draft.description || 'No description provided'}
                  multiline
                />
              )}
            </Grid>
          </Grid>
        );
      }}
    </EditableSection>
  );
}
