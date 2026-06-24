import React from 'react';
import {
  SiNotion,
  SiGithub,
  SiJira,
  SiGitlab,
  SiShortcut,
} from '@icons-pack/react-simple-icons';

/**
 * Tool Provider Configuration
 *
 * This file contains all configuration related to tool providers including:
 * - Supported providers (aligned with backend ToolProviderType values)
 * - Provider icons and branding
 */

// Providers that support the extract action (REST or MCP — backend picks transport).
// Must stay in sync with _ROUTES in apps/backend/.../services/tool/actions.py.
export const EXTRACT_PROVIDERS = [
  'notion',
  'github',
  'gitlab',
  'shortcut',
  'asana',
];

/** @deprecated Use EXTRACT_PROVIDERS */
export const REST_PROVIDERS = EXTRACT_PROVIDERS;

// Short description of what each provider is used for in Rhesis
export const TOOL_PROVIDER_DESCRIPTIONS: Record<string, string> = {
  notion: 'Pull pages and databases into your knowledge base as test context',
  github: 'Pull files and docs from your repositories into your knowledge base',
  jira: 'Create Jira issues directly from Rhesis tasks',
  gitlab: 'Import issues, merge requests, and wiki pages from GitLab projects',
  shortcut: 'Import stories and epics from Shortcut into your knowledge base',
  asana: 'Import tasks and projects from Asana into your knowledge base',
};

function AsanaIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label="Asana"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="6" r="3.5" fill="#F06A6A" />
      <circle cx="5.5" cy="16" r="3.5" fill="#F06A6A" />
      <circle cx="18.5" cy="16" r="3.5" fill="#F06A6A" />
    </svg>
  );
}

// Provider icon mapping
export const TOOL_PROVIDER_ICONS: Record<string, React.ReactNode> = {
  notion: <SiNotion className="h-8 w-8" />,
  github: <SiGithub className="h-8 w-8" />,
  jira: <SiJira className="h-8 w-8" />,
  gitlab: <SiGitlab className="h-8 w-8" />,
  shortcut: <SiShortcut className="h-8 w-8" />,
  asana: <AsanaIcon className="h-8 w-8" />,
};
