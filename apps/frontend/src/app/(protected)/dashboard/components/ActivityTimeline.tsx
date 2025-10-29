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
import { formatDistanceToNow, parseISO } from 'date-fns';

interface ActivityTimelineProps {
  sessionToken: string;
}

type ActivityType =
  | 'test_created'
  | 'test_updated'
  | 'test_run'
  | 'test_set_created'
  | 'task_created'
  | 'task_completed';

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
    default:
      return 'primary';
  }
};

export default function ActivityTimeline({
  sessionToken,
}: ActivityTimelineProps) {
  const theme = useTheme();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);

  const fetchActivities = useCallback(async () => {
    try {
      setLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);

      // Fetch multiple activity sources in parallel
      // Optimized: 4 calls × 2 items = 8 total (displays 6)
      const [newTests, recentTestRuns, newTestSets, recentTasks] =
        await Promise.all([
          clientFactory.getTestsClient().getTests({
            skip: 0,
            limit: 2,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          clientFactory.getTestRunsClient().getTestRuns({
            skip: 0,
            limit: 2,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          clientFactory.getTestSetsClient().getTestSets({
            skip: 0,
            limit: 2,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          clientFactory.getTasksClient().getTasks({
            skip: 0,
            limit: 2,
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

      // Add test runs
      recentTestRuns.data.forEach((testRun: TestRunDetail) => {
        allActivities.push({
          id: `test_run_${testRun.id}`,
          type: 'test_run',
          title: 'Test Run Executed',
          subtitle:
            testRun.test_configuration?.test_set?.name || 'Test run completed',
          timestamp: testRun.created_at,
          metadata: {
            testRunId: testRun.id,
            status: testRun.status?.name || testRun.attributes?.task_state,
          },
        });
      });

      // Add new test sets
      newTestSets.data.forEach((testSet: TestSet) => {
        if (testSet.created_at) {
          allActivities.push({
            id: `test_set_created_${testSet.id}`,
            type: 'test_set_created',
            title: 'Test Set Created',
            subtitle: testSet.name,
            timestamp: testSet.created_at,
            metadata: { testSetId: testSet.id },
          });
        }
      });

      // Add tasks
      recentTasks.data.forEach((task: Task) => {
        // Add task created activity
        if (task.created_at) {
          allActivities.push({
            id: `task_created_${task.id}`,
            type: 'task_created',
            title: 'Task Created',
            subtitle: task.title,
            timestamp: task.created_at,
            metadata: {
              taskId: task.id,
              status: task.status?.name,
              assignee: task.assignee?.name || task.assignee?.email,
              entity_type: task.entity_type,
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
              entity_type: task.entity_type,
            },
          });
        }
      });

      // Sort by timestamp (most recent first) and take top 6
      allActivities.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setActivities(allActivities.slice(0, 6));

      setError(null);
    } catch (err) {
      setError('Unable to load activity data');
      setActivities([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken]);

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

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
        if (activity.metadata?.taskId) {
          router.push(`/tasks/${activity.metadata.taskId}`);
        }
        break;
    }
  };

  if (loading) {
    return (
      <Paper sx={{ p: 3, height: '100%' }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3, height: '100%', minHeight: '924px', overflow: 'auto' }}>
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
                })
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
                      transition: 'all 0.2s',
                      '&:hover': {
                        bgcolor: alpha(theme.palette[activityColor].main, 0.1),
                        transform: 'translateX(4px)',
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
                        label={`Assignee: ${activity.metadata.assignee}`}
                        size="small"
                        color="primary"
                        variant="outlined"
                        sx={{ mt: 0.5, height: 20, fontSize: '0.688rem' }}
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
