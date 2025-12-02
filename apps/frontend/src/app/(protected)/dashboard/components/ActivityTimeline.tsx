'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Paper,
  Chip,
  useTheme,
  alpha,
  Avatar,
} from '@mui/material';
import Timeline from '@mui/lab/Timeline';
import TimelineItem from '@mui/lab/TimelineItem';
import TimelineSeparator from '@mui/lab/TimelineSeparator';
import TimelineConnector from '@mui/lab/TimelineConnector';
import TimelineContent from '@mui/lab/TimelineContent';
import TimelineDot from '@mui/lab/TimelineDot';
import TimelineOppositeContent from '@mui/lab/TimelineOppositeContent';
import { useRouter } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ActivityItem,
  ActivityOperation,
} from '@/utils/api-client/interfaces/activities';
import ScienceIcon from '@mui/icons-material/Science';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CategoryIcon from '@mui/icons-material/Category';
import AssignmentIcon from '@mui/icons-material/Assignment';
import TimelineIcon from '@mui/icons-material/Timeline';
import ApiIcon from '@mui/icons-material/Api';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import AppsIcon from '@mui/icons-material/Apps';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PsychologyIcon from '@mui/icons-material/Psychology';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import CommentIcon from '@mui/icons-material/Comment';
import StorageIcon from '@mui/icons-material/Storage';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import EditIcon from '@mui/icons-material/Edit';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { formatDistanceToNow, parseISO, formatDistance } from 'date-fns';

interface ActivityTimelineProps {
  sessionToken: string;
  onLoadComplete?: () => void;
}

type ActivityType =
  | 'test_created'
  | 'test_updated'
  | 'test_run'
  | 'test_set_created'
  | 'task_created'
  | 'task_completed'
  | 'task_assigned'
  | 'task_updated'
  | 'bulk_operation'
  | 'other';

interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  subtitle?: string;
  timestamp: string;
  metadata?: any;
  isBulk?: boolean;
  count?: number;
  entityType?: string; // Add entity type for icon mapping
  operation?: string; // CREATE, UPDATE, DELETE
  timeRange?: {
    start: string;
    end: string;
  };
  sampleEntities?: Record<string, any>[];
  user?: {
    id: string;
    email: string;
    name?: string | null;
    given_name?: string | null;
    family_name?: string | null;
    picture?: string | null;
  };
}

// Entity type to icon mapping - matches layout.tsx navigation icons
const ENTITY_ICON_MAP: Record<string, React.ReactElement> = {
  Test: <ScienceIcon fontSize="small" />,
  TestRun: <PlayArrowIcon fontSize="small" />,
  TestSet: <CategoryIcon fontSize="small" />,
  Task: <AssignmentIcon fontSize="small" />,
  Endpoint: <ApiIcon fontSize="small" />,
  Metric: <AutoGraphIcon fontSize="small" />,
  Project: <AppsIcon fontSize="small" />,
  Model: <SmartToyIcon fontSize="small" />,
  Behavior: <PsychologyIcon fontSize="small" />,
  Source: <MenuBookIcon fontSize="small" />, // Knowledge in menu
  Comment: <CommentIcon fontSize="small" />,
  // Generic fallback
  default: <StorageIcon fontSize="small" />,
};

const getActivityIcon = (entityType?: string) => {
  if (!entityType) {
    return ENTITY_ICON_MAP.default;
  }
  return ENTITY_ICON_MAP[entityType] || ENTITY_ICON_MAP.default;
};

const getActivityColor = (
  type: ActivityType
): 'primary' | 'secondary' | 'success' | 'info' | 'warning' => {
  switch (type) {
    case 'test_created':
      return 'primary';
    case 'test_updated':
      return 'info';
    case 'test_run':
      return 'success';
    case 'test_set_created':
      return 'secondary';
    case 'task_created':
      return 'info';
    case 'task_completed':
      return 'success';
    case 'task_assigned':
      return 'warning';
    case 'task_updated':
      return 'info';
    case 'bulk_operation':
      return 'primary';
    default:
      return 'primary';
  }
};

// Layout constants for responsive calculation
const LAYOUT_CONSTANTS = {
  DASHBOARD_HEADER_HEIGHT: 8, // theme.spacing units
  KPIS_HEIGHT: 25, // theme.spacing units
  MARGINS: 12.5, // theme.spacing units
  ITEM_HEIGHT: 15, // theme.spacing units per timeline item
  DEFAULT_LIMIT: 6,
  MIN_LIMIT: 6,
  MAX_LIMIT: 15,
  DEFAULT_CONTAINER_HEIGHT: 87.5, // theme.spacing units (700px equivalent)
};

export default function ActivityTimeline({
  sessionToken,
  onLoadComplete,
}: ActivityTimelineProps) {
  const theme = useTheme();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [viewportHeight, setViewportHeight] = useState(0);

  // Calculate how many activities can fit based on viewport height
  const calculateLimit = useCallback(() => {
    if (viewportHeight === 0) return LAYOUT_CONSTANTS.DEFAULT_LIMIT;
    const totalReservedHeight =
      (LAYOUT_CONSTANTS.DASHBOARD_HEADER_HEIGHT +
        LAYOUT_CONSTANTS.KPIS_HEIGHT +
        LAYOUT_CONSTANTS.MARGINS) *
      parseInt(theme.spacing(1));
    const availableHeight = viewportHeight - totalReservedHeight;
    const itemHeightPx =
      LAYOUT_CONSTANTS.ITEM_HEIGHT * parseInt(theme.spacing(1));
    const calculatedLimit = Math.floor(availableHeight / itemHeightPx);
    return Math.max(
      LAYOUT_CONSTANTS.MIN_LIMIT,
      Math.min(calculatedLimit, LAYOUT_CONSTANTS.MAX_LIMIT)
    );
  }, [viewportHeight, theme]);

  const mapActivityItemToActivity = (
    item: ActivityItem,
    index: number
  ): Activity => {
    // Handle bulk operations
    if (item.is_bulk && item.summary) {
      return {
        id: `bulk_${item.entity_type}_${item.operation}_${index}`,
        type: 'bulk_operation',
        title: item.summary,
        subtitle: `${item.count} items`,
        timestamp: item.timestamp,
        isBulk: true,
        count: item.count,
        entityType: item.entity_type, // Store entity type for icon mapping
        operation: item.operation,
        timeRange: item.time_range,
        sampleEntities: item.sample_entities,
        user: item.user || undefined,
        metadata: {
          entityType: item.entity_type,
          operation: item.operation,
          entityIds: item.entity_ids,
          sampleEntities: item.sample_entities,
        },
      };
    }

    // Map individual activities based on entity type and operation
    const entityType = item.entity_type;
    const operation = item.operation;
    const entityData = item.entity_data;

    // Map to appropriate activity type and create title/subtitle
    let type: ActivityType = 'other';
    let title = '';
    let subtitle = '';
    let metadata: any = {};

    if (entityType === 'Test') {
      if (operation === ActivityOperation.CREATE) {
        type = 'test_created';
        title = 'Test Created';
        subtitle =
          entityData?.test_metadata?.prompt?.substring(0, 60) || 'New test';
        metadata = {
          testId: item.entity_id,
          behavior: entityData?.behavior?.name,
          category: entityData?.category,
          topic: entityData?.topic,
          project: entityData?.project?.name,
          testSet: entityData?.test_set?.name,
        };
      } else if (operation === ActivityOperation.UPDATE) {
        type = 'test_updated';
        title = 'Test Updated';
        subtitle = 'Test modified';
        metadata = {
          testId: item.entity_id,
          behavior: entityData?.behavior?.name,
          project: entityData?.project?.name,
          testSet: entityData?.test_set?.name,
        };
      }
    } else if (entityType === 'TestRun') {
      type = 'test_run';
      title = 'Test Run Executed';
      subtitle = entityData?.name || 'Test run completed';
      metadata = {
        testRunId: item.entity_id,
        status: entityData?.status?.name,
      };
    } else if (entityType === 'TestSet') {
      type = 'test_set_created';
      title =
        operation === ActivityOperation.UPDATE
          ? 'Test Set Updated'
          : 'Test Set Created';
      subtitle = entityData?.name || 'Test set';
      metadata = { testSetId: item.entity_id };
    } else if (entityType === 'Task') {
      if (entityData?.completed_at) {
        type = 'task_completed';
        title = 'Task Completed';
      } else if (operation === ActivityOperation.UPDATE) {
        type = 'task_updated';
        title = 'Task Updated';
      } else {
        type = 'task_created';
        title = 'Task Created';
      }
      subtitle = entityData?.title || 'Task';
      metadata = {
        taskId: item.entity_id,
        status: entityData?.status?.name,
        assignee: entityData?.assignee?.name || entityData?.assignee?.email,
      };
    } else if (entityType === 'Comment') {
      type = 'other';
      title = 'Comment Added';
      subtitle = entityData?.content?.substring(0, 60) || 'Comment';
      metadata = { commentId: item.entity_id };
    } else {
      // Generic handling for other entity types
      type = 'other';
      const operationText =
        operation === ActivityOperation.CREATE
          ? 'Created'
          : operation === ActivityOperation.UPDATE
            ? 'Updated'
            : 'Deleted';
      title = `${entityType} ${operationText}`;
      subtitle =
        entityData?.name ||
        entityData?.title ||
        entityData?.description ||
        entityType;
      metadata = { entityId: item.entity_id, entityType };
    }

    return {
      id: `${entityType}_${operation}_${item.entity_id || index}`,
      type,
      title,
      subtitle,
      timestamp: item.timestamp,
      entityType, // Store entity type for icon mapping
      operation,
      user: item.user || undefined,
      metadata,
    };
  };

  const fetchActivities = useCallback(async () => {
    try {
      setLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);

      const limit = calculateLimit();

      // Fetch recent activities using the new unified endpoint
      const response = await clientFactory
        .getServicesClient()
        .getRecentActivities(limit);

      // Map ActivityItems to Activity format for UI
      const mappedActivities = response.activities.map(
        mapActivityItemToActivity
      );

      setActivities(mappedActivities);
      setError(null);
    } catch (err) {
      console.error('Error fetching activities:', err);
      setError('Unable to load activity data');
      setActivities([]);
    } finally {
      setLoading(false);
      onLoadComplete?.();
    }
  }, [sessionToken, calculateLimit]);

  useEffect(() => {
    // Set viewport height once on mount
    setViewportHeight(window.innerHeight);
  }, []);

  useEffect(() => {
    // Fetch data once viewport height is set
    if (sessionToken && viewportHeight > 0) {
      fetchActivities();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, viewportHeight]); // Fetch when sessionToken changes or when viewport height is initially set

  const handleActivityClick = (activity: Activity) => {
    // Bulk operations - don't navigate, could expand to show details in future
    if (activity.isBulk) {
      return;
    }

    switch (activity.type) {
      case 'test_created':
      case 'test_updated':
        if (activity.metadata?.testId) {
          router.push(`/tests/${activity.metadata.testId}`);
        }
        break;
      case 'test_run':
        if (activity.metadata?.testRunId) {
          router.push(`/test-runs/${activity.metadata.testRunId}`);
        }
        break;
      case 'test_set_created':
        if (activity.metadata?.testSetId) {
          router.push(`/test-sets/${activity.metadata.testSetId}`);
        }
        break;
      case 'task_created':
      case 'task_completed':
      case 'task_assigned':
      case 'task_updated':
        if (activity.metadata?.taskId) {
          router.push(`/tasks/${activity.metadata.taskId}`);
        }
        break;
      case 'other':
        // Generic handling - could be extended based on entityType
        if (activity.metadata?.entityId && activity.metadata?.entityType) {
          const entityType = activity.metadata.entityType.toLowerCase();
          router.push(`/${entityType}s/${activity.metadata.entityId}`);
        }
        break;
    }
  };

  // Calculate dynamic container height
  const containerHeight =
    calculateLimit() > LAYOUT_CONSTANTS.MIN_LIMIT
      ? theme.spacing(
          Math.min(
            calculateLimit() * LAYOUT_CONSTANTS.ITEM_HEIGHT + 18.75,
            (viewportHeight -
              (LAYOUT_CONSTANTS.DASHBOARD_HEADER_HEIGHT +
                LAYOUT_CONSTANTS.KPIS_HEIGHT +
                LAYOUT_CONSTANTS.MARGINS) *
                parseInt(theme.spacing(1))) /
              parseInt(theme.spacing(1))
          )
        )
      : theme.spacing(LAYOUT_CONSTANTS.DEFAULT_CONTAINER_HEIGHT);

  if (loading) {
    return (
      <Paper
        sx={{
          p: theme.spacing(3),
          height: containerHeight,
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            p: theme.spacing(3),
          }}
        >
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper
      sx={{
        p: theme.spacing(3),
        height: containerHeight,
        overflow: 'auto',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: theme.spacing(1),
          mb: theme.spacing(3),
        }}
      >
        <TimelineIcon color="primary" />
        <Typography variant="h6">Recent Activity</Typography>
      </Box>

      {error && (
        <Alert severity="warning" sx={{ mb: theme.spacing(2) }}>
          {error}
        </Alert>
      )}

      {activities.length === 0 ? (
        <Typography color="text.secondary" align="center">
          No recent activity
        </Typography>
      ) : (
        <Timeline
          sx={{
            p: 0,
            m: 0,
            '& .MuiTimelineItem-root:before': {
              flex: 0,
              padding: 0,
            },
          }}
        >
          {activities.map((activity, index) => {
            const isLast = index === activities.length - 1;
            const activityColor = getActivityColor(activity.type);
            const activityIcon = getActivityIcon(activity.entityType);
            const timeAgo = activity.timestamp
              ? formatDistanceToNow(parseISO(activity.timestamp), {
                  addSuffix: true,
                })
                  .replace('about ', '~')
                  .replace(' ago', ' ago')
              : 'Unknown';

            return (
              <TimelineItem
                key={activity.id}
                sx={{
                  '&::before': {
                    flex: 0,
                    padding: 0,
                  },
                  minHeight: 'auto',
                }}
              >
                <TimelineOppositeContent
                  sx={{
                    width: theme.spacing(10),
                    minWidth: theme.spacing(10),
                    maxWidth: theme.spacing(10),
                    paddingLeft: 0,
                    paddingRight: theme.spacing(1),
                    paddingTop: theme.spacing(2.6),
                    paddingBottom: 0,
                    margin: 0,
                    flex: '0 0 auto',
                    display: 'flex',
                    alignItems: 'flex-start',
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ lineHeight: 1, textAlign: 'right', width: '100%' }}
                  >
                    {timeAgo}
                  </Typography>
                </TimelineOppositeContent>
                <TimelineSeparator>
                  <TimelineDot color={activityColor} variant="outlined">
                    {activityIcon}
                  </TimelineDot>
                  {!isLast && <TimelineConnector />}
                </TimelineSeparator>
                <TimelineContent
                  sx={{
                    paddingTop: theme.spacing(1),
                    paddingBottom: theme.spacing(1),
                  }}
                >
                  <Box
                    sx={{
                      cursor: activity.isBulk ? 'default' : 'pointer',
                      p: theme.spacing(1.5),
                      mb: theme.spacing(1),
                      borderRadius: theme.shape.borderRadius,
                      bgcolor: alpha(theme.palette[activityColor].main, 0.05),
                      border: `${theme.spacing(0.125)} solid ${alpha(theme.palette[activityColor].main, 0.1)}`,
                      transition: theme.transitions.create('background-color', {
                        duration: theme.transitions.duration.short,
                      }),
                      width: '100%',
                      '&:hover': activity.isBulk
                        ? {}
                        : {
                            bgcolor: alpha(
                              theme.palette[activityColor].main,
                              0.1
                            ),
                          },
                    }}
                    onClick={() => handleActivityClick(activity)}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        mb: theme.spacing(0.5),
                      }}
                    >
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: theme.spacing(1),
                          flex: 1,
                          minWidth: 0,
                        }}
                      >
                        <Avatar
                          src={activity.user?.picture || undefined}
                          alt={
                            activity.user?.name ||
                            activity.user?.email ||
                            'User'
                          }
                          sx={{
                            width: theme.spacing(3),
                            height: theme.spacing(3),
                            fontSize: theme.typography.caption.fontSize,
                          }}
                        >
                          {(activity.user?.name || activity.user?.email || '?')
                            .charAt(0)
                            .toUpperCase()}
                        </Avatar>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography
                            variant="caption"
                            sx={{
                              fontWeight: theme.typography.fontWeightMedium,
                              display: 'block',
                            }}
                          >
                            {activity.title}
                          </Typography>
                          {activity.user && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                fontSize: theme.typography.caption.fontSize,
                                display: 'block',
                              }}
                            >
                              {activity.user.name || activity.user.email}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                      {activity.isBulk && activity.count && (
                        <Chip
                          label={`${activity.count}x`}
                          size="small"
                          color={activityColor}
                          sx={{
                            height: theme.spacing(2.75),
                            fontSize: theme.typography.caption.fontSize,
                            fontWeight: theme.typography.fontWeightBold,
                          }}
                        />
                      )}
                    </Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        mb: theme.spacing(0.5),
                      }}
                    >
                      {activity.subtitle}
                    </Typography>

                    {/* Chips Row */}
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: theme.spacing(0.5),
                        mt: theme.spacing(0.5),
                      }}
                    >
                      {/* Operation Badge */}
                      {activity.operation && (
                        <Chip
                          label={
                            activity.operation.charAt(0).toUpperCase() +
                            activity.operation.slice(1)
                          }
                          size="small"
                          color={
                            activity.operation === 'create'
                              ? 'success'
                              : activity.operation === 'update'
                                ? 'info'
                                : 'error'
                          }
                          sx={{
                            height: theme.spacing(2.5),
                            fontSize: theme.typography.caption.fontSize,
                          }}
                        />
                      )}

                      {/* Time Range for Bulk Operations */}
                      {activity.isBulk && activity.timeRange && (
                        <Chip
                          label={`${formatDistance(
                            parseISO(activity.timeRange.start),
                            parseISO(activity.timeRange.end),
                            { addSuffix: false }
                          )}`}
                          size="small"
                          variant="outlined"
                          sx={{
                            height: theme.spacing(2.5),
                          }}
                        />
                      )}

                      {/* Behavior */}
                      {activity.metadata?.behavior && (
                        <Chip
                          label={activity.metadata.behavior}
                          size="small"
                          sx={{
                            height: theme.spacing(2.5),
                          }}
                        />
                      )}

                      {/* Project */}
                      {activity.metadata?.project && (
                        <Chip
                          icon={<AppsIcon fontSize="small" />}
                          label={activity.metadata.project}
                          size="small"
                          variant="outlined"
                          sx={{
                            height: theme.spacing(2.5),
                          }}
                        />
                      )}

                      {/* Test Set */}
                      {activity.metadata?.testSet && (
                        <Chip
                          icon={<CategoryIcon fontSize="small" />}
                          label={activity.metadata.testSet}
                          size="small"
                          variant="outlined"
                          sx={{
                            height: theme.spacing(2.5),
                          }}
                        />
                      )}
                      {/* Task Status */}
                      {activity.metadata?.status && (
                        <Chip
                          label={activity.metadata.status}
                          size="small"
                          color={
                            activity.metadata.status
                              .toLowerCase()
                              .includes('completed')
                              ? 'success'
                              : activity.metadata.status
                                    .toLowerCase()
                                    .includes('failed')
                                ? 'error'
                                : 'default'
                          }
                          sx={{
                            height: theme.spacing(2.5),
                          }}
                        />
                      )}

                      {/* Task Assignee */}
                      {activity.metadata?.assignee && (
                        <Chip
                          label={`@${activity.metadata.assignee}`}
                          size="small"
                          sx={{
                            height: theme.spacing(2.5),
                            backgroundColor: theme.palette.secondary.light,
                            color: theme.palette.secondary.contrastText,
                          }}
                        />
                      )}
                    </Box>

                    {/* Sample Preview for Bulk Operations */}
                    {activity.isBulk &&
                      activity.sampleEntities &&
                      activity.sampleEntities.length > 0 && (
                        <Box sx={{ mt: theme.spacing(1) }}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              fontSize: theme.typography.caption.fontSize,
                              fontStyle: 'italic',
                            }}
                          >
                            {activity.sampleEntities
                              .slice(0, 3)
                              .map(
                                entity =>
                                  entity.name ||
                                  entity.title ||
                                  entity.test_metadata?.prompt?.substring(0, 30)
                              )
                              .filter(Boolean)
                              .join(', ')}
                          </Typography>
                        </Box>
                      )}
                  </Box>
                </TimelineContent>
              </TimelineItem>
            );
          })}
        </Timeline>
      )}
    </Paper>
  );
}
