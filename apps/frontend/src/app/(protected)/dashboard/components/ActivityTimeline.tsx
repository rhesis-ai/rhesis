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
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Task } from '@/utils/api-client/interfaces/task';
import ScienceIcon from '@mui/icons-material/Science';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import HorizontalSplitIcon from '@mui/icons-material/HorizontalSplit';
import UpdateIcon from '@mui/icons-material/Update';
import AssignmentIcon from '@mui/icons-material/Assignment';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import TimelineIcon from '@mui/icons-material/Timeline';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import EditIcon from '@mui/icons-material/Edit';
import { formatDistanceToNow, parseISO } from 'date-fns';

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
  | 'task_updated';

interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  subtitle?: string;
  timestamp: string;
  metadata?: any;
}

const getActivityIcon = (type: ActivityType) => {
  switch (type) {
    case 'test_created':
      return <ScienceIcon fontSize="small" />;
    case 'test_updated':
      return <UpdateIcon fontSize="small" />;
    case 'test_run':
      return <PlayArrowIcon fontSize="small" />;
    case 'test_set_created':
      return <HorizontalSplitIcon fontSize="small" />;
    case 'task_created':
      return <AssignmentIcon fontSize="small" />;
    case 'task_completed':
      return <CheckCircleIcon fontSize="small" />;
    case 'task_assigned':
      return <PersonAddIcon fontSize="small" />;
    case 'task_updated':
      return <EditIcon fontSize="small" />;
    default:
      return <ScienceIcon fontSize="small" />;
  }
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
    default:
      return 'primary';
  }
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
  // Each activity item is approximately 120px tall
  // Account for dashboard header (~64px), KPIs (~200px), margins (~100px)
  const calculateLimit = useCallback(() => {
    if (viewportHeight === 0) return 6; // Default
    const availableHeight = viewportHeight - 364; // Header + KPIs + margins
    const itemHeight = 120; // Approximate height per timeline item
    const calculatedLimit = Math.floor(availableHeight / itemHeight);
    return Math.max(6, Math.min(calculatedLimit, 15)); // Min 6, max 15
  }, [viewportHeight]);

  const fetchActivities = useCallback(async () => {
    try {
      setLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);

      const limit = calculateLimit();
      // Fetch more items per source to ensure we get the most recent activities
      // Fetch at least 5 items per source to have enough to choose from
      const perSourceLimit = Math.max(5, Math.ceil(limit / 2));

      // Fetch multiple activity sources in parallel
      const [newTests, updatedTests, recentTestRuns, newTestSets, recentTasks] =
        await Promise.all([
          clientFactory.getTestsClient().getTests({
            skip: 0,
            limit: perSourceLimit,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          clientFactory.getTestsClient().getTests({
            skip: 0,
            limit: perSourceLimit,
            sort_by: 'updated_at',
            sort_order: 'desc',
          }),
          clientFactory.getTestRunsClient().getTestRuns({
            skip: 0,
            limit: perSourceLimit,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          clientFactory.getTestSetsClient().getTestSets({
            skip: 0,
            limit: perSourceLimit,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          clientFactory.getTasksClient().getTasks({
            skip: 0,
            limit: perSourceLimit,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
        ]);

      // Combine and format activities
      const allActivities: Activity[] = [];

      // Add new tests
      newTests.data.forEach((test: TestDetail) => {
        allActivities.push({
          id: `test_created_${test.id}`,
          type: 'test_created',
          title: 'Test Created',
          subtitle:
            test.prompt?.content?.substring(0, 60) + '...' || 'New test',
          timestamp: test.created_at,
          metadata: { testId: test.id, behavior: test.behavior?.name },
        });
      });

      // Add updated tests (only if updated_at differs from created_at)
      updatedTests.data.forEach((test: TestDetail) => {
        if (test.updated_at && test.updated_at !== test.created_at) {
          allActivities.push({
            id: `test_updated_${test.id}`,
            type: 'test_updated',
            title: 'Test Updated',
            subtitle:
              test.prompt?.content?.substring(0, 60) + '...' || 'Test modified',
            timestamp: test.updated_at,
            metadata: { testId: test.id, behavior: test.behavior?.name },
          });
        }
      });

      // Add test runs
      recentTestRuns.data.forEach((testRun: TestRunDetail) => {
        // Use started_at from attributes if available, otherwise fall back to created_at
        const timestamp = testRun.attributes?.started_at || testRun.created_at;

        allActivities.push({
          id: `test_run_${testRun.id}`,
          type: 'test_run',
          title: 'Test Run Executed',
          subtitle:
            testRun.test_configuration?.test_set?.name || 'Test run completed',
          timestamp: timestamp,
          metadata: {
            testRunId: testRun.id,
            status: testRun.status?.name || testRun.attributes?.task_state,
          },
        });
      });

      // Add new test sets
      newTestSets.data.forEach((testSet: TestSet) => {
        // Use created_at or updated_at; use a very old date as fallback to sort properly
        const testSetTimestamp =
          testSet.created_at || testSet.updated_at || '2000-01-01T00:00:00Z';

        if (!testSet.created_at && !testSet.updated_at) {
          console.warn(
            'Test set missing timestamp (will be sorted to bottom):',
            testSet.id,
            testSet.name
          );
        }

        allActivities.push({
          id: `test_set_created_${testSet.id}`,
          type: 'test_set_created',
          title: 'Test Set Created',
          subtitle: testSet.name,
          timestamp: testSetTimestamp,
          metadata: { testSetId: testSet.id },
        });
      });

      // Add tasks with enhanced activity tracking
      recentTasks.data.forEach((task: Task) => {
        // Use created_at or updated_at; use a very old date as fallback to sort properly
        // Tasks without timestamps will appear at the bottom
        const taskTimestamp =
          task.created_at || task.updated_at || '2000-01-01T00:00:00Z';

        if (!task.created_at && !task.updated_at) {
          console.warn(
            'Task missing timestamp (will be sorted to bottom):',
            task.id,
            task.title
          );
        }

        // Add task created activity
        allActivities.push({
          id: `task_created_${task.id}`,
          type: 'task_created',
          title: 'Task Created',
          subtitle: task.title,
          timestamp: taskTimestamp,
          metadata: {
            taskId: task.id,
            status: task.status?.name,
            assignee: task.assignee?.name || task.assignee?.email,
            entity_type: task.entity_type,
          },
        });

        // Add task assignment activity if assigned
        if (
          task.assignee &&
          task.updated_at &&
          task.updated_at !== task.created_at
        ) {
          allActivities.push({
            id: `task_assigned_${task.id}`,
            type: 'task_assigned',
            title: 'Task Assigned',
            subtitle: `${task.title} → ${task.assignee.name || task.assignee.email}`,
            timestamp: task.updated_at,
            metadata: {
              taskId: task.id,
              assignee: task.assignee.name || task.assignee.email,
              entity_type: task.entity_type,
              status: task.status?.name,
            },
          });
        }

        // Add task completed activity if completed
        if (task.completed_at) {
          allActivities.push({
            id: `task_completed_${task.id}`,
            type: 'task_completed',
            title: 'Task Completed',
            subtitle: task.title,
            timestamp: task.completed_at,
            metadata: {
              taskId: task.id,
              status: task.status?.name,
              entity_type: task.entity_type,
              assignee: task.assignee?.name || task.assignee?.email,
            },
          });
        }

        // Add task updated activity for status changes (if not completed)
        if (
          task.updated_at &&
          task.updated_at !== task.created_at &&
          !task.completed_at &&
          task.status?.name !== 'Open'
        ) {
          allActivities.push({
            id: `task_updated_${task.id}`,
            type: 'task_updated',
            title: 'Task Updated',
            subtitle: `${task.title} → ${task.status?.name}`,
            timestamp: task.updated_at,
            metadata: {
              taskId: task.id,
              status: task.status?.name,
              entity_type: task.entity_type,
              assignee: task.assignee?.name || task.assignee?.email,
            },
          });
        }
      });

      // Sort by timestamp (most recent first) and take calculated limit
      allActivities.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setActivities(allActivities.slice(0, limit));

      setError(null);
    } catch (err) {
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
    }
  };

  // Calculate dynamic container height
  const containerHeight =
    calculateLimit() > 6
      ? `${Math.min(calculateLimit() * 120 + 150, viewportHeight - 364)}px`
      : '700px';

  if (loading) {
    return (
      <Paper sx={{ p: 3, height: containerHeight, overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3, height: containerHeight, overflow: 'auto' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <TimelineIcon color="primary" />
        <Typography variant="h6">Recent Activity</Typography>
      </Box>

      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
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
            const activityIcon = getActivityIcon(activity.type);
            const timeAgo = activity.timestamp
              ? formatDistanceToNow(parseISO(activity.timestamp), {
                  addSuffix: true,
                }).replace('about ', '~')
              : 'Unknown';

            return (
              <TimelineItem key={activity.id}>
                <TimelineOppositeContent
                  sx={{ maxWidth: '80px', paddingLeft: 0, paddingRight: 1 }}
                >
                  <Typography variant="caption" color="text.secondary">
                    {timeAgo.replace(' ago', '')}
                  </Typography>
                </TimelineOppositeContent>
                <TimelineSeparator>
                  <TimelineDot color={activityColor} variant="outlined">
                    {activityIcon}
                  </TimelineDot>
                  {!isLast && <TimelineConnector />}
                </TimelineSeparator>
                <TimelineContent>
                  <Box
                    sx={{
                      cursor: 'pointer',
                      p: 1.5,
                      mb: 1,
                      borderRadius: 1,
                      bgcolor: alpha(theme.palette[activityColor].main, 0.05),
                      border: `1px solid ${alpha(theme.palette[activityColor].main, 0.1)}`,
                      transition: 'background-color 0.2s',
                      '&:hover': {
                        bgcolor: alpha(theme.palette[activityColor].main, 0.1),
                      },
                    }}
                    onClick={() => handleActivityClick(activity)}
                  >
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: 600, mb: 0.5 }}
                    >
                      {activity.title}
                    </Typography>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        fontSize: '0.813rem',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {activity.subtitle}
                    </Typography>
                    {activity.metadata?.behavior && (
                      <Chip
                        label={activity.metadata.behavior}
                        size="small"
                        sx={{ mt: 0.5, height: 20, fontSize: '0.688rem' }}
                      />
                    )}
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
                          mt: 0.5,
                          height: 20,
                          fontSize: '0.688rem',
                          mr: 0.5,
                        }}
                      />
                    )}
                    {activity.metadata?.assignee && (
                      <Chip
                        label={`@${activity.metadata.assignee}`}
                        size="small"
                        sx={{
                          mt: 0.5,
                          mr: 0.5,
                          height: 20,
                          fontSize: '0.688rem',
                          backgroundColor: theme.palette.secondary.light,
                          color: theme.palette.secondary.contrastText,
                        }}
                      />
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
