'use client';

import { Box, Typography } from '@mui/material';
import Link from 'next/link';
import GridBadge from '@/components/common/GridBadge';
import SectionCard from '@/components/common/SectionCard';
import { useEndpointDetailContext } from './EndpointDetailContext';

function connectionTarget(
  endpoint: ReturnType<typeof useEndpointDetailContext>['endpoint']
) {
  if (endpoint.connection_type === 'SDK') {
    const fn = endpoint.endpoint_metadata?.sdk_connection?.function_name;
    return fn ? String(fn) : 'SDK function (not registered)';
  }
  return endpoint.url || 'No URL configured';
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ');
}

export default function EndpointSummaryCard() {
  const { endpoint } = useEndpointDetailContext();

  return (
    <SectionCard title="Endpoint summary">
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(3, 1fr)',
          },
          gap: 2.5,
        }}
      >
        <Box>
          <Typography variant="caption" color="text.secondary">
            Connection type
          </Typography>
          <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <GridBadge size="detail" label={endpoint.connection_type} />
          </Box>
        </Box>

        <Box sx={{ minWidth: 0 }}>
          <Typography variant="caption" color="text.secondary">
            Target
          </Typography>
          <Typography
            variant="body2"
            sx={{
              mt: 0.5,
              fontWeight: 500,
              fontFamily:
                endpoint.connection_type === 'SDK' ? 'monospace' : 'inherit',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={connectionTarget(endpoint)}
          >
            {connectionTarget(endpoint)}
          </Typography>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary">
            Environment
          </Typography>
          <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <GridBadge
              size="detail"
              label={
                endpoint.environment.charAt(0).toUpperCase() +
                endpoint.environment.slice(1)
              }
            />
          </Box>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary">
            Status
          </Typography>
          <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <GridBadge
              size="detail"
              label={endpoint.status?.name ?? 'Unknown'}
            />
          </Box>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary">
            Project
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {endpoint.project_id ? (
              <Link
                href={`/projects/${endpoint.project_id}`}
                style={{ color: 'inherit', fontWeight: 500 }}
              >
                {endpoint.project?.name || 'View project'}
              </Link>
            ) : (
              'No project assigned'
            )}
          </Typography>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary">
            Tracing
          </Typography>
          <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <GridBadge
              size="detail"
              label={endpoint.disable_tracing ? 'Disabled' : 'Enabled'}
            />
          </Box>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary">
            Config source
          </Typography>
          <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <GridBadge
              size="detail"
              label={formatLabel(endpoint.config_source)}
            />
          </Box>
        </Box>

        {endpoint.connection_type === 'REST' && endpoint.method && (
          <Box>
            <Typography variant="caption" color="text.secondary">
              Method
            </Typography>
            <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <GridBadge size="detail" label={endpoint.method} />
            </Box>
          </Box>
        )}
      </Box>
    </SectionCard>
  );
}
