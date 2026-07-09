'use client';

import * as React from 'react';
import {
  Avatar,
  Box,
  InputAdornment,
  TextField,
  Button,
  IconButton,
  CircularProgress,
  List,
  ListItemButton,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
  drawerOutlineButtonSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import {
  getSelectableProjectItemSx,
  getSelectableProjectNameSx,
  projectAvatarSx,
  projectDescriptionSx,
} from './memberCardSx';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import SendIcon from '@mui/icons-material/Send';
import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { getMemberRoleExtensions } from '@/lib/extension-registries';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UUID } from 'crypto';

interface InviteItem {
  id: string;
  email: string;
  orgRoleId: string | null;
}

interface FormData {
  invites: InviteItem[];
}

interface TeamInviteFormProps {
  onInvitesSent?: (emails: string[]) => void;
  disableDuringTour?: boolean;
  /** When true, submit is triggered by the parent drawer (no footer button). */
  embedded?: boolean;
  onSubmittingChange?: (submitting: boolean) => void;
  /** Passed from the parent drawer so role pickers refetch when it opens. */
  drawerOpen?: boolean;
}

function createInvite(email = ''): InviteItem {
  return { id: crypto.randomUUID(), email, orgRoleId: null };
}

const TeamInviteForm = React.forwardRef<HTMLFormElement, TeamInviteFormProps>(
  function TeamInviteForm(
    {
      onInvitesSent,
      disableDuringTour = false,
      embedded = false,
      onSubmittingChange,
      drawerOpen = false,
    },
    ref
  ) {
    const { data: session } = useSession();
    const notifications = useNotifications();
    const { projects: availableProjects } = useActiveProject();
    const { AddMemberRoleField, InviteOrgRoleField, assignOrgMemberRole } =
      getMemberRoleExtensions();

    const [formData, setFormData] = useState<FormData>({
      invites: [createInvite()],
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errors, setErrors] = useState<{
      [key: string]: { hasError: boolean; message: string };
    }>({});
    const [projectSearch, setProjectSearch] = useState('');
    // projectRoles maps projectId → chosen roleId (null = default/unset).
    // A project being present in this map means it is selected for invite.
    const [projectRoles, setProjectRoles] = useState<
      Record<string, string | null>
    >({});

    useEffect(() => {
      onSubmittingChange?.(isSubmitting);
    }, [isSubmitting, onSubmittingChange]);

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const MAX_TEAM_MEMBERS = 10;

    const validateForm = () => {
      const newErrors: {
        [key: string]: { hasError: boolean; message: string };
      } = {};
      let hasError = false;

      const nonEmptyInvites = formData.invites.filter(invite =>
        invite.email.trim()
      );
      if (nonEmptyInvites.length > MAX_TEAM_MEMBERS) {
        notifications.show(
          `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members at once.`,
          { severity: 'error' }
        );
        return false;
      }

      const emailsToCheck = formData.invites
        .map(invite => ({
          email: invite.email.trim().toLowerCase(),
          id: invite.id,
        }))
        .filter(item => item.email);

      const seenEmails = new Set<string>();
      const duplicateEmails = new Set<string>();

      emailsToCheck.forEach(({ email }) => {
        if (seenEmails.has(email)) {
          duplicateEmails.add(email);
        } else {
          seenEmails.add(email);
        }
      });

      formData.invites.forEach(invite => {
        const trimmedEmail = invite.email.trim();

        if (trimmedEmail) {
          if (!emailRegex.test(trimmedEmail)) {
            newErrors[invite.id] = {
              hasError: true,
              message: 'Please enter a valid email address',
            };
            hasError = true;
          } else if (duplicateEmails.has(trimmedEmail.toLowerCase())) {
            newErrors[invite.id] = {
              hasError: true,
              message: 'This email address is already added',
            };
            hasError = true;
          }
        }
      });

      setErrors(newErrors);
      return !hasError;
    };

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();

      if (!validateForm()) {
        return;
      }

      if (!session?.session_token) {
        notifications.show('Session expired. Please refresh the page.', {
          severity: 'error',
        });
        return;
      }

      const sessionToken = session.session_token;

      try {
        setIsSubmitting(true);

        const validInvites = formData.invites.filter(invite =>
          invite.email.trim()
        );

        if (validInvites.length === 0) {
          notifications.show('Please enter at least one email address', {
            severity: 'error',
          });
          return;
        }

        const clientFactory = new ApiClientFactory(sessionToken);
        const usersClient = clientFactory.getUsersClient();

        type InviteResult = {
          user: Awaited<ReturnType<typeof usersClient.createUser>> | null;
          invitation: {
            email: string;
            success: boolean;
            error?: string;
          };
        };

        const createUserResults = await Promise.all(
          validInvites.map(async invite => {
            const email = invite.email.trim();
            const userData = {
              email: email,
              organization_id: session.user?.organization_id as UUID,
              is_active: true,
              send_invite: true,
            };

            try {
              const user = await usersClient.createUser(userData);
              if (user && invite.orgRoleId && assignOrgMemberRole) {
                try {
                  await assignOrgMemberRole(
                    sessionToken,
                    String(user.id),
                    invite.orgRoleId
                  );
                } catch {
                  // org-role assignment failure is non-fatal — user is still invited
                }
              }
              return {
                user,
                invitation: { email, success: true },
              } satisfies InviteResult;
            } catch (error: unknown) {
              let errorMessage = 'Unknown error';
              let isExpectedError = false;

              if (error instanceof Error) {
                if (error.message.includes('API error:')) {
                  const statusMatch = error.message.match(/API error: (\d+)/);
                  const statusCode = statusMatch
                    ? parseInt(statusMatch[1])
                    : null;
                  isExpectedError = statusCode
                    ? [400, 409, 422, 429].includes(statusCode)
                    : false;

                  const match = error.message.match(/API error: \d+ - (.+)/);
                  if (match && match[1]) {
                    try {
                      const parsed = JSON.parse(match[1]);
                      errorMessage =
                        parsed.detail || parsed.message || match[1];
                    } catch {
                      errorMessage = match[1];
                    }
                  } else {
                    errorMessage = error.message;
                  }
                } else {
                  errorMessage = error.message;
                }
              } else if (
                typeof error === 'object' &&
                error !== null &&
                'detail' in error
              ) {
                errorMessage = String((error as { detail: unknown }).detail);
              } else if (typeof error === 'string') {
                errorMessage = error;
              }

              if (!isExpectedError) {
                // unexpected errors logged by API client
              }

              return {
                user: null,
                invitation: { email, success: false, error: errorMessage },
              } satisfies InviteResult;
            }
          })
        );

        const createdUsers = createUserResults.map(result => result.user);
        const invitationResults = createUserResults.map(
          result => result.invitation
        );

        // Enroll successfully created users into the selected projects.
        const selectedProjectIds = Object.keys(projectRoles);
        if (selectedProjectIds.length > 0) {
          const projectsClient = clientFactory.getProjectsClient();
          const enrollPromises = createdUsers.flatMap((user, idx) => {
            if (!user || !invitationResults[idx]?.success) return [];
            return selectedProjectIds.map(async projectId => {
              const userId = String(user.id);
              const roleId = projectRoles[projectId];
              try {
                // Single atomic request: the backend applies the escalation
                // guard before creating the membership row, so the member is
                // never left enrolled with a role other than the one selected
                // here (no best-effort follow-up assignment to partially fail).
                await projectsClient.addProjectMember(projectId, {
                  user_id: userId,
                  role: 'member',
                  role_id: roleId ?? undefined,
                });
              } catch {
                // enrollment failure is non-fatal — user is still invited
              }
            });
          });
          await Promise.all(enrollPromises);
        }

        const successCount = invitationResults.filter(
          result => result.success
        ).length;
        const failedCount = validInvites.length - successCount;

        if (successCount > 0 && failedCount === 0) {
          notifications.show(
            `Successfully sent ${successCount} invitation${successCount > 1 ? 's' : ''}!`,
            { severity: 'success' }
          );
        } else if (successCount > 0 && failedCount > 0) {
          const failedEmails = invitationResults
            .filter(result => !result.success)
            .map(result => result.email);

          const errorTypes = invitationResults
            .filter(result => !result.success)
            .map(result => result.error)
            .filter((error, index, arr) => arr.indexOf(error) === index);

          let errorSummary = '';
          if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('rate limit')
          ) {
            errorSummary = 'rate limit exceeded';
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already belongs to an organization')
          ) {
            errorSummary = `${failedEmails.join(', ')} already belong${failedEmails.length === 1 ? 's' : ''} to another organization`;
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already exists')
          ) {
            errorSummary = `${failedEmails.join(', ')} already exist${failedEmails.length === 1 ? 's' : ''}`;
          } else {
            errorSummary = `${failedEmails.join(', ')} failed`;
          }

          notifications.show(
            `Sent ${successCount} invitation${successCount > 1 ? 's' : ''}. ${errorSummary}.`,
            { severity: 'warning', autoHideDuration: 6000 }
          );
        } else {
          const failedEmails = invitationResults
            .filter(result => !result.success)
            .map(result => result.email);

          const errorTypes = invitationResults
            .filter(result => !result.success)
            .map(result => result.error)
            .filter((error, index, arr) => arr.indexOf(error) === index);

          let errorMessage = '';
          if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('rate limit')
          ) {
            errorMessage = errorTypes[0];
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already belongs to an organization')
          ) {
            if (failedEmails.length === 1) {
              errorMessage = `${failedEmails[0]} already belongs to another organization. They must leave their current organization first.`;
            } else {
              errorMessage = `${failedEmails.join(', ')} already belong to another organization. They must leave their current organizations first.`;
            }
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already exists')
          ) {
            if (failedEmails.length === 1) {
              errorMessage = `${failedEmails[0]} already exists.`;
            } else {
              errorMessage = `${failedEmails.join(', ')} already exist.`;
            }
          } else {
            errorMessage = `Failed to invite ${failedEmails.join(', ')}.`;
          }

          notifications.show(errorMessage, {
            severity: 'error',
            autoHideDuration: 6000,
          });
        }

        if (successCount > 0) {
          setFormData({ invites: [createInvite()] });
          setErrors({});
          setProjectRoles({});
          setProjectSearch('');

          if (onInvitesSent) {
            const successfulEmails = invitationResults
              .filter(result => result.success)
              .map(result => result.email);
            onInvitesSent(successfulEmails);
          }
        }
      } catch (_error) {
        notifications.show('Failed to send invitations. Please try again.', {
          severity: 'error',
        });
      } finally {
        setIsSubmitting(false);
      }
    };

    const handleEmailChange = (invite: InviteItem, value: string) => {
      setFormData(prev => ({
        invites: prev.invites.map(i =>
          i.id === invite.id ? { ...i, email: value } : i
        ),
      }));

      if (errors[invite.id]) {
        const newErrors = { ...errors };
        delete newErrors[invite.id];
        setErrors(newErrors);
      }
    };

    const handleOrgRoleChange = (
      invite: InviteItem,
      orgRoleId: string | null
    ) => {
      setFormData(prev => ({
        invites: prev.invites.map(i =>
          i.id === invite.id ? { ...i, orgRoleId } : i
        ),
      }));
    };

    const addEmailField = () => {
      if (formData.invites.length >= MAX_TEAM_MEMBERS) {
        notifications.show(
          `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members at once.`,
          { severity: 'error' }
        );
        return;
      }

      setFormData({
        invites: [...formData.invites, createInvite()],
      });
    };

    const removeEmailField = (invite: InviteItem) => {
      setFormData(prev => ({
        invites: prev.invites.filter(i => i.id !== invite.id),
      }));

      if (errors[invite.id]) {
        const newErrors = { ...errors };
        delete newErrors[invite.id];
        setErrors(newErrors);
      }
    };

    return (
      <Box
        component="form"
        ref={ref}
        onSubmit={handleSubmit}
        sx={drawerSectionSx}
      >
        {/* Section A: Team members */}
        <Box sx={drawerSectionSx}>
          <FormSectionDivider
            headline="Team members"
            descriptiveText={`Invite up to ${MAX_TEAM_MEMBERS} colleagues to join your organization. Members without a project assigned see a no-access screen until an admin adds them.`}
          />
          <Box sx={drawerFieldsSx}>
            {formData.invites.map((invite, index) => (
              <Box
                key={invite.id}
                display="flex"
                alignItems="flex-start"
                gap={1.5}
              >
                <TextField
                  fullWidth
                  type="email"
                  label="Email Address"
                  value={invite.email}
                  onChange={e => handleEmailChange(invite, e.target.value)}
                  error={Boolean(errors[invite.id]?.hasError)}
                  helperText={errors[invite.id]?.message || ''}
                  placeholder="colleague@company.com"
                  variant="outlined"
                  sx={{
                    ...drawerOutlinedFieldSx,
                    flex: InviteOrgRoleField ? 1.4 : 1,
                  }}
                  data-tour={index === 0 ? 'invite-email-input' : undefined}
                />
                {InviteOrgRoleField && session?.session_token && (
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <InviteOrgRoleField
                      sessionToken={session.session_token}
                      value={invite.orgRoleId}
                      onChange={roleId => handleOrgRoleChange(invite, roleId)}
                      active={drawerOpen}
                    />
                  </Box>
                )}
                {formData.invites.length > 1 && (
                  <IconButton
                    onClick={() => removeEmailField(invite)}
                    color="error"
                    sx={{ mt: 1 }}
                  >
                    <DeleteIcon />
                  </IconButton>
                )}
              </Box>
            ))}

            <Button
              startIcon={<AddIcon />}
              onClick={addEmailField}
              variant="outlined"
              fullWidth
              disabled={formData.invites.length >= MAX_TEAM_MEMBERS}
              sx={drawerOutlineButtonSx}
            >
              {formData.invites.length >= MAX_TEAM_MEMBERS
                ? `Maximum ${MAX_TEAM_MEMBERS} invites reached`
                : 'Add Another Email'}
            </Button>
          </Box>
        </Box>

        {/* Section B: Project access */}
        <Box sx={drawerSectionSx}>
          <FormSectionDivider
            headline="Project access"
            descriptiveText="Invited users will only have access to the projects you select. Leave empty to invite without project access — an admin can add them later."
          />
          <Box>
            {availableProjects.length === 0 ? (
              <Typography variant="body2" color="text.disabled">
                No projects available
              </Typography>
            ) : (
              <>
                <TextField
                  value={projectSearch}
                  onChange={e => setProjectSearch(e.target.value)}
                  placeholder="Search projects…"
                  fullWidth
                  sx={{ ...drawerOutlinedFieldSx, mb: 1 }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon
                            fontSize="small"
                            sx={{ color: 'text.secondary' }}
                          />
                        </InputAdornment>
                      ),
                    },
                  }}
                />
                <List
                  disablePadding
                  sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}
                >
                  {availableProjects
                    .filter(p =>
                      p.name.toLowerCase().includes(projectSearch.toLowerCase())
                    )
                    .map(project => {
                      const projectId = String(project.id);
                      const isSelected = projectId in projectRoles;
                      return (
                        <ListItemButton
                          key={projectId}
                          onClick={() =>
                            setProjectRoles(prev => {
                              if (isSelected) {
                                const next = { ...prev };
                                delete next[projectId];
                                return next;
                              }
                              return { ...prev, [projectId]: null };
                            })
                          }
                          sx={getSelectableProjectItemSx(isSelected)}
                        >
                          <Avatar sx={projectAvatarSx}>
                            {getProjectIcon(project)}
                          </Avatar>
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography
                              variant="body2"
                              sx={getSelectableProjectNameSx(isSelected)}
                            >
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
                          {isSelected &&
                            AddMemberRoleField &&
                            session?.session_token && (
                              <Box sx={{ flexShrink: 0 }}>
                                <AddMemberRoleField
                                  sessionToken={session.session_token}
                                  value={projectRoles[projectId] ?? null}
                                  onChange={roleId =>
                                    setProjectRoles(prev => ({
                                      ...prev,
                                      [projectId]: roleId,
                                    }))
                                  }
                                  size="small"
                                  active={drawerOpen}
                                />
                              </Box>
                            )}
                        </ListItemButton>
                      );
                    })}
                </List>
                {projectSearch &&
                  !availableProjects.some(p =>
                    p.name.toLowerCase().includes(projectSearch.toLowerCase())
                  ) && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ textAlign: 'center', pt: 1 }}
                    >
                      No projects match your search.
                    </Typography>
                  )}
              </>
            )}
          </Box>
        </Box>

        {!embedded && (
          <Box display="flex" justifyContent="flex-end">
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={isSubmitting || disableDuringTour}
              startIcon={
                isSubmitting ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  <SendIcon />
                )
              }
              data-tour="send-invites-button"
            >
              {isSubmitting ? 'Sending Invitations...' : 'Send Invitations'}
            </Button>
          </Box>
        )}
      </Box>
    );
  }
);

export default TeamInviteForm;
