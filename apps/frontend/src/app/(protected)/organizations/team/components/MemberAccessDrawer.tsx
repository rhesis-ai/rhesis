'use client';

import React, { useEffect, useState } from 'react';
import {
  Avatar,
  Box,
  Divider,
  List,
  ListItem,
  Skeleton,
  Typography,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import BaseDrawer from '@/components/common/BaseDrawer';
import GridBadge from '@/components/common/GridBadge';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import { BORDER_RADIUS } from '@/styles/theme';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { Project, ProjectMember } from '@/utils/api-client/interfaces/project';
import { getMemberRoleExtensions } from '@/lib/extension-registries';

interface ProjectAccess {
  project: Project;
  member: ProjectMember;
}

function getDisplayName(user: User): string {
  if (user.name) return user.name;
  if (user.given_name || user.family_name) {
    return `${user.given_name || ''} ${user.family_name || ''}`.trim();
  }
  return user.email;
}

function formatRole(role: string | null | undefined): string {
  if (!role) return 'Member';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

export interface MemberAccessDrawerProps {
  open: boolean;
  onClose: () => void;
  user: User | null;
}

export default function MemberAccessDrawer({
  open,
  onClose,
  user,
}: MemberAccessDrawerProps) {
  const { data: session } = useSession();
  const [projectAccess, setProjectAccess] = useState<ProjectAccess[]>([]);
  const [loading, setLoading] = useState(false);
  const { OrgRoleCell, ProjectRoleCell } = getMemberRoleExtensions();

  useEffect(() => {
    if (!open || !user || !session?.session_token) return;

    setLoading(true);
    setProjectAccess([]);

    const factory = new ApiClientFactory(session.session_token);
    const projectsClient = factory.getProjectsClient();

    projectsClient
      .getAllProjects()
      .then(async projects => {
        const results = await Promise.all(
          projects.map(async project => {
            try {
              const members = await projectsClient.getProjectMembers(
                project.id as string
              );
              const row = members.find(m => m.user_id === user.id);
              return row ? { project, member: row } : null;
            } catch {
              return null;
            }
          })
        );
        setProjectAccess(
          results
            .filter((r): r is ProjectAccess => r !== null)
            .sort((a, b) => a.project.name.localeCompare(b.project.name))
        );
      })
      .finally(() => setLoading(false));
  }, [open, user?.id, session?.session_token]);

  const displayName = user ? getDisplayName(user) : '';
  const sessionToken = session?.session_token ?? '';
  const count = projectAccess.length;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Member Access"
      closeButtonText="Close"
    >
      {user && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Member header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 2,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0 }}>
              <Avatar
                src={user.picture || undefined}
                sx={{ width: 48, height: 48, bgcolor: 'primary.main', flexShrink: 0 }}
              >
                {user.picture ? null : <PersonIcon />}
              </Avatar>
              <Box sx={{ minWidth: 0 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight={600}
                  sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {displayName}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {user.email}
                </Typography>
              </Box>
            </Box>

            {OrgRoleCell && (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-end',
                  gap: 0.5,
                  flexShrink: 0,
                }}
              >
                <Typography variant="overline" color="text.secondary">
                  Org Role
                </Typography>
                <OrgRoleCell userId={user.id} sessionToken={sessionToken} />
              </Box>
            )}
          </Box>

          <Divider />

          {/* Project access section */}
          <Box>
            <Typography
              variant="body2"
              fontWeight={500}
              color="text.secondary"
              sx={{ mb: 1 }}
            >
              Project access {!loading && `(${count} ${count === 1 ? 'project' : 'projects'})`}
            </Typography>

            {loading ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {[1, 2, 3].map(i => (
                  <Skeleton key={i} variant="rounded" height={64} />
                ))}
              </Box>
            ) : count === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No explicit project assignments.
              </Typography>
            ) : (
              <List disablePadding sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                {projectAccess.map(({ project, member }) => {
                  const projectId = project.id as string;
                  return (
                    <ListItem
                      key={projectId}
                      disablePadding
                      sx={{
                        borderRadius: BORDER_RADIUS.md,
                        border: theme => `1px solid ${theme.palette.divider}`,
                        px: 1.5,
                        py: 1.25,
                        gap: 1.5,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      {/* Project avatar — matches ProjectSwitcherDrawer */}
                      <Avatar
                        sx={{
                          width: theme => theme.spacing(4),
                          height: theme => theme.spacing(4),
                          bgcolor: 'primary.main',
                          flexShrink: 0,
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontWeight: theme => theme.typography.fontWeightBold,
                          '& svg': { fontSize: theme => theme.spacing(2) },
                        }}
                      >
                        {getProjectIcon(project)}
                      </Avatar>

                      {/* Project name + description */}
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography
                          variant="body2"
                          sx={{
                            fontWeight: theme => theme.typography.fontWeightMedium,
                            color: theme => theme.palette.greyscale.title,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {project.name}
                        </Typography>
                        {project.description && (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              display: 'block',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {project.description}
                          </Typography>
                        )}
                      </Box>

                      {/* Role selector */}
                      {ProjectRoleCell ? (
                        <Box sx={{ flexShrink: 0 }}>
                          <ProjectRoleCell
                            userId={user.id}
                            projectId={projectId}
                            sessionToken={sessionToken}
                          />
                        </Box>
                      ) : (
                        <GridBadge
                          label={formatRole(member.role)}
                          sx={{ flexShrink: 0 }}
                        />
                      )}
                    </ListItem>
                  );
                })}
              </List>
            )}
          </Box>
        </Box>
      )}
    </BaseDrawer>
  );
}
