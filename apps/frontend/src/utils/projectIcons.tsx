import React from 'react';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import DevicesIcon from '@mui/icons-material/Devices';
import WebIcon from '@mui/icons-material/Web';
import StorageIcon from '@mui/icons-material/Storage';
import CodeIcon from '@mui/icons-material/Code';
import DataObjectIcon from '@mui/icons-material/DataObject';
import CloudIcon from '@mui/icons-material/Cloud';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import TerminalIcon from '@mui/icons-material/Terminal';
import VideogameAssetIcon from '@mui/icons-material/VideogameAsset';
import ChatIcon from '@mui/icons-material/Chat';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import SchoolIcon from '@mui/icons-material/School';
import ScienceIcon from '@mui/icons-material/Science';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { Project } from '@/utils/api-client/interfaces/project';

// Map of icon names to components for easy lookup
const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Devices: DevicesIcon,
  Web: WebIcon,
  Storage: StorageIcon,
  Code: CodeIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  ShoppingCart: ShoppingCartIcon,
  Terminal: TerminalIcon,
  VideogameAsset: VideogameAssetIcon,
  Chat: ChatIcon,
  Psychology: PsychologyIcon,
  Dashboard: DashboardIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

/**
 * Get the appropriate icon component for a project
 * @param project - Project object or icon name
 * @param useCase - Optional use case fallback
 * @returns Icon component
 */
export const getProjectIcon = (
  project?: Project | { icon?: string; useCase?: string } | string,
  useCase?: string
) => {
  // If project is a string, treat it as an icon name
  if (typeof project === 'string') {
    const IconComponent = ICON_MAP[project];
    return IconComponent ? <IconComponent /> : <SmartToyIcon />;
  }

  // If project is undefined, return default
  if (!project) {
    return <SmartToyIcon />;
  }

  // Check if a specific project icon was selected
  if (project.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }

  // Fall back to useCase-based icons if no specific icon is set
  const projectUseCase = project.useCase || useCase;
  if (projectUseCase) {
    switch (projectUseCase.toLowerCase()) {
      case 'chatbot':
        return <ChatIcon />;
      case 'assistant':
        return <PsychologyIcon />;
      case 'advisor':
        return <SmartToyIcon />;
      default:
        return <SmartToyIcon />;
    }
  }

  // Default icon
  return <SmartToyIcon />;
};

/**
 * Get the icon component class for a project
 * @param project - Project object or icon name
 * @param useCase - Optional use case fallback
 * @returns Icon component class
 */
export const getProjectIconComponent = (
  project?: Project | { icon?: string; useCase?: string } | string,
  useCase?: string
): React.ComponentType => {
  // If project is a string, treat it as an icon name
  if (typeof project === 'string') {
    return ICON_MAP[project] || SmartToyIcon;
  }

  // If project is undefined, return default
  if (!project) {
    return SmartToyIcon;
  }

  // Check if a specific project icon was selected
  if (project.icon && ICON_MAP[project.icon]) {
    return ICON_MAP[project.icon];
  }

  // Fall back to useCase-based icons if no specific icon is set
  const projectUseCase = project.useCase || useCase;
  if (projectUseCase) {
    switch (projectUseCase.toLowerCase()) {
      case 'chatbot':
        return ChatIcon;
      case 'assistant':
        return PsychologyIcon;
      case 'advisor':
        return SmartToyIcon;
      default:
        return SmartToyIcon;
    }
  }

  // Default icon
  return SmartToyIcon;
};
