'use client';

import React from 'react';
import { Box, Skeleton } from '@mui/material';
import { useRouter } from 'next/navigation';
import EntityCard, {
  EntityCardStatusBadge,
  type ChipSection,
} from '@/components/common/EntityCard';
import { Project } from '@/utils/api-client/interfaces/project';
import { BORDER_RADIUS } from '@/styles/theme';
import type { Theme } from '@mui/material/styles';

// Project icon imports
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
import SmartToyIcon from '@mui/icons-material/SmartToy';
import DevicesIcon from '@mui/icons-material/Devices';

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

function getProjectIcon(project: Project): React.ReactElement {
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
}

export const ProjectCardSkeleton = () => (
  <Box
    sx={{
      border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
      borderRadius: BORDER_RADIUS.md,
      p: 3.75,
      display: 'flex',
      flexDirection: 'column',
      gap: 1.5,
      height: '100%',
    }}
  >
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
      <Skeleton variant="circular" width={24} height={24} />
      <Skeleton variant="text" width="60%" height={25} />
    </Box>
    <Skeleton variant="text" width="100%" />
    <Skeleton variant="text" width="80%" />
    <Skeleton variant="rounded" width="40%" height={24} sx={{ mt: 1 }} />
  </Box>
);

interface ProjectCardProps {
  project: Project;
  isLoading?: boolean;
  onDelete?: () => void;
}

const ProjectCard = React.memo(
  ({ project, isLoading = false, onDelete }: ProjectCardProps) => {
    const router = useRouter();

    if (isLoading) {
      return <ProjectCardSkeleton />;
    }

    const chipSections: ChipSection[] = [];

    const projectStatus =
      project.is_active === true
        ? 'active'
        : project.is_active === false
          ? 'inactive'
          : undefined;

    chipSections.push({
      label: 'Status',
      chips: [],
      customContent: projectStatus ? (
        <EntityCardStatusBadge status={projectStatus} />
      ) : undefined,
      emptyText: 'No status set',
    });

    if (project.environment !== undefined) {
      chipSections.push({
        label: 'Environment',
        chips: project.environment
          ? [{ key: 'env', label: project.environment }]
          : [],
        emptyText: 'No environment set',
      });
    }

    return (
      <EntityCard
        icon={getProjectIcon(project)}
        title={project.name}
        description={project.description}
        onClick={() => router.push(`/projects/${project.id}`)}
        onDelete={onDelete}
        userAvatar={project.owner?.picture}
        userName={project.owner?.name}
        chipSections={chipSections}
      />
    );
  }
);

ProjectCard.displayName = 'ProjectCard';

export default ProjectCard;
