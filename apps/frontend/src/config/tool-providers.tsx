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
 * - Supported providers
 * - Provider icons and branding
 */

// Tool providers currently supported
// These must match the ToolProviderType values defined in the backend
export const SUPPORTED_TOOL_PROVIDERS = [
  'notion',
  'github',
  'jira',
  'confluence',
];

// Provider icon mapping
export const TOOL_PROVIDER_ICONS: Record<string, React.ReactNode> = {
  notion: <SiNotion className="h-8 w-8" />,
  github: <SiGithub className="h-8 w-8" />,
  jira: <SiJira className="h-8 w-8" />,
  confluence: <SiConfluence className="h-8 w-8" />,
};

// Provider information interface
export interface ToolProviderInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}
