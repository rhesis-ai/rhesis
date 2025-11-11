'use client';

import React, {
  useMemo,
  useCallback,
  useState,
  useEffect,
  useRef,
} from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  Chip,
  Button,
  Avatar,
  Divider,
  Stack,
  CardHeader,
  useTheme,
  Skeleton,
  Tooltip,
} from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import VisibilityIcon from '@mui/icons-material/Visibility';
import EditIcon from '@mui/icons-material/Edit';
import FolderIcon from '@mui/icons-material/Folder';
import DevicesIcon from '@mui/icons-material/Devices';
import PersonIcon from '@mui/icons-material/Person';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DoNotDisturbAltIcon from '@mui/icons-material/DoNotDisturbAlt';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import DescriptionIcon from '@mui/icons-material/Description';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { useRouter } from 'next/navigation';

// Import all the available project icons
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

// Memoize utility functions
const getEnvironmentColor = (environment?: string) => {
  if (!environment) return 'default';

  switch (environment.toLowerCase()) {
    case 'production':
      return 'success';
    case 'staging':
      return 'warning';
    case 'development':
      return 'info';
    default:
      return 'default';
  }
};

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

// Get appropriate icon based on project type or use case
const getProjectIcon = (project: Project) => {
  // Check if a specific project icon was selected during creation
  if (project.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }

  // Fall back to useCase-based icons if no specific icon is set
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

  // Default icon
  return <SmartToyIcon />;
};

interface ProjectCardProps {
  project: Project;
  isLoading?: boolean;
}

// Create a skeleton loader for the card
const ProjectCardSkeleton = () => (
  <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
    <CardHeader
      avatar={<Skeleton variant="circular" width={40} height={40} />}
      title={<Skeleton variant="text" width="80%" />}
    />
    <Divider />
    <CardContent sx={{ flexGrow: 1 }}>
      <Skeleton variant="text" width="100%" />
      <Skeleton variant="text" width="60%" />
      <Skeleton
        variant="rounded"
        width="40%"
        height={24}
        sx={{ mt: 2, mb: 2 }}
      />
      <Skeleton variant="rounded" width="60%" height={24} sx={{ mb: 2 }} />
    </CardContent>
    <Divider />
    <CardActions sx={{ justifyContent: 'flex-end', p: 1.5 }}>
      <Skeleton variant="rounded" width={80} height={36} sx={{ mr: 1 }} />
      <Skeleton variant="rounded" width={80} height={36} />
    </CardActions>
  </Card>
);

const ProjectCard = React.memo(
  ({ project, isLoading = false }: ProjectCardProps) => {
    const router = useRouter();
    const theme = useTheme();
    const titleRef = useRef<HTMLSpanElement>(null);
    const cardHeaderRef = useRef<HTMLDivElement>(null);
    const [isTruncated, setIsTruncated] = useState(false);

    // Check if text is truncated
    useEffect(() => {
      const checkTruncation = () => {
        // Use a small timeout to ensure DOM is fully rendered and styled
        setTimeout(() => {
          if (cardHeaderRef.current) {
            // Find the actual Typography element with noWrap styling
            const typographyElement = cardHeaderRef.current.querySelector(
              '.MuiCardHeader-content .MuiTypography-root'
            );
            if (typographyElement) {
              const isOverflowing =
                typographyElement.scrollWidth > typographyElement.clientWidth;
              setIsTruncated(isOverflowing);
            }
          }
        }, 10);
      };

      // Check on mount and when project name changes
      checkTruncation();

      // Also check on window resize
      const handleResize = () => {
        setTimeout(checkTruncation, 100);
      };

      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }, [project.name]);

    // Memoize handlers to prevent unnecessary rerenders
    const handleViewClick = useCallback(() => {
      router.push(`/projects/${project.id}`);
    }, [router, project.id]);

    const handleEditClick = useCallback(() => {
      router.push(`/projects/${project.id}/edit`);
    }, [router, project.id]);

    // Memoize theme color getter
    const getThemeColor = useCallback(
      (name: string | undefined) => {
        const themeColors = [theme.palette.primary.main];
        // Use a default character if name is undefined
        const index =
          (name ? name.charCodeAt(0) : 'A'.charCodeAt(0)) % themeColors.length;
        return themeColors[index];
      },
      [theme]
    );

    // Memoize card components for better performance
    const cardHeader = useMemo(
      () => (
        <CardHeader
          ref={cardHeaderRef}
          avatar={
            <Avatar
              sx={{
                bgcolor: getThemeColor(project.name),
                width: 40,
                height: 40,
              }}
            >
              {getProjectIcon(project)}
            </Avatar>
          }
          title={
            isTruncated ? (
              <Tooltip title={project.name} arrow placement="top">
                <span style={{ cursor: 'help' }}>{project.name}</span>
              </Tooltip>
            ) : (
              <span>{project.name}</span>
            )
          }
          titleTypographyProps={{
            variant: 'h6',
            component: 'div',
            noWrap: true,
            sx: {
              fontWeight: 'medium',
            },
          }}
          sx={{
            pb: 1,
            display: 'flex',
            overflow: 'hidden',
            '& .MuiCardHeader-content': {
              overflow: 'hidden',
            },
          }}
        />
      ),
      [project, getThemeColor, isTruncated]
    );

    // Memoize tag rendering
    const renderTags = useMemo(() => {
      if (!project.tags || project.tags.length === 0) return null;

      return (
        <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
          <LocalOfferIcon
            sx={{
              fontSize: theme => theme.iconSizes.medium,
              color: 'text.secondary',
              mr: 1,
              mt: 0.3,
            }}
          />
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {project.tags.slice(0, 3).map(tag => (
              <Chip
                key={tag}
                label={tag}
                size="small"
                variant="outlined"
                color="secondary"
              />
            ))}
            {project.tags.length > 3 && (
              <Chip
                label={`+${project.tags.length - 3}`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        </Box>
      );
    }, [project.tags]);

    // If loading, show skeleton
    if (isLoading) {
      return <ProjectCardSkeleton />;
    }

    return (
      <Card
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          transition: 'all 0.2s ease-in-out',
          borderRadius: theme => theme.shape.borderRadius * 0.5,
          overflow: 'hidden',
        }}
        elevation={2}
      >
        {/* Header Section */}
        {cardHeader}

        <Divider />

        {/* Main Content Section - Simplified with straightforward layout */}
        <CardContent sx={{ flexGrow: 1, pt: 2, pb: 1 }}>
          {/* Description with icon */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
            <DescriptionIcon
              sx={{
                fontSize: theme => theme.iconSizes.medium,
                color: 'text.secondary',
                mr: 1,
                mt: 0.3,
              }}
            />
            <Typography variant="body2">
              {project.description
                ? project.description.length > 250
                  ? `${project.description.substring(0, 250)}...`
                  : project.description
                : 'No description provided'}
            </Typography>
          </Box>

          {/* Owner Information */}
          {project.owner && (
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Avatar
                src={project.owner.picture}
                alt={project.owner.name}
                sx={{ width: 24, height: 24, mr: 1 }}
              />
              <Typography variant="body2">{project.owner.name}</Typography>
            </Box>
          )}

          {/* Active Status Chip */}
          {project.is_active !== undefined && (
            <Box sx={{ mb: 2 }}>
              <Chip
                icon={
                  project.is_active ? (
                    <CheckCircleIcon fontSize="small" />
                  ) : (
                    <DoNotDisturbAltIcon fontSize="small" />
                  )
                }
                label={project.is_active ? 'Active' : 'Inactive'}
                size="small"
                color={project.is_active ? 'success' : 'error'}
                variant="outlined"
              />
            </Box>
          )}

          {/* Environment Chip - if needed */}
          {project.environment && (
            <Box sx={{ mb: 2 }}>
              <Chip
                label={project.environment}
                size="small"
                variant="outlined"
                color={getEnvironmentColor(project.environment)}
              />
              {project.useCase && (
                <Chip
                  label={project.useCase}
                  size="small"
                  variant="outlined"
                  color="primary"
                  sx={{ ml: 1 }}
                />
              )}
            </Box>
          )}

          {/* Creation Date */}
          {project.createdAt && (
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CalendarTodayIcon
                sx={{
                  fontSize: theme => theme.iconSizes.medium,
                  color: 'text.secondary',
                  mr: 1,
                }}
              />
              <Typography variant="body2" color="text.secondary">
                Created: {new Date(project.createdAt).toLocaleDateString()}
              </Typography>
            </Box>
          )}

          {/* Tags */}
          {renderTags}
        </CardContent>

        <Box sx={{ flexGrow: 1 }} />
        <Divider />

        {/* Actions Section */}
        <CardActions sx={{ justifyContent: 'flex-end', p: 1.5 }}>
          <Button
            size="small"
            startIcon={<VisibilityIcon />}
            onClick={handleViewClick}
            variant="contained"
            sx={{ minWidth: '80px' }}
          >
            View
          </Button>
        </CardActions>
      </Card>
    );
  }
);

// Add display name for React DevTools
ProjectCard.displayName = 'ProjectCard';

export default ProjectCard;
