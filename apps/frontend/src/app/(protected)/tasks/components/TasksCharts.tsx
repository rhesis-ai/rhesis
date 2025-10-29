'use client';

import React, { useEffect, useState } from 'react';
import { Box, Typography, Grid, Card, CardContent } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Task } from '@/utils/api-client/interfaces/task';

interface TasksChartsProps {
  sessionToken: string;
}

export default function TasksCharts({ sessionToken }: TasksChartsProps) {
  const [stats, setStats] = useState({
    total: 0,
    open: 0,
    inProgress: 0,
    completed: 0,
    cancelled: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const tasksClient = clientFactory.getTasksClient();

        // Fetch all tasks in batches to get accurate statistics
        const allTasks: Task[] = [];
        let skip = 0;
        const limit = 100; // Backend maximum limit

        while (true) {
          const response = await tasksClient.getTasks({ skip, limit });
          allTasks.push(...response.data);

          // If we got fewer tasks than the limit, we've reached the end
          if (response.data.length < limit) {
            break;
          }

          skip += limit;
        }

        const stats = {
          total: allTasks.length,
          open: allTasks.filter(task => task.status?.name === 'Open').length,
          inProgress: allTasks.filter(
            task => task.status?.name === 'In Progress'
          ).length,
          completed: allTasks.filter(task => task.status?.name === 'Completed')
            .length,
          cancelled: allTasks.filter(task => task.status?.name === 'Cancelled')
            .length,
        };

        setStats(stats);
      } catch (error) {
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [sessionToken]);

  const StatCard = ({
    title,
    value,
    color = 'primary',
  }: {
    title: string;
    value: number;
    color?: string;
  }) => (
    <Card>
      <CardContent>
        <Typography color="textSecondary" gutterBottom variant="h6">
          {title}
        </Typography>
        <Typography variant="h4" color={`${color}.main`}>
          {loading ? '...' : value}
        </Typography>
      </CardContent>
    </Card>
  );

  return (
    <Box sx={{ mb: 3 }}>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Total" value={stats.total} />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Open" value={stats.open} color="warning" />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard
            title="In Progress"
            value={stats.inProgress}
            color="primary"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Completed" value={stats.completed} color="success" />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Cancelled" value={stats.cancelled} color="error" />
        </Grid>
      </Grid>
    </Box>
  );
}
