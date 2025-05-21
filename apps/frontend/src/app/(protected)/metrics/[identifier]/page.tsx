'use client';

import { useState, useEffect } from 'react';
import { Box, Grid, Paper, Typography, Stack, Chip } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SettingsIcon from '@mui/icons-material/Settings';
import BaseWorkflowSection from '@/components/common/BaseWorkflowSection';
import BaseTag from '@/components/common/BaseTag';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { formatDate } from '@/utils/date-utils';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType } from '@/utils/api-client/interfaces/tag';

export default function MetricDetailPage() {
  const params = useParams();
  const identifier = params.identifier as string;
  const { data: session } = useSession();
  const [metric, setMetric] = useState<MetricDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const notifications = useNotifications();

  useEffect(() => {
    const fetchMetric = async () => {
      if (!session?.session_token) return;
      
      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const metricsClient = clientFactory.getMetricsClient();
        const metricData = await metricsClient.getMetric(identifier);
        setMetric(metricData);
      } catch (error) {
        console.error('Error fetching metric:', error);
        notifications.show('Failed to load metric details', { severity: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchMetric();
  }, [identifier, session?.session_token, notifications]);

  const handleTagsChange = async (newTags: string[]) => {
    if (!session?.session_token || !metric) return;

    try {
      const clientFactory = new ApiClientFactory(session.session_token);
      const metricsClient = clientFactory.getMetricsClient();
      const updatedMetric = await metricsClient.getMetric(metric.id);
      setMetric(updatedMetric);
    } catch (error) {
      console.error('Error refreshing metric:', error);
      notifications.show('Failed to refresh metric data', { severity: 'error' });
    }
  };

  const SectionHeader = ({ icon, title }: { icon: React.ReactNode; title: string }) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
      <Box sx={{ color: 'primary.main' }}>{icon}</Box>
      <Typography variant="h6">{title}</Typography>
    </Box>
  );

  const InfoRow = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography variant="subtitle2" color="text.secondary">
        {label}
      </Typography>
      {children}
    </Box>
  );

  if (loading) {
    return (
      <PageContainer title="Loading...">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Typography>Loading metric details...</Typography>
        </Box>
      </PageContainer>
    );
  }

  if (!metric) {
    return (
      <PageContainer title="Error">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Typography color="error">Failed to load metric details</Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer title={metric.name} breadcrumbs={[
      { title: 'Metrics', path: '/metrics' },
      { title: metric.name, path: `/metrics/${identifier}` }
    ]}>
      <Grid container spacing={3}>
        {/* Left side - Main content */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            {/* General Information Section */}
            <Paper sx={{ p: 3 }}>
              <SectionHeader icon={<InfoIcon />} title="General Information" />
              
              {/* Top row with Created, Last Updated, and Metric Type */}
              <Box sx={{ display: 'flex', gap: 4, mb: 3 }}>
                <InfoRow label="Created">
                  <Typography>{formatDate(metric.created_at)}</Typography>
                </InfoRow>

                <InfoRow label="Last Updated">
                  <Typography>{formatDate(metric.updated_at)}</Typography>
                </InfoRow>

                <InfoRow label="Metric Type">
                  {metric.metric_type && (
                    <Chip 
                      label={metric.metric_type.type_value}
                      color="primary"
                      variant="outlined"
                      size="small"
                    />
                  )}
                </InfoRow>
              </Box>

              {/* Description */}
              <Box sx={{ mb: 3 }}>
                <InfoRow label="Description">
                  <Typography>{metric.description || '-'}</Typography>
                </InfoRow>
              </Box>

              {/* Tags */}
              <InfoRow label="Tags">
                <BaseTag
                  value={metric.tags?.map(tag => tag.name) || []}
                  onChange={handleTagsChange}
                  placeholder="Add tags..."
                  chipColor="primary"
                  disableEdition={!session?.session_token}
                  entityType={EntityType.METRIC}
                  entity={metric}
                  sessionToken={session?.session_token}
                />
              </InfoRow>
            </Paper>

            {/* Evaluation Process Section */}
            <Paper sx={{ p: 3 }}>
              <SectionHeader icon={<AssessmentIcon />} title="Evaluation Process" />
              {/* TODO: Add evaluation process content */}
            </Paper>

            {/* Result Configuration Section */}
            <Paper sx={{ p: 3 }}>
              <SectionHeader icon={<SettingsIcon />} title="Result Configuration" />
              {/* TODO: Add result configuration content */}
            </Paper>
          </Stack>
        </Grid>

        {/* Right side - Workflow */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <BaseWorkflowSection
              title="Workflow"
              entityId={identifier}
              entityType="Metric"
              onUpdateEntity={async (updateData, fieldName) => {
                if (!session?.session_token) return;
                
                try {
                  const clientFactory = new ApiClientFactory(session.session_token);
                  const metricsClient = clientFactory.getMetricsClient();
                  await metricsClient.updateMetric(identifier, updateData);
                  notifications.show(`${fieldName} updated successfully`, { severity: 'success' });
                } catch (error) {
                  console.error('Error updating metric:', error);
                  notifications.show(`Failed to update ${fieldName}`, { severity: 'error' });
                }
              }}
            />
          </Paper>
        </Grid>
      </Grid>
    </PageContainer>
  );
} 