'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useRouter, useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import MetricCard from './MetricCard';
import SectionEditDrawer from './DimensionDrawer';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import type {
  Behavior as ApiBehavior,
  BehaviorWithMetrics,
} from '@/utils/api-client/interfaces/behavior';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';

interface BehaviorMetrics {
  [behaviorId: string]: {
    metrics: MetricDetail[] | any[];
    isLoading: boolean;
    error: string | null;
  };
}

interface SelectedMetricsTabProps {
  sessionToken: string;
  organizationId: UUID;
  behaviorsWithMetrics: BehaviorWithMetrics[];
  behaviorMetrics: BehaviorMetrics;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  setBehaviors: React.Dispatch<React.SetStateAction<ApiBehavior[]>>;
  setBehaviorsWithMetrics: React.Dispatch<
    React.SetStateAction<BehaviorWithMetrics[]>
  >;
  setBehaviorMetrics: React.Dispatch<React.SetStateAction<BehaviorMetrics>>;
  onTabChange: () => void; // Function to switch to Metrics Directory tab
}

// Add type guard function
function isValidMetricType(
  type: string | undefined
): type is 'custom-prompt' | 'api-call' | 'custom-code' | 'grading' {
  return (
    type === 'custom-prompt' ||
    type === 'api-call' ||
    type === 'custom-code' ||
    type === 'grading'
  );
}

export default function SelectedMetricsTab({
  sessionToken,
  organizationId,
  behaviorsWithMetrics,
  behaviorMetrics,
  isLoading,
  error,
  onRefresh,
  setBehaviors,
  setBehaviorsWithMetrics,
  setBehaviorMetrics,
  onTabChange,
}: SelectedMetricsTabProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const theme = useTheme();

  // Drawer state
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editingSection, setEditingSection] = React.useState<{
    key: UUID | null;
    title: string;
    description: string;
  } | null>(null);
  const [isNewSection, setIsNewSection] = React.useState(false);
  const [drawerLoading, setDrawerLoading] = React.useState(false);
  const [drawerError, setDrawerError] = React.useState<string>();

  const handleEditSection = (key: UUID, title: string, description: string) => {
    setEditingSection({ key, title, description });
    setIsNewSection(false);
    setDrawerOpen(true);
  };

  const handleAddNewSection = () => {
    setEditingSection({ key: null, title: '', description: '' });
    setIsNewSection(true);
    setDrawerOpen(true);
  };

  const handleSwitchToDirectoryWithAssignMode = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('assignMode', 'true');
    params.delete('tab'); // Switch to directory tab (tab 0)
    router.replace(`/metrics?${params.toString()}`, { scroll: false });
    onTabChange(); // Trigger the tab change
  };

  const handleSaveSection = async (
    title: string,
    description: string,
    organization_id: UUID
  ) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);

      const behaviorClient = new BehaviorClient(sessionToken);

      if (isNewSection) {
        // Create new behavior
        const createPayload = {
          name: title,
          description: description || null,
          organization_id,
        };

        const created = await behaviorClient.createBehavior(createPayload);

        // Create new behavior with metrics structure for optimized data
        const newBehaviorWithMetrics: BehaviorWithMetrics = {
          ...created,
          nano_id: null,
          organization_id: created.organization_id || organizationId,
          status_id: created.status_id || ('' as UUID),
          metrics: [],
          organization: {} as any,
          status: null,
        };

        setBehaviors(prev => [...prev, created]);
        setBehaviorMetrics(prev => ({
          ...prev,
          [created.id]: { metrics: [], isLoading: false, error: null },
        }));
        setBehaviorsWithMetrics(prev => [...prev, newBehaviorWithMetrics]);

        notifications.show('Dimension created successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } else if (editingSection && editingSection.key) {
        // Update existing behavior
        const updatePayload = {
          name: title,
          description: description || null,
          organization_id,
        };

        const updated = await behaviorClient.updateBehavior(
          editingSection.key,
          updatePayload
        );

        setBehaviors(prev =>
          prev.map(b =>
            b.id === editingSection.key
              ? { ...b, name: updated.name, description: updated.description }
              : b
          )
        );

        setBehaviorsWithMetrics(prev =>
          prev.map(b =>
            b.id === editingSection.key
              ? { ...b, name: updated.name, description: updated.description }
              : b
          )
        );

        notifications.show('Dimension updated successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      }
      setDrawerOpen(false);
    } catch (err) {
      setDrawerError(
        err instanceof Error ? err.message : 'Failed to save dimension'
      );
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDeleteSection = async () => {
    if (!isNewSection && editingSection && editingSection.key) {
      try {
        const behaviorClient = new BehaviorClient(sessionToken);
        const metricsClient = new MetricsClient(sessionToken);
        const behaviorData = behaviorMetrics[editingSection.key];

        if (behaviorData && behaviorData.metrics.length > 0) {
          // First remove all metrics from the behavior
          const removePromises = behaviorData.metrics.map(metric =>
            metricsClient.removeBehaviorFromMetric(
              metric.id as UUID,
              editingSection.key as UUID
            )
          );

          try {
            await Promise.all(removePromises);
          } catch (err) {
            notifications.show(
              'Failed to remove all metrics from dimension. Please try again.',
              { severity: 'error', autoHideDuration: 4000 }
            );
            return;
          }
        }

        // Then delete the behavior itself
        await behaviorClient.deleteBehavior(editingSection.key);

        // Update local state
        setBehaviors(prev => prev.filter(b => b.id !== editingSection.key));
        setBehaviorMetrics(prev => {
          const newState = { ...prev };
          const key = editingSection?.key as UUID;
          if (key) {
            delete newState[key];
          }
          return newState;
        });
        setBehaviorsWithMetrics(prev =>
          prev.filter(b => b.id !== editingSection.key)
        );

        notifications.show('Dimension deleted successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
        setDrawerOpen(false);
      } catch (err) {
        notifications.show(
          err instanceof Error ? err.message : 'Failed to delete dimension',
          { severity: 'error', autoHideDuration: 4000 }
        );
      }
    } else {
      setDrawerOpen(false);
    }
  };

  const handleMetricDetail = (metricId: string) => {
    router.push(`/metrics/${metricId}`);
  };

  const handleRemoveMetricFromBehavior = async (
    behaviorId: string,
    metricId: string
  ) => {
    try {
      const behaviorClient = new BehaviorClient(sessionToken);
      const metricClient = new MetricsClient(sessionToken);

      // Remove metric from behavior
      await metricClient.removeBehaviorFromMetric(
        metricId as UUID,
        behaviorId as UUID
      );

      // Fetch updated metrics for the behavior
      const updatedBehaviorMetrics = await behaviorClient.getBehaviorMetrics(
        behaviorId as UUID
      );

      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: {
          ...prev[behaviorId],
          metrics: updatedBehaviorMetrics,
          isLoading: false,
          error: null,
        },
      }));

      // Also update the optimized behaviorsWithMetrics data
      setBehaviorsWithMetrics(prevBehaviors =>
        prevBehaviors.map(behavior =>
          behavior.id === behaviorId
            ? { ...behavior, metrics: updatedBehaviorMetrics as any }
            : behavior
        )
      );

      notifications.show('Successfully removed metric from behavior', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (err) {
      notifications.show('Failed to remove metric from behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
  };

  const renderSection = (behaviorWithMetrics: BehaviorWithMetrics) => {
    const behaviorMetricsList = behaviorWithMetrics.metrics || [];

    return (
      <Box key={behaviorWithMetrics.id} sx={{ mb: theme.spacing(4) }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: theme.spacing(1),
            pb: theme.spacing(1),
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Typography
            variant="h6"
            component="h2"
            sx={{
              fontWeight: theme.typography.fontWeightBold,
              color: theme.palette.text.primary,
            }}
          >
            {behaviorWithMetrics.name}
          </Typography>
          <IconButton
            onClick={() =>
              handleEditSection(
                behaviorWithMetrics.id as UUID,
                behaviorWithMetrics.name,
                behaviorWithMetrics.description || ''
              )
            }
            size="small"
            sx={{
              color: theme.palette.primary.main,
              '&:hover': {
                backgroundColor: theme.palette.action.hover,
              },
            }}
          >
            <EditIcon />
          </IconButton>
        </Box>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mb: theme.spacing(3) }}
        >
          {behaviorWithMetrics.description || 'No description provided'}
        </Typography>

        {behaviorMetricsList.length > 0 ? (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
              },
              gap: theme.spacing(3),
              width: '100%',
              px: 0,
            }}
          >
            {behaviorMetricsList.map(metric => (
              <Box key={metric.id} sx={{ position: 'relative' }}>
                <Box
                  sx={{
                    position: 'absolute',
                    top: theme.spacing(1),
                    right: theme.spacing(1),
                    display: 'flex',
                    gap: theme.spacing(0.5),
                    zIndex: 1,
                  }}
                >
                  {/* Only show detail button for rhesis and custom metrics */}
                  {(metric.backend_type?.type_value?.toLowerCase() ===
                    'rhesis' ||
                    metric.backend_type?.type_value?.toLowerCase() ===
                      'custom') && (
                    <IconButton
                      size="small"
                      onClick={() => handleMetricDetail(metric.id)}
                      sx={{
                        padding: theme.spacing(0.25),
                        '& .MuiSvgIcon-root': {
                          fontSize:
                            theme?.typography?.helperText?.fontSize ||
                            '0.75rem',
                          color: 'currentColor',
                        },
                      }}
                    >
                      <OpenInNewIcon fontSize="inherit" />
                    </IconButton>
                  )}
                  <IconButton
                    size="small"
                    onClick={e => {
                      e.stopPropagation();
                      handleRemoveMetricFromBehavior(
                        behaviorWithMetrics.id,
                        metric.id
                      );
                    }}
                    sx={{
                      padding: theme => theme.spacing(0.25),
                      '& .MuiSvgIcon-root': {
                        fontSize: theme.typography.caption.fontSize,
                        color: 'currentColor',
                      },
                    }}
                  >
                    <CloseIcon fontSize="inherit" />
                  </IconButton>
                </Box>
                <MetricCard
                  type={
                    isValidMetricType(metric.metric_type?.type_value)
                      ? metric.metric_type.type_value
                      : undefined
                  }
                  title={metric.name}
                  description={metric.description}
                  backend={metric.backend_type?.type_value}
                  metricType={metric.metric_type?.type_value}
                  scoreType={metric.score_type}
                  metricScope={metric.metric_scope}
                  usedIn={[behaviorWithMetrics.name]}
                  showUsage={false}
                />
              </Box>
            ))}
          </Box>
        ) : (
          <Paper
            elevation={0}
            sx={{
              p: theme.spacing(3),
              textAlign: 'center',
              backgroundColor: theme.palette.action.hover,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: theme.spacing(2),
              borderRadius: theme.shape.borderRadius,
              border: `1px dashed ${theme.palette.divider}`,
            }}
          >
            <Typography
              variant="body1"
              color="text.secondary"
              sx={{ fontWeight: theme.typography.fontWeightMedium }}
            >
              No metrics assigned to this behavior
            </Typography>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={handleSwitchToDirectoryWithAssignMode}
              sx={{
                color: theme.palette.primary.main,
                borderColor: theme.palette.primary.main,
                '&:hover': {
                  backgroundColor: theme.palette.primary.light,
                  borderColor: theme.palette.primary.main,
                },
              }}
            >
              Add Metric
            </Button>
          </Paper>
        )}
      </Box>
    );
  };

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          p: 4,
          minHeight: theme => theme.spacing(25),
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CircularProgress size={24} />
          <Typography>Loading behaviors and metrics...</Typography>
        </Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '100%',
        px: theme.spacing(3),
        pb: theme.spacing(4),
      }}
    >
      {behaviorsWithMetrics
        .filter(b => b.name && b.name.trim() !== '')
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(behavior => renderSection(behavior))}

      <Box
        sx={{
          mt: 4,
          p: 3,
          border: theme => `${theme.spacing(0.25)} dashed`,
          borderColor: 'divider',
          borderRadius: theme => theme.shape.borderRadius * 0.25,
          display: 'flex',
          justifyContent: 'center',
          mb: 8,
        }}
      >
        <Button
          startIcon={<AddIcon />}
          onClick={handleAddNewSection}
          sx={{ color: 'text.secondary' }}
        >
          Add New Behavior
        </Button>
      </Box>

      {/* Section Edit Drawer */}
      {editingSection && (
        <SectionEditDrawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          title={editingSection.title}
          description={editingSection.description}
          onSave={handleSaveSection}
          onDelete={
            !isNewSection &&
            editingSection.key &&
            behaviorMetrics[editingSection.key] &&
            behaviorMetrics[editingSection.key].metrics.length === 0
              ? handleDeleteSection
              : undefined
          }
          isNew={isNewSection}
          loading={drawerLoading}
          error={drawerError}
          organization_id={organizationId}
        />
      )}
    </Box>
  );
}
