'use client';

import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { Task } from '@/types/tasks';
import { useNotifications } from '@/components/common/NotificationContext';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import SvgIcon, { type SvgIconProps } from '@mui/material/SvgIcon';
import { Fab, FabGroup } from '@/components/common/Fab';

const JiraIcon = (props: SvgIconProps) => (
  <SvgIcon {...props} viewBox="0 0 24 24">
    <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.004-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0z" />
  </SvgIcon>
);

interface CreateJiraIssueButtonProps {
  task: Task;
  onIssueCreated?: () => void;
}

export default function CreateJiraIssueButton({
  task,
  onIssueCreated,
}: CreateJiraIssueButtonProps) {
  const { data: session } = useSession();
  const { show } = useNotifications();
  const [jiraTools, setJiraTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const hasJiraIssue = Boolean(task.task_metadata?.jira_issue);
  const jiraIssue = task.task_metadata?.jira_issue as
    | {
        issue_key: string;
        issue_url: string;
      }
    | undefined;

  useEffect(() => {
    const fetchJiraTools = async () => {
      if (!session?.session_token) return;

      setLoading(true);
      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const toolsClient = clientFactory.getToolsClient();

        const response = await toolsClient.getTools({});
        const tools = response.data || [];

        const jiraToolsList = tools.filter(
          tool =>
            tool.tool_provider_type?.type_value === 'jira' &&
            tool.tool_metadata?.space_key
        );

        setJiraTools(jiraToolsList);
      } catch {
        // Silently fail - button will not render if no tools available
      } finally {
        setLoading(false);
      }
    };

    fetchJiraTools();
  }, [session?.session_token]);

  const handleCreateIssue = async (toolId?: string) => {
    const selectedToolId = toolId || jiraTools[0]?.id;
    if (!selectedToolId) return;

    if (!session?.session_token) {
      show('Session not available', { severity: 'error' });
      return;
    }

    setIsCreating(true);
    try {
      const clientFactory = new ApiClientFactory(session.session_token);
      const servicesClient = clientFactory.getServicesClient();

      const result = await servicesClient.createJiraTicketFromTask(
        task.id,
        selectedToolId
      );

      show(result.message || 'Jira issue created successfully', {
        severity: 'success',
      });

      if (onIssueCreated) {
        onIssueCreated();
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to create Jira issue';
      show(errorMessage, { severity: 'error' });
    } finally {
      setIsCreating(false);
    }
  };

  const handleOpenJiraIssue = () => {
    if (jiraIssue?.issue_url) {
      window.open(jiraIssue.issue_url, '_blank');
    }
  };

  const handleClick = () => {
    handleCreateIssue(jiraTools[0]?.id);
  };

  if (hasJiraIssue && jiraIssue) {
    return (
      <FabGroup>
        <Fab
          icon={<OpenInNewIcon />}
          tooltip={
            jiraIssue.issue_key
              ? `View ${jiraIssue.issue_key} in Jira`
              : 'View in Jira'
          }
          aria-label="View in Jira"
          onClick={handleOpenJiraIssue}
        />
      </FabGroup>
    );
  }

  const hasNoJiraTools = !loading && jiraTools.length === 0;

  const tooltip = hasNoJiraTools
    ? 'Connect Jira in Connect → Tools to create issues from this task'
    : loading
      ? 'Loading Jira tools…'
      : isCreating
        ? 'Creating Jira issue…'
        : 'Create Jira Issue';

  return (
    <>
      <FabGroup>
        <Fab
          icon={<JiraIcon />}
          tooltip={tooltip}
          aria-label="Create Jira Issue"
          onClick={handleClick}
          disabled={hasNoJiraTools}
          loading={loading || isCreating}
        />
      </FabGroup>
    </>
  );
}
