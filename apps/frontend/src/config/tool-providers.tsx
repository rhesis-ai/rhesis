import React from 'react';
import {
  SiNotion,
  SiGithub,
  SiJira,
  SiGitlab,
} from '@icons-pack/react-simple-icons';

/**
 * Tool Provider Configuration
 *
 * This file contains all configuration related to tool providers including:
 * - Supported providers (aligned with backend ToolProviderType values)
 * - Provider icons and branding
 */

// Providers supported via the deterministic REST extract path.
// Must match ToolProviderType values defined in the backend.
export const REST_PROVIDERS = ['notion', 'github'];

// Short description of what each provider is used for in Rhesis
export const TOOL_PROVIDER_DESCRIPTIONS: Record<string, string> = {
  notion: 'Pull pages and databases into your knowledge base as test context',
  github: 'Pull files and docs from your repositories into your knowledge base',
  jira: 'Create Jira issues directly from Rhesis tasks',
  gitlab: 'Import issues, merge requests, and wiki pages from GitLab projects',
};

// Provider icon mapping
export const TOOL_PROVIDER_ICONS: Record<string, React.ReactNode> = {
  notion: <SiNotion className="h-8 w-8" />,
  github: <SiGithub className="h-8 w-8" />,
  jira: <SiJira className="h-8 w-8" />,
  gitlab: <SiGitlab className="h-8 w-8" />,
};
