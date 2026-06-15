import React from 'react';
import {
  SiNotion,
  SiGithub,
  SiJira,
  SiConfluence,
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
  notion: 'Import pages and databases as knowledge sources',
  github: 'Import files and documentation from repositories',
  gitlab: 'Import files and documentation from GitLab repositories',
  jira: 'Import issues and project backlogs',
  confluence: 'Import pages and spaces as knowledge sources',
  asana: 'Import tasks and project briefs',
  shortcut: 'Import stories and epics as knowledge sources',
};

// Provider icon mapping
export const TOOL_PROVIDER_ICONS: Record<string, React.ReactNode> = {
  notion: <SiNotion className="h-8 w-8" />,
  github: <SiGithub className="h-8 w-8" />,
  jira: <SiJira className="h-8 w-8" />,
  confluence: <SiConfluence className="h-8 w-8" />,
};
