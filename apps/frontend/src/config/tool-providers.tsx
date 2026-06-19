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

// Providers supported via the deterministic REST extract path.
// Must match ToolProviderType values defined in the backend.
export const REST_PROVIDERS = ['notion', 'github'];

// Short description of what each provider is used for in Rhesis
export const TOOL_PROVIDER_DESCRIPTIONS: Record<string, string> = {
  notion: 'Pull pages and databases into your knowledge base as test context',
  github: 'Pull files and docs from your repositories into your knowledge base',
  jira: 'Create Jira issues directly from Rhesis tasks',
  gitlab: 'Import issues, merge requests, and wiki pages from GitLab projects',
  shortcut: 'Import stories and epics from Shortcut into your knowledge base',
  asana: 'Import tasks and projects from Asana into your knowledge base',
  linear: 'Import issues and project context from Linear into your knowledge base',
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

function LinearIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label="Linear"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fill="#5E6AD2"
        d="M3.035 5.482a1 1 0 0 1 1.414 0L12 13.033l7.551-7.551a1 1 0 1 1 1.414 1.414L13.414 14.447v5.138a1 1 0 1 1-2 0v-5.138L3.035 6.896a1 1 0 0 1 0-1.414z"
      />
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
  linear: <LinearIcon className="h-8 w-8" />,
};
