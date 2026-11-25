'use client';

import React from 'react';
import { useTheme } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import { useRouter } from 'next/navigation';
import EntityCard, {
  skeletonCardKeys,
  type EntityCardFact,
} from '@/components/common/EntityCard';
import { Project } from '@/utils/api-client/interfaces/project';
import { alpha } from '@mui/material/styles';

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

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1);

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

interface ProjectCardProps {
  project: Project;
  onDelete?: () => void;
  /** When set, the trash can renders disabled with this as its tooltip. */
  deleteDisabledReason?: string;
  /** Marks the project currently scoping the app. */
  isActive?: boolean;
}

const ProjectCard = React.memo(
  ({
    project,
    onDelete,
    deleteDisabledReason,
    isActive = false,
  }: ProjectCardProps) => {
    const router = useRouter();
    const theme = useTheme();

    const facts: EntityCardFact[] = [];
    if (project.is_active !== undefined) {
      facts.push({
        key: 'status',
        kind: 'state',
        label: project.is_active ? 'Active' : 'Inactive',
        tone: project.is_active ? 'success' : 'error',
      });
    }
    if (project.environment) {
      facts.push({
        key: 'environment',
        kind: 'plain',
        label: capitalize(project.environment),
      });
    }

    return (
      <EntityCard
        icon={getProjectIcon(project)}
        title={project.name}
        description={project.description}
        onClick={() => router.push(`/projects/${project.id}`)}
        onDelete={onDelete}
        deleteDisabledReason={deleteDisabledReason}
        deleteLabel="Delete project"
        topRightActions={
          isActive ? (
            <GridBadge
              size="detail"
              label="Current"
              sx={{
                bgcolor: alpha(theme.palette.primary.main, 0.12),
                color: 'primary.main',
              }}
            />
          ) : undefined
        }
        // EntityCard builds its border from a template string, so it needs a
        // real colour value, not a palette key.
        borderColor={isActive ? theme.palette.primary.main : undefined}
        userAvatar={project.owner?.picture}
        userName={project.owner?.name}
        facts={facts}
      />
    );
  }
);

ProjectCard.displayName = 'ProjectCard';

export default ProjectCard;

/** Typical values for a loading view's cards, only the fields the card reads. */
const PLACEHOLDER_PROJECT = {
  id: '00000000-0000-0000-0000-000000000000',
  name: 'Project name',
  is_active: true,
  environment: 'development',
  owner: { name: 'Owner' },
} as unknown as Project;

/**
 * A loading view's cards: the real card in skeleton mode. `canDelete` follows
 * the page's own permission, so the delete placeholder shows only for users
 * who get the button.
 */
export function ProjectCardPlaceholders({ canDelete }: { canDelete: boolean }) {
  return (
    <>
      {skeletonCardKeys.map(key => (
        <ProjectCard
          key={key}
          project={PLACEHOLDER_PROJECT}
          onDelete={canDelete ? () => {} : undefined}
        />
      ))}
    </>
  );
}
