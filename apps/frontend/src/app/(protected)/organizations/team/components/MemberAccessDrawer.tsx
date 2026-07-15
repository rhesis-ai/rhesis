'use client';

import { useEffect, useState } from 'react';
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
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { Project, ProjectMember } from '@/utils/api-client/interfaces/project';
import {
  getMemberRoleExtensions,
  type UserProjectMembership,
} from '@/lib/extension-registries';
import {
  memberAvatarSx,
  orgRoleContainerSx,
  projectAvatarSx,
  projectCardItemSx,
  projectDescriptionSx,
  projectNameSx,
  truncateSx,
} from './memberCardSx';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface ProjectAccess {
  project: Pick<Project, 'id' | 'name' | 'description' | 'icon'>;
  member: Pick<ProjectMember, 'role'>;
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

function toBulkProjectAccess(m: UserProjectMembership): ProjectAccess {
  return {
    project: {
      id: m.project.id,
      name: m.project.name,
      description: m.project.description ?? undefined,
      icon: m.project.icon ?? undefined,
    },
    member: { role: m.role?.display_name ?? null },
  };
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
  const { data: session, status } = useSession();
  const [projectAccess, setProjectAccess] = useState<ProjectAccess[]>([]);
  const [loading, setLoading] = useState(false);
  const { OrgRoleCell, ProjectRoleCell, fetchUserProjectMemberships } =
    getMemberRoleExtensions();

  useEffect(() => {
    if (!open || !user || !isAuthenticated(status)) return;

    setLoading(true);
    setProjectAccess([]);

    if (fetchUserProjectMemberships) {
      fetchUserProjectMemberships(session?.session_token ?? '', user.id)
        .then(memberships => {
          setProjectAccess(
            memberships
              .map(toBulkProjectAccess)
              .sort((a, b) => a.project.name.localeCompare(b.project.name))
          );
        })
        .catch(() => setProjectAccess([]))
        .finally(() => setLoading(false));
      return;
    }

    const sessionToken = session?.session_token ?? '';

    new ApiClientFactory(sessionToken)
      .getProjectsClient()
      .getAllProjects()
      .then(async projects => {
        const results = await Promise.all(
          projects.map(async project => {
            try {
              const members = await new ApiClientFactory(
                sessionToken,
                project.id as string
              )
                .getProjectsClient()
                .getProjectMembers(project.id as string);
              const row = members.find(m => m.user_id === user.id);
              return row ? ({ project, member: row } as ProjectAccess) : null;
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
  }, [
    open,
    user?.id,
    session?.session_token,
    fetchUserProjectMemberships,
    status,
    user,
  ]);

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
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                minWidth: 0,
              }}
            >
              <Avatar src={user.picture || undefined} sx={memberAvatarSx}>
                {user.picture ? null : <PersonIcon />}
              </Avatar>
              <Box sx={{ minWidth: 0 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight={600}
                  sx={truncateSx}
                >
                  {displayName}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={truncateSx}
                >
                  {user.email}
                </Typography>
              </Box>
            </Box>

            {OrgRoleCell && (
              <Box sx={orgRoleContainerSx}>
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
              Project access{' '}
              {!loading && `(${count} ${count === 1 ? 'project' : 'projects'})`}
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
              <List
                disablePadding
                sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}
              >
                {projectAccess.map(({ project, member }) => {
                  const projectId = project.id as string;
                  return (
                    <ListItem
                      key={projectId}
                      disablePadding
                      sx={projectCardItemSx}
                    >
                      <Avatar sx={projectAvatarSx}>
                        {getProjectIcon(project)}
                      </Avatar>

                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" sx={projectNameSx}>
                          {project.name}
                        </Typography>
                        {project.description && (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={projectDescriptionSx}
                          >
                            {project.description}
                          </Typography>
                        )}
                      </Box>

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
