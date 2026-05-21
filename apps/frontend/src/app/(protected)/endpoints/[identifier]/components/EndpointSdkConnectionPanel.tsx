'use client';

import {
  Alert,
  Box,
  Chip,
  Grid,
  Paper,
  Tooltip,
  Typography,
} from '@mui/material';
import SectionCard from '@/components/common/SectionCard';
import { getStatusColor } from '@/utils/status-colors';
import { useEndpointDetailContext } from './EndpointDetailContext';

export default function EndpointSdkConnectionPanel() {
  const { endpoint } = useEndpointDetailContext();

  return (
    <SectionCard title="SDK connection">
      <Grid container spacing={2}>
        {endpoint.endpoint_metadata ? (
          <>
            {/* Function Name */}
            {endpoint.endpoint_metadata.sdk_connection?.function_name && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle2" color="text.secondary">
                  Function Name
                </Typography>
                <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                  {endpoint.endpoint_metadata.sdk_connection.function_name}
                </Typography>
              </Grid>
            )}

            {/* Function Description */}
            {endpoint.endpoint_metadata.function_schema?.description && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle2" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body1">
                  {endpoint.endpoint_metadata.function_schema.description}
                </Typography>
              </Grid>
            )}

            {/* Function Parameters */}
            {endpoint.endpoint_metadata.function_schema?.parameters && (
              <Grid size={12}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  Function Parameters
                </Typography>
                <Paper
                  variant="outlined"
                  sx={{ p: 2, bgcolor: 'background.default' }}
                >
                  {Object.keys(
                    endpoint.endpoint_metadata.function_schema.parameters
                  ).length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      No parameters
                    </Typography>
                  ) : (
                    <Box
                      component="table"
                      sx={{ width: '100%', borderCollapse: 'collapse' }}
                    >
                      <Box component="thead">
                        <Box component="tr">
                          <Box
                            component="th"
                            sx={{ textAlign: 'left', pb: 1, pr: 2 }}
                          >
                            <Typography variant="caption" fontWeight="bold">
                              Parameter
                            </Typography>
                          </Box>
                          <Box
                            component="th"
                            sx={{ textAlign: 'left', pb: 1, pr: 2 }}
                          >
                            <Typography variant="caption" fontWeight="bold">
                              Type
                            </Typography>
                          </Box>
                          <Box component="th" sx={{ textAlign: 'left', pb: 1 }}>
                            <Typography variant="caption" fontWeight="bold">
                              Default
                            </Typography>
                          </Box>
                        </Box>
                      </Box>
                      <Box component="tbody">
                        {Object.entries(
                          endpoint.endpoint_metadata.function_schema.parameters
                        ).map(([param, info]: [string, unknown]) => {
                          const paramInfo = info as {
                            type?: string;
                            default?: unknown;
                          };
                          return (
                            <Box
                              component="tr"
                              key={param}
                              sx={{
                                borderTop: 1,
                                borderColor: 'divider',
                              }}
                            >
                              <Box component="td" sx={{ py: 1, pr: 2 }}>
                                <Typography
                                  variant="body2"
                                  sx={{
                                    fontFamily: 'monospace',
                                    fontWeight: 500,
                                  }}
                                >
                                  {param}
                                </Typography>
                              </Box>
                              <Box component="td" sx={{ py: 1, pr: 2 }}>
                                <Typography
                                  variant="caption"
                                  sx={{ fontFamily: 'monospace' }}
                                  color="text.secondary"
                                >
                                  {paramInfo.type
                                    ? paramInfo.type
                                        .replace(/<class '(.+?)'>/g, '$1')
                                        .replace(/typing\./g, '')
                                        .replace(/builtins\./g, '')
                                    : '—'}
                                </Typography>
                              </Box>
                              <Box component="td" sx={{ py: 1 }}>
                                <Typography
                                  variant="caption"
                                  sx={{ fontFamily: 'monospace' }}
                                  color="text.secondary"
                                >
                                  {paramInfo.default !== null
                                    ? String(paramInfo.default)
                                    : '—'}
                                </Typography>
                              </Box>
                            </Box>
                          );
                        })}
                      </Box>
                    </Box>
                  )}
                </Paper>
              </Grid>
            )}

            {/* Mapping Information */}
            {endpoint.endpoint_metadata.mapping_info && (
              <Grid size={12}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  Mapping Status
                </Typography>
                <Paper
                  variant="outlined"
                  sx={{ p: 2, bgcolor: 'background.default' }}
                >
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Typography variant="caption" color="text.secondary">
                        Source
                      </Typography>
                      <Box sx={{ mt: 0.5 }}>
                        {(() => {
                          const source =
                            endpoint.endpoint_metadata.mapping_info.source ??
                            'unknown';
                          const sourceConfig: Record<
                            string,
                            {
                              label: string;
                              tooltip: string;
                              color: 'success' | 'warning' | 'info' | 'default';
                            }
                          > = {
                            auto_mapped: {
                              label: 'Auto-Mapped',
                              tooltip:
                                'Automatically mapped from function signature. Parameters match standard Rhesis fields.',
                              color: 'success',
                            },
                            llm_generated: {
                              label: 'LLM Generated',
                              tooltip:
                                'Mapping generated by AI based on function schema and Rhesis requirements.',
                              color: 'warning',
                            },
                            sdk_manual: {
                              label: 'SDK (Manual)',
                              tooltip:
                                'Manually configured mapping through SDK registration.',
                              color: 'info',
                            },
                            sdk_hybrid: {
                              label: 'SDK (Hybrid)',
                              tooltip:
                                'Hybrid mapping combining automatic detection with SDK configuration.',
                              color: 'info',
                            },
                            manual: {
                              label: 'Manual',
                              tooltip:
                                'Manually configured mapping through the UI.',
                              color: 'info',
                            },
                          };
                          const config = sourceConfig[source] || {
                            label: source,
                            tooltip: 'Unknown mapping source',
                            color: 'default' as const,
                          };

                          return (
                            <Tooltip
                              title={config.tooltip}
                              arrow
                              placement="top"
                            >
                              <Chip
                                label={config.label}
                                size="small"
                                color={config.color}
                                variant="outlined"
                              />
                            </Tooltip>
                          );
                        })()}
                      </Box>
                    </Grid>
                    {endpoint.endpoint_metadata.mapping_info.confidence !==
                      undefined && (
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <Typography variant="caption" color="text.secondary">
                          Confidence
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                          {(
                            endpoint.endpoint_metadata.mapping_info.confidence *
                            100
                          ).toFixed(0)}
                          %
                        </Typography>
                      </Grid>
                    )}
                    {endpoint.endpoint_metadata.mapping_info.reasoning && (
                      <Grid size={12}>
                        <Typography variant="caption" color="text.secondary">
                          Reasoning
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                          {endpoint.endpoint_metadata.mapping_info.reasoning}
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </Paper>
              </Grid>
            )}

            {/* Validation Error */}
            {endpoint.endpoint_metadata.validation_error && (
              <Grid size={12}>
                <Alert severity="error">
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    Validation Error
                  </Typography>
                  <Typography variant="body2">
                    {endpoint.endpoint_metadata.validation_error.error}
                  </Typography>
                  {endpoint.endpoint_metadata.validation_error.reason && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ mt: 1, display: 'block' }}
                    >
                      Reason:{' '}
                      {endpoint.endpoint_metadata.validation_error.reason}
                    </Typography>
                  )}
                </Alert>
              </Grid>
            )}

            {/* Last Error */}
            {endpoint.endpoint_metadata.last_error &&
              !endpoint.endpoint_metadata.validation_error && (
                <Grid size={12}>
                  <Alert severity="warning">
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      Last Error
                    </Typography>
                    <Typography variant="body2">
                      {endpoint.endpoint_metadata.last_error}
                    </Typography>
                  </Alert>
                </Grid>
              )}

            {/* Timestamps and Status */}
            <Grid size={{ xs: 12, sm: 4 }}>
              {endpoint.endpoint_metadata.created_at && (
                <>
                  <Typography variant="caption" color="text.secondary">
                    Created
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {new Date(
                      endpoint.endpoint_metadata.created_at
                    ).toLocaleString()}
                  </Typography>
                </>
              )}
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              {endpoint.endpoint_metadata.last_registered && (
                <>
                  <Typography variant="caption" color="text.secondary">
                    Last Registered
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {new Date(
                      endpoint.endpoint_metadata.last_registered
                    ).toLocaleString()}
                  </Typography>
                </>
              )}
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <Typography variant="caption" color="text.secondary">
                Status
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                {endpoint.status ? (
                  <Chip
                    label={endpoint.status.name}
                    size="small"
                    variant="outlined"
                    color={getStatusColor(endpoint.status.name)}
                  />
                ) : (
                  <Chip
                    label="Unknown"
                    size="small"
                    variant="outlined"
                    color="default"
                  />
                )}
              </Box>
            </Grid>
          </>
        ) : (
          <Grid size={12}>
            <Typography variant="body2" color="text.secondary">
              No SDK connection metadata available
            </Typography>
          </Grid>
        )}
      </Grid>
    </SectionCard>
  );
}
