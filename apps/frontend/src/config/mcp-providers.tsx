import React from 'react';
import {
  SiNotion,
  SiGithub,
  SiGoogledrive,
} from '@icons-pack/react-simple-icons';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import StorageIcon from '@mui/icons-material/Storage';

/**
 * MCP Provider Configuration
 *
 * This file contains all configuration related to MCP providers including:
 * - Supported providers
 * - Provider icons and branding
 */

// MCP providers currently supported
export const SUPPORTED_MCP_PROVIDERS = ['notion', 'github', 'gdrive', 'google'];

// Provider icon mapping
export const MCP_PROVIDER_ICONS: Record<string, React.ReactNode> = {
  notion: <SiNotion className="h-8 w-8" />,
  github: <SiGithub className="h-8 w-8" />,
  gdrive: <SiGoogledrive className="h-8 w-8" />,
  google: <StorageIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  custom: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
};

// Provider information interface
export interface MCPProviderInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}
