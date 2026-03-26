'use client';

import React from 'react';
import { Card, CardContent, Typography, Skeleton, Box } from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';

import SmartToyIcon from '@mui/icons-material/SmartToy';
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

const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Devices: SmartToyIcon,
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

const getProjectIcon = (project: Project) => {
  if (project.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }
  if (project.useCase) {
    switch (project.useCase.toLowerCase()) {
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
  return <SmartToyIcon />;
};

export const ProjectCardSkeleton = () => (
  <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
    <CardContent sx={{ p: 3.75, '&:last-child': { pb: 3.75 } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 1.25 }}>
        <Skeleton variant="circular" width={24} height={24} />
        <Skeleton variant="text" width="70%" />
      </Box>
      <Skeleton variant="text" width="100%" />
      <Skeleton variant="text" width="80%" sx={{ mb: 2.5 }} />
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 2.5 }}>
        <Skeleton variant="circular" width={24} height={24} />
        <Skeleton variant="text" width="30%" />
      </Box>
      <Skeleton variant="rounded" width="25%" height={24} sx={{ mb: 2 }} />
      <Skeleton variant="rectangular" width="100%" height={1} sx={{ mb: 2 }} />
      <Skeleton variant="text" width="40%" sx={{ mb: 1 }} />
      <Box sx={{ display: 'flex', gap: 0.75 }}>
        <Skeleton variant="rounded" width={60} height={22} />
        <Skeleton variant="rounded" width={80} height={22} />
      </Box>
    </CardContent>
  </Card>
);

interface ProjectCardProps {
  project: Project;
  isLoading?: boolean;
  onClick?: () => void;
}

const ProjectCard = React.memo(
  ({ project, isLoading = false, onClick }: ProjectCardProps) => {
    if (isLoading) {
      return <ProjectCardSkeleton />;
    }

    const chipSections: ChipSection[] = [];

    const propertyChips = [];
    if (project.environment) {
      propertyChips.push({
        key: 'environment',
        label: project.environment,
      });
    }
    if (project.useCase) {
      propertyChips.push({
        key: 'useCase',
        label: project.useCase,
      });
    }
    if (project.tags && project.tags.length > 0) {
      project.tags.slice(0, 4).forEach((tag, i) => {
        propertyChips.push({ key: `tag-${i}`, label: tag });
      });
      if (project.tags.length > 4) {
        propertyChips.push({
          key: 'more-tags',
          label: `+${project.tags.length - 4}`,
        });
      }
    }

    if (propertyChips.length > 0) {
      chipSections.push({ label: 'Properties', chips: propertyChips });
    }

    return (
      <EntityCard
        icon={getProjectIcon(project)}
        title={project.name}
        description={
          project.description
            ? project.description.length > 200
              ? `${project.description.substring(0, 200)}...`
              : project.description
            : 'No description provided'
        }
        ownerName={project.owner?.name}
        ownerAvatar={project.owner?.picture}
        statusLabel={
          project.is_active !== undefined
            ? project.is_active
              ? 'Active'
              : 'Inactive'
            : undefined
        }
        statusColor={
          project.is_active !== undefined
            ? project.is_active
              ? 'success'
              : 'error'
            : undefined
        }
        chipSections={chipSections}
        onClick={onClick}
      />
    );
  }
);

ProjectCard.displayName = 'ProjectCard';

export default ProjectCard;
