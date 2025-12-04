'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Drawer from '@mui/material/Drawer';
import CircularProgress from '@mui/material/CircularProgress';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useRouter } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import MetricCard from '@/app/(protected)/metrics/components/MetricCard';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';

interface BehaviorMetricsViewerProps {
  open: boolean;
  onClose: () => void;
  behavior: BehaviorWithMetrics | null;
  sessionToken: string;
  onRefresh: (removedMetricId?: string) => void;
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

export default function BehaviorMetricsViewer({
  open,
  onClose,
  behavior,
  sessionToken,
  onRefresh,
}: BehaviorMetricsViewerProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const theme = useTheme();

  const [isRemoving, setIsRemoving] = React.useState<string | null>(null);

  const handleMetricDetail = (metricId: string) => {
    router.push(`/metrics/${metricId}`);
  };

  const handleRemoveMetric = async (metricId: string) => {
    if (!behavior) return;

    try {
      setIsRemoving(metricId);
      const metricClient = new MetricsClient(sessionToken);

      await metricClient.removeBehaviorFromMetric(
        metricId as UUID,
        behavior.id as UUID
      );

      notifications.show('Successfully removed metric from behavior', {
        severity: 'success',
        autoHideDuration: 4000,
      });

      onRefresh(metricId); // Pass the removed metric ID for dynamic update
    } catch (err) {
      notifications.show('Failed to remove metric from behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsRemoving(null);
    }
  };

  const metrics = behavior?.metrics || [];

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{
        keepMounted: true,
        slotProps: {
          backdrop: {
            sx: {
              backgroundColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      }}
      slotProps={{
        backdrop: {
          sx: {
            zIndex: theme => theme.zIndex.drawer - 1,
          },
        },
      }}
      PaperProps={{
        sx: {
          width: { xs: '100%', sm: '80%', md: '60%' },
          maxWidth: '900px',
          zIndex: theme => theme.zIndex.drawer + 1,
        },
      }}
      sx={{
        zIndex: theme => theme.zIndex.drawer + 1,
        '& .MuiDrawer-paper': {
          boxSizing: 'border-box',
        },
      }}
    >
      {behavior && (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <Box
            sx={{
              p: 3,
              borderBottom: 1,
              borderColor: 'divider',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
            }}
          >
            <Box sx={{ flex: 1 }}>
              <Typography variant="h6" component="h2" gutterBottom>
                {behavior.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {behavior.description || 'No description provided'}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mt: 1 }}
              >
                {metrics.length} {metrics.length === 1 ? 'Metric' : 'Metrics'}
              </Typography>
            </Box>
            <IconButton onClick={onClose} sx={{ ml: 2 }}>
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Content */}
          <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
            {metrics.length > 0 ? (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    md: 'repeat(2, 1fr)',
                  },
                  gap: 3,
                }}
              >
                {metrics.map(metric => (
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
                        onClick={() => handleRemoveMetric(metric.id)}
                        disabled={isRemoving === metric.id}
                        sx={{
                          padding: theme.spacing(0.25),
                          '& .MuiSvgIcon-root': {
                            fontSize: theme.typography.caption.fontSize,
                            color: 'currentColor',
                          },
                        }}
                      >
                        {isRemoving === metric.id ? (
                          <CircularProgress size={12} />
                        ) : (
                          <CloseIcon fontSize="inherit" />
                        )}
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
                      usedIn={[behavior.name]}
                      showUsage={false}
                    />
                  </Box>
                ))}
              </Box>
            ) : (
              <Box
                sx={{
                  p: 4,
                  textAlign: 'center',
                  border: theme => `2px dashed ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius / 2,
                }}
              >
                <Typography variant="body1" color="text.secondary">
                  No metrics assigned to this behavior yet.
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Drawer>
  );
}
