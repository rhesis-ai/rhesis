'use client';

import * as React from 'react';
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
import { useRouter } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import MetricCard from './MetricCard';
import SectionEditDrawer from './DimensionDrawer';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import type { Behavior as ApiBehavior, BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';

interface BehaviorMetrics {
  [behaviorId: string]: {
    metrics: MetricDetail[] | any[];
    isLoading: boolean;
    error: string | null;
  }
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
  setBehaviorsWithMetrics: React.Dispatch<React.SetStateAction<BehaviorWithMetrics[]>>;
  setBehaviorMetrics: React.Dispatch<React.SetStateAction<BehaviorMetrics>>;
  onTabChange: () => void; // Function to switch to Metrics Directory tab
}

// Add type guard function
function isValidMetricType(type: string | undefined): type is 'custom-prompt' | 'api-call' | 'custom-code' | 'grading' {
  return type === 'custom-prompt' || type === 'api-call' || type === 'custom-code' || type === 'grading';
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
  onTabChange
}: SelectedMetricsTabProps) {
  const router = useRouter();
  const notifications = useNotifications();

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

  const handleSaveSection = async (title: string, description: string, organization_id: UUID) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);
      
      const behaviorClient = new BehaviorClient(sessionToken);

      if (isNewSection) {
        // Create new behavior
        const createPayload = {
          name: title,
          description: description || null,
          organization_id
        };

        const created = await behaviorClient.createBehavior(createPayload);
        
        // Create new behavior with metrics structure for optimized data
        const newBehaviorWithMetrics: BehaviorWithMetrics = {
          ...created,
          nano_id: null,
          organization_id: created.organization_id || organizationId,
          status_id: created.status_id || '' as UUID,
          metrics: [],
          organization: {} as any,
          status: null
        };
        
        setBehaviors(prev => [...prev, created]);
        setBehaviorMetrics(prev => ({
          ...prev,
          [created.id]: { metrics: [], isLoading: false, error: null }
        }));
        setBehaviorsWithMetrics(prev => [...prev, newBehaviorWithMetrics]);
        
        notifications.show('Dimension created successfully', { 
          severity: 'success', 
          autoHideDuration: 4000 
        });
      } else if (editingSection && editingSection.key) {
        // Update existing behavior
        const updatePayload = {
          name: title,
          description: description || null,
          organization_id
        };

        const updated = await behaviorClient.updateBehavior(editingSection.key, updatePayload);
        
        setBehaviors(prev => prev.map(b => 
          b.id === editingSection.key 
            ? { ...b, name: updated.name, description: updated.description } 
            : b
        ));
        
        setBehaviorsWithMetrics(prev => prev.map(b => 
          b.id === editingSection.key 
            ? { ...b, name: updated.name, description: updated.description } 
            : b
        ));
        
        notifications.show('Dimension updated successfully', { 
          severity: 'success', 
          autoHideDuration: 4000 
        });
      }
      setDrawerOpen(false);
    } catch (err) {
      console.error('Error saving behavior:', err);
      setDrawerError(err instanceof Error ? err.message : 'Failed to save dimension');
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
            metricsClient.removeBehaviorFromMetric(metric.id as UUID, editingSection.key as UUID)
          );

          try {
            await Promise.all(removePromises);
          } catch (err) {
            console.error('Error removing metrics from behavior:', err);
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
        setBehaviorsWithMetrics(prev => prev.filter(b => b.id !== editingSection.key));
        
        notifications.show('Dimension deleted successfully', { 
          severity: 'success', 
          autoHideDuration: 4000 
        });
        setDrawerOpen(false);
      } catch (err) {
        console.error('Error deleting behavior:', err);
        notifications.show(
          err instanceof Error ? err.message : 'Failed to delete dimension', 
          { severity: 'error', autoHideDuration: 4000 }
        );
      }
    } else {
      setDrawerOpen(false);
    }
  };

  const handleMetricDetail = (metricType: string) => {
    router.push(`/metrics/${metricType}`);
  };

  const handleRemoveMetricFromBehavior = async (behaviorId: string, metricId: string) => {
    try {
      const behaviorClient = new BehaviorClient(sessionToken);
      const metricClient = new MetricsClient(sessionToken);

      // Remove metric from behavior
      await metricClient.removeBehaviorFromMetric(metricId as UUID, behaviorId as UUID);

      // Fetch updated metrics for the behavior
      const updatedBehaviorMetrics = await behaviorClient.getBehaviorMetrics(behaviorId as UUID);

      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: {
          ...prev[behaviorId],
          metrics: updatedBehaviorMetrics,
          isLoading: false,
          error: null
        }
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
        autoHideDuration: 4000
      });
    } catch (err) {
      console.error('Error removing metric from behavior:', err);
      notifications.show('Failed to remove metric from behavior', {
        severity: 'error',
        autoHideDuration: 4000
      });
    }
  };

  const renderSection = (behaviorWithMetrics: BehaviorWithMetrics) => {
    const behaviorMetricsList = behaviorWithMetrics.metrics || [];

    return (
      <Box key={behaviorWithMetrics.id} sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography 
            variant="h6" 
            component="h2" 
            sx={{ fontWeight: 'bold' }}
          >
            {behaviorWithMetrics.name}
          </Typography>
          <IconButton 
            onClick={() => handleEditSection(behaviorWithMetrics.id as UUID, behaviorWithMetrics.name, behaviorWithMetrics.description || '')}
            size="small"
          >
            <EditIcon />
          </IconButton>
        </Box>
        <Typography 
          variant="body2" 
          color="text.secondary"
          sx={{ mb: 3 }}
        >
          {behaviorWithMetrics.description || 'No description provided'}
        </Typography>
        
        {behaviorMetricsList.length > 0 ? (
          <Box 
            sx={{ 
              display: 'flex',
              flexWrap: 'wrap',
              gap: 3,
              '& > *': {
                flex: { 
                  xs: '1 1 100%', 
                  sm: '1 1 calc(50% - 12px)', 
                  md: '1 1 calc(33.333% - 16px)' 
                },
                minWidth: { xs: '100%', sm: '300px', md: '320px' },
                maxWidth: { xs: '100%', sm: 'calc(50% - 12px)', md: 'calc(33.333% - 16px)' }
              }
            }}
          >
            {behaviorMetricsList.map((metric) => (
              <Box key={metric.id} sx={{ position: 'relative' }}>
                <Box 
                  sx={{ 
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    display: 'flex',
                    gap: 1,
                    zIndex: 1
                  }}
                >
                  <IconButton
                    size="small"
                    onClick={() => handleMetricDetail(metric.id)}
                    sx={{
                      padding: '2px',
                      '& .MuiSvgIcon-root': {
                        fontSize: theme.typography.helperText.fontSize
                      }
                    }}
                  >
                    <OpenInNewIcon fontSize="inherit" />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveMetricFromBehavior(behaviorWithMetrics.id, metric.id);
                    }}
                    sx={{
                      padding: '2px',
                      '& .MuiSvgIcon-root': {
                        fontSize: theme.typography.helperText.fontSize
                      }
                    }}
                  >
                    <CloseIcon fontSize="inherit" />
                  </IconButton>
                </Box>
                <MetricCard 
                  type={isValidMetricType(metric.metric_type?.type_value) ? metric.metric_type.type_value : undefined}
                  title={metric.name}
                  description={metric.description}
                  backend={metric.backend_type?.type_value}
                  metricType={metric.metric_type?.type_value}
                  scoreType={metric.score_type}
                  usedIn={[behaviorWithMetrics.name]}
                  showUsage={false}
                />
              </Box>
            ))}
          </Box>
        ) : (
          <Paper 
            sx={{ 
              p: 3, 
              textAlign: 'center',
              backgroundColor: 'action.hover',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2
            }}
          >
            <Typography color="text.secondary">
              No metrics assigned to this behavior
            </Typography>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={onTabChange}
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
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        p: 4, 
        minHeight: '200px' 
      }}>
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
    <Box sx={{ 
      width: '100%',
      pr: 2,
      pb: 4
    }}>
      {behaviorsWithMetrics
        .filter(b => b.name && b.name.trim() !== '')
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(behavior => renderSection(behavior))}
      
      <Box 
        sx={{ 
          mt: 4, 
          p: 3, 
          border: '2px dashed',
          borderColor: 'divider',
          borderRadius: 1,
          display: 'flex',
          justifyContent: 'center',
          mb: 8
        }}
      >
        <Button
          startIcon={<AddIcon />}
          onClick={handleAddNewSection}
          sx={{ color: 'text.secondary' }}
        >
          Add New Dimension
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
