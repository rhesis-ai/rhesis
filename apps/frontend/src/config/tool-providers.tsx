import React from 'react';
import {
  SiNotion,
  SiGithub,
  SiJira,
  SiGitlab,
  SiShortcut,
  SiLinear,
  SiAsana,
  SiTrello,
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
  'azure_devops',
  'linear',
  'trello',
];

const TOOL_PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  azure_devops: 'Azure DevOps',
};

export function formatToolProviderDisplayName(typeValue: string): string {
  return (
    TOOL_PROVIDER_DISPLAY_NAMES[typeValue] ??
    typeValue.charAt(0).toUpperCase() + typeValue.slice(1)
  );
}

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
  linear:
    'Import issues and project context from Linear into your knowledge base',
  azure_devops:
    'Import work items, epics, and user stories from Azure DevOps boards',
  trello:
    'Import boards, lists, and cards from Trello into your knowledge base',
};

/**
 * Azure DevOps has no icon in `react-simple-icons`, so it is drawn here.
 *
 * The explicit size matters: an `<svg>` with only a `viewBox` has no intrinsic
 * dimensions and expands to fill whatever contains it. The other icons carry
 * their own default, so leaving this one unsized made it the odd one out and
 * blew out the tile it sat in.
 */
/** Matches `theme.iconSizes.medium`, which is what the tiles and cards use. */
const PROVIDER_ICON_SIZE = 24;

function AzureDevOpsIcon({ size = 24 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role="img"
      aria-label="Azure DevOps"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fill="currentColor"
        d="M21 4.6v12.3l-5 4.1-7.8-2.8v2.8L3.9 17.4l11.4.9V5.1L21 4.6zM15.5 6 8.2 8.9v6.2L3 13.2V8.5l5.2-2.1L15.5 3v3z"
      />
    </svg>
  );
}

// Provider icon mapping
/**
 * Provider icon mapping.
 *
 * Every entry renders at the same size. These previously carried `h-8 w-8`,
 * Tailwind classes that did nothing because this project styles with MUI, so
 * each icon silently fell back to whatever it shipped with.
 */
export const TOOL_PROVIDER_ICONS: Record<string, React.ReactNode> = {
  notion: <SiNotion size={PROVIDER_ICON_SIZE} />,
  github: <SiGithub size={PROVIDER_ICON_SIZE} />,
  jira: <SiJira size={PROVIDER_ICON_SIZE} />,
  gitlab: <SiGitlab size={PROVIDER_ICON_SIZE} />,
  shortcut: <SiShortcut size={PROVIDER_ICON_SIZE} />,
  asana: <SiAsana size={PROVIDER_ICON_SIZE} />,
  linear: <SiLinear size={PROVIDER_ICON_SIZE} />,
  azure_devops: <AzureDevOpsIcon size={PROVIDER_ICON_SIZE} />,
  trello: <SiTrello size={PROVIDER_ICON_SIZE} />,
};
