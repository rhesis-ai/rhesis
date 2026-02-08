'use client';

import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import {
  Button,
  CircularProgress,
  Menu,
  MenuItem,
  Typography,
  Tooltip,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { Task } from '@/types/tasks';
import { useNotifications } from '@/components/common/NotificationContext';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import SvgIcon from '@mui/material/SvgIcon';

// Jira icon component
const JiraIcon = (props: any) => (
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
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  // Check if task already has a Jira issue
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

        // Fetch all tools and filter by Jira provider
        const response = await toolsClient.getTools({});
        const tools = response.data || [];

        // Filter for Jira tools that have space_key configured
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
    // Close menu if open
    setAnchorEl(null);

    // Use the first tool if no toolId provided
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

      // Notify parent to refetch task
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

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    if (jiraTools.length === 1) {
      // If only one tool, create issue directly
      handleCreateIssue(jiraTools[0].id);
    } else {
      // Show menu to select project
      setAnchorEl(event.currentTarget);
    }
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
  };

  // If task already has a Jira issue, show "View in Jira" button
  if (hasJiraIssue && jiraIssue) {
    return (
      <Button
        variant="outlined"
        size="small"
        onClick={handleOpenJiraIssue}
        startIcon={<OpenInNewIcon />}
        sx={{
          textTransform: 'none',
        }}
      >
        View in Jira
      </Button>
    );
  }

  // If no Jira tools available, show disabled button with tooltip
  const hasNoJiraTools = !loading && jiraTools.length === 0;

  // Show "Create Jira Issue" button
  return (
    <>
      <Tooltip
        title={
          hasNoJiraTools ? 'Go to MCP -> Add Jira tool to create issues' : ''
        }
        arrow
      >
        <span>
          <Button
            variant="outlined"
            size="small"
            onClick={handleClick}
            disabled={isCreating || loading || hasNoJiraTools}
            startIcon={
              loading ? (
                <CircularProgress size={16} />
              ) : isCreating ? (
                <CircularProgress size={16} />
              ) : (
                <JiraIcon />
              )
            }
            endIcon={
              !hasNoJiraTools && jiraTools.length > 1 ? (
                <ArrowDropDownIcon />
              ) : undefined
            }
            sx={{
              textTransform: 'none',
              '&.Mui-disabled': {
                color: 'text.secondary',
                borderColor: 'divider',
              },
            }}
          >
            {loading
              ? 'Loading...'
              : isCreating
                ? 'Creating...'
                : 'Create Jira Issue'}
          </Button>
        </span>
      </Tooltip>

      {/* Dropdown menu for multiple tools */}
      {jiraTools.length > 1 && (
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleCloseMenu}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
        >
          {jiraTools.map(tool => (
            <MenuItem
              key={tool.id}
              onClick={() => handleCreateIssue(tool.id)}
              sx={{ minWidth: 200 }}
            >
              <Typography variant="body2">
                {tool.tool_metadata?.space_key || tool.name}
              </Typography>
            </MenuItem>
          ))}
        </Menu>
      )}
    </>
  );
}
