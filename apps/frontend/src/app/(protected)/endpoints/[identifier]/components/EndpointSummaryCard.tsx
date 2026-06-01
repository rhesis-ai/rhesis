'use client';

import Link from 'next/link';
import { Box } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import SectionCard from '@/components/common/SectionCard';
import ViewField from '@/components/common/ViewField';
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
  const target = connectionTarget(endpoint);

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
        <ViewField label="Connection type">
          <GridBadge size="detail" label={endpoint.connection_type} />
        </ViewField>

        <ViewField
          label="Target"
          inputSx={{
            fontFamily:
              endpoint.connection_type === 'SDK' ? 'monospace' : 'inherit',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          value={target}
        />

        <ViewField label="Environment">
          <GridBadge
            size="detail"
            label={
              endpoint.environment.charAt(0).toUpperCase() +
              endpoint.environment.slice(1)
            }
          />
        </ViewField>

        <ViewField label="Status">
          <GridBadge size="detail" label={endpoint.status?.name ?? 'Unknown'} />
        </ViewField>

        <ViewField label="Project">
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
        </ViewField>

        <ViewField label="Tracing">
          <GridBadge
            size="detail"
            label={endpoint.disable_tracing ? 'Disabled' : 'Enabled'}
          />
        </ViewField>

        <ViewField label="Config source">
          <GridBadge
            size="detail"
            label={formatLabel(endpoint.config_source)}
          />
        </ViewField>

        {endpoint.connection_type === 'REST' && endpoint.method ? (
          <ViewField label="Method">
            <GridBadge size="detail" label={endpoint.method} />
          </ViewField>
        ) : null}
      </Box>
    </SectionCard>
  );
}
